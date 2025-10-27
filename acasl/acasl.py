# SPDX-License-Identifier: GPL-3.0-only
"""
ACASL - After-Compilation Actions System & Loader

Système modulaire de plugins pour exécuter des actions APRÈS la compilation.

Caractéristiques principales:
- Détection et chargement automatiques des plugins depuis le dossier "Plugins" à la racine du projet
- Enregistrement des plugins avec identifiant unique et métadonnées
- Hook d'exécution après compilation (on_post_compile)
- Isolation des erreurs (un plugin défaillant ne bloque pas les autres)
- Gestion des dépendances et ordre d'exécution (topologie + priorité)
- API publique pour ajouter, supprimer, lister, activer, désactiver des plugins
- Optimisé pour environnements à ressources limitées (stdlib uniquement, I/O minimisées)

Convention de plugin:
- Chaque package plugin dans Plugins/ doit exposer une fonction: acasl_register(manager: ACASL) -> None
  Cette fonction doit instancier le plugin (sous-classe de Ac_PluginBase) et l'enregistrer via manager.add_plugin(...).

Exemple d'utilisation:

    from pathlib import Path
    from acasl import ACASL, PostCompileContext

    project_root = Path(__file__).resolve().parent
    acasl = ACASL(project_root)
    acasl.load_plugins_from_directory(project_root / "Plugins")
    ctx = PostCompileContext(project_root, artifacts=[...])
    results = acasl.run_post_compile(ctx)
    for r in results:
        print(r)

"""
from __future__ import annotations

import fnmatch
import importlib.util
import logging
import os
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "Ac_PluginBase",
    "PluginMeta",
    "PostCompileContext",
    "ExecutionReport",
    "ACASL",
]


# Configuration logger par défaut (faible verbosité pour embarqué)
_logger = logging.getLogger("acasl")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter("[%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


ACASL_PLUGIN_REGISTER_FUNC = "acasl_register"


@dataclass(frozen=True)
class PluginMeta:
    """Métadonnées d'un plugin ACASL.

    id: identifiant unique (stable)
    name: nom humain
    version: chaîne de version
    description: courte description
    author: optionnel
    tags: liste de tags pour classification (ex: ["cleanup", "optimization"])
    """

    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        nid = (self.id or "").strip()
        if not nid:
            raise ValueError("PluginMeta invalide: 'id' requis")
        object.__setattr__(self, "id", nid)
        # Normaliser les tags
        try:
            normalized_tags = tuple(
                str(t).strip().lower() for t in (self.tags or []) if str(t).strip()
            )
            object.__setattr__(self, "tags", normalized_tags)
        except Exception:
            object.__setattr__(self, "tags", tuple())


class Ac_PluginBase:
    """Classe de base minimale que doivent étendre les plugins ACASL.

    Un plugin doit fournir:
    - meta: PluginMeta (avec id unique)
    - requires: dépendances (liste d'ids d'autres plugins)
    - priority: entier pour l'ordonnancement (plus petit => plus tôt)
    - on_post_compile(ctx): hook principal exécuté après compilation

    Remarques:
    - Les opérations doivent être idempotentes et robustes (embarqués)
    - Éviter les dépendances externes; stdlib uniquement
    - Les tags permettent de classifier et filtrer les plugins
    """

    meta: PluginMeta
    requires: tuple[str, ...]
    priority: int

    def __init__(
        self, meta: PluginMeta, requires: Iterable[str] = (), priority: int = 100
    ) -> None:
        if not meta or not meta.id:
            raise ValueError("PluginMeta invalide: 'id' requis")
        # Normaliser l'id pour éviter erreurs de casse/espaces accidentelles
        norm_id = meta.id.strip()
        if not norm_id:
            raise ValueError("PluginMeta invalide: 'id' vide")
        self.meta = meta
        self.requires = tuple(str(r).strip() for r in requires if str(r).strip())
        self.priority = int(priority)

    # Hook principal
    def on_post_compile(
        self, ctx: PostCompileContext
    ) -> None:  # pragma: no cover - à surcharger
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Plugin {self.meta.id} v{self.meta.version} prio={self.priority} tags={self.meta.tags}>"


@dataclass
class PostCompileContext:
    """Contexte passé aux plugins ACASL.

    Fournit utilitaires pour accéder aux artefacts compilés et à la configuration.
    """

    project_root: Path
    artifacts: list[str] = field(default_factory=list)
    output_dir: Optional[str] = None
    config: dict[str, Any] = field(default_factory=dict)
    _iter_cache: dict[tuple[tuple[str, ...], tuple[str, ...]], list[Path]] = field(
        default_factory=dict, repr=False, compare=False
    )

    def iter_artifacts(
        self, include: Iterable[str] = (), exclude: Iterable[str] = ()
    ) -> Iterable[Path]:
        """Itère sur les artefacts compilés en appliquant des motifs glob d'inclusion/exclusion.

        - include: motifs type glob (ex: "*.exe", "*.so"); si vide, retourne tous les artefacts
        - exclude: motifs à exclure
        Optimisé: évite la création de grosses listes; yield au fil de l'eau.
        """
        inc = tuple(include) if include else ("*",)
        exc = tuple(exclude) if exclude else tuple()

        def is_excluded(p: Path) -> bool:
            s = p.as_posix()
            for pat in exc:
                if fnmatch.fnmatch(s, pat):
                    return True
            return False

        for art_str in self.artifacts or []:
            try:
                art_path = Path(art_str)
                if not art_path.is_file():
                    continue
                # Vérifier inclusion
                matched = False
                for pat in inc:
                    if fnmatch.fnmatch(art_path.name, pat):
                        matched = True
                        break
                if matched and not is_excluded(art_path):
                    yield art_path
            except Exception:
                continue

    def iter_files(
        self, include: Iterable[str], exclude: Iterable[str] = ()
    ) -> Iterable[Path]:
        """Itère sur les fichiers du projet en appliquant des motifs glob d'inclusion/exclusion.

        - include: motifs type glob (ex: "**/*.py", "src/**/*.c")
        - exclude: motifs à exclure (ex: "venv/**", "**/__pycache__/**")
        Optimisé: évite la création de grosses listes; yield au fil de l'eau.
        """
        root = self.project_root
        inc = tuple(include) if include else ("**/*",)
        exc = tuple(exclude) if exclude else tuple()

        def is_excluded(p: Path) -> bool:
            s = p.as_posix()
            for pat in exc:
                if fnmatch.fnmatch(s, pat):
                    return True
            return False

        for pat in inc:
            for path in root.glob(pat):
                if path.is_file() and not is_excluded(path):
                    yield path


@dataclass
class ExecutionItem:
    plugin_id: str
    name: str
    success: bool
    duration_ms: float
    error: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class ExecutionReport:
    """Rapport d'exécution agrégé après run_post_compile."""

    items: list[ExecutionItem] = field(default_factory=list)

    def add(self, item: ExecutionItem) -> None:
        self.items.append(item)

    @property
    def ok(self) -> bool:
        return all(i.success for i in self.items)

    def summary(self) -> str:
        total = len(self.items)
        ok = sum(1 for i in self.items if i.success)
        ko = total - ok
        dur = sum(i.duration_ms for i in self.items)
        return (
            f"Plugins ACASL: {ok}/{total} ok, {ko} échec(s), temps total {dur:.1f} ms"
        )

    def by_tag(self, tag: str) -> list[ExecutionItem]:
        """Retourne les items ayant le tag spécifié."""
        tag_lower = str(tag).strip().lower()
        return [i for i in self.items if tag_lower in i.tags]

    def __iter__(self):
        return iter(self.items)


class _PluginRecord:
    __slots__ = (
        "plugin",
        "active",
        "requires",
        "priority",
        "order",
        "insert_idx",
        "module_path",
        "module_name",
    )

    def __init__(self, plugin: Ac_PluginBase, insert_idx: int) -> None:
        self.plugin = plugin
        self.active = True
        self.requires = tuple(plugin.requires)
        self.priority = plugin.priority
        self.order = 0  # calculé
        self.insert_idx = insert_idx
        self.module_path: Optional[Path] = None
        self.module_name: Optional[str] = None


class ACASL:
    """Gestionnaire principal des plugins et de leur exécution après compilation."""

    def __init__(
        self,
        project_root: Path,
        config: Optional[dict[str, Any]] = None,
        *,
        plugin_timeout_s: float = 0.0,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.config = dict(config or {})
        self._registry: dict[str, _PluginRecord] = {}
        self._insert_counter = 0
        # Timeout settings
        self.plugin_timeout_s = float(plugin_timeout_s)

    # API publique
    def add_plugin(self, plugin: Ac_PluginBase) -> None:
        if not isinstance(plugin, Ac_PluginBase):
            raise TypeError("Le plugin doit être une instance de Ac_PluginBase")
        pid = plugin.meta.id
        if pid in self._registry:
            raise ValueError(f"Plugin id déjà enregistré: {pid}")
        rec = _PluginRecord(plugin, self._insert_counter)
        self._registry[pid] = rec
        self._insert_counter += 1
        _logger.debug("Plugin ACASL ajouté: %s", plugin)

    def remove_plugin(self, plugin_id: str) -> bool:
        return self._registry.pop(plugin_id, None) is not None

    def list_plugins(
        self, include_inactive: bool = True, tag_filter: Optional[str] = None
    ) -> list[tuple[str, PluginMeta, bool, int]]:
        """Liste les plugins, optionnellement filtrés par tag."""
        out = []
        tag_lower = str(tag_filter).strip().lower() if tag_filter else None
        for pid, rec in self._registry.items():
            if include_inactive or rec.active:
                # Filtrer par tag si spécifié
                if tag_lower and tag_lower not in rec.plugin.meta.tags:
                    continue
                out.append((pid, rec.plugin.meta, rec.active, rec.priority))
        out.sort(key=lambda x: (x[3], x[0]))
        return out

    def enable_plugin(self, plugin_id: str) -> bool:
        rec = self._registry.get(plugin_id)
        if not rec:
            return False
        rec.active = True
        return True

    def disable_plugin(self, plugin_id: str) -> bool:
        rec = self._registry.get(plugin_id)
        if not rec:
            return False
        rec.active = False
        return True

    def set_priority(self, plugin_id: str, priority: int) -> bool:
        rec = self._registry.get(plugin_id)
        if not rec:
            return False
        rec.priority = int(priority)
        rec.plugin.priority = int(priority)
        return True

    # Chargement automatique
    def load_plugins_from_directory(
        self, directory: Path
    ) -> tuple[int, list[tuple[str, str]]]:
        """Charge automatiquement tous les plugins depuis un dossier.

        Retourne (nombre_plugins_enregistrés, liste_erreurs[(module, message)]).
        """
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            _logger.warning("Dossier plugins introuvable: %s", directory)
            return 0, [(str(directory), "non trouvé ou non répertoire")]

        count = 0
        errors: list[tuple[str, str]] = []
        # Parcourt uniquement les packages Python (dossiers contenant __init__.py)
        try:
            pkg_dirs = sorted(
                [p for p in directory.iterdir() if p.is_dir()], key=lambda p: p.name
            )
        except Exception:
            pkg_dirs = []
        for pkg_dir in pkg_dirs:
            if pkg_dir.name.startswith("__"):
                continue
            init_file = pkg_dir / "__init__.py"
            if not init_file.exists():
                continue
            mod_name = f"acasl_plugin_{pkg_dir.name}"
            try:
                spec = importlib.util.spec_from_file_location(
                    mod_name, str(init_file), submodule_search_locations=[str(pkg_dir)]
                )
                if spec is None or spec.loader is None:
                    raise ImportError("spec invalide")
                module = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = module
                spec.loader.exec_module(module)  # type: ignore[attr-defined]

                # Recherche et appel de la fonction d'enregistrement si présente
                reg = getattr(module, ACASL_PLUGIN_REGISTER_FUNC, None)
                if not callable(reg):
                    _logger.debug(
                        "Package %s: aucune fonction %s, ignoré",
                        pkg_dir.name,
                        ACASL_PLUGIN_REGISTER_FUNC,
                    )
                    continue
                # Appeler l'enregistrement
                before_ids = set(self._registry.keys())
                reg(self)  # le package appelle self.add_plugin(...)
                new_ids = [k for k in self._registry.keys() if k not in before_ids]
                for pid in new_ids:
                    rec = self._registry.get(pid)
                    if rec is not None:
                        rec.module_path = init_file
                        rec.module_name = mod_name
                # Validation de signature supprimée (simplification)
                added = len(new_ids)
                if added <= 0:
                    _logger.warning(
                        "Aucun plugin enregistré par package %s", pkg_dir.name
                    )
                else:
                    count += added
                    _logger.info("Plugin ACASL chargé depuis package %s", pkg_dir.name)
            except Exception as exc:  # isolation
                msg = f"échec chargement: {exc}"
                errors.append((pkg_dir.name, msg))
                _logger.error("%s: %s", pkg_dir.name, msg)
        return count, errors

    # Ordonnancement et exécution
    def _resolve_order(self) -> list[str]:
        """Résout l'ordre d'exécution en respectant dépendances et priorités.

        - Filtre les plugins inactifs
        - Ignore les dépendances inconnues (log warning)
        - Kahn + file de priorité (priority, insert_idx) pour stabilité
        - En cas de cycle, journalise et insère les restants par priorité
        """
        active_items = {pid: rec for pid, rec in self._registry.items() if rec.active}
        if not active_items:
            return []

        # Construire graphe
        indeg: dict[str, int] = {pid: 0 for pid in active_items}
        children: dict[str, list[str]] = {pid: [] for pid in active_items}

        for pid, rec in active_items.items():
            for dep in rec.requires:
                if dep not in active_items:
                    _logger.warning(
                        "Dépendance manquante pour %s: '%s' (ignorée)", pid, dep
                    )
                    continue
                indeg[pid] += 1
                children[dep].append(pid)

        # File de départ (indeg=0) triée par priorité puis ordre d'insertion
        roots = sorted(
            [pid for pid, d in indeg.items() if d == 0],
            key=lambda x: (active_items[x].priority, active_items[x].insert_idx, x),
        )
        order: list[str] = []
        import heapq

        heap: list[tuple[int, int, str]] = []
        for pid in roots:
            rec = active_items[pid]
            heapq.heappush(heap, (rec.priority, rec.insert_idx, pid))

        while heap:
            _, _, pid = heapq.heappop(heap)
            order.append(pid)
            for ch in children[pid]:
                indeg[ch] -= 1
                if indeg[ch] == 0:
                    rch = active_items[ch]
                    heapq.heappush(heap, (rch.priority, rch.insert_idx, ch))

        if len(order) != len(active_items):
            # Cycle détecté; insérer les restants par priorité pour ne pas bloquer
            remaining = [pid for pid in active_items if pid not in order]
            _logger.error("Cycle de dépendances détecté: %s", ", ".join(remaining))
            remaining.sort(
                key=lambda x: (active_items[x].priority, active_items[x].insert_idx, x)
            )
            order.extend(remaining)
        return order

    def run_post_compile(
        self, ctx: Optional[PostCompileContext] = None
    ) -> ExecutionReport:
        """Exécute le hook 'on_post_compile' de tous les plugins actifs.

        Exécution séquentielle en respectant dépendances et priorités.
        """
        if ctx is None:
            ctx = PostCompileContext(self.project_root, config=self.config)
        else:
            ctx.project_root = Path(ctx.project_root).resolve()
            ctx.config = dict(self.config) | dict(ctx.config or {})

        report = ExecutionReport()
        # Construire graphe des dépendances des plugins actifs
        active_items = {pid: rec for pid, rec in self._registry.items() if rec.active}
        if not active_items:
            _logger.info("Aucun plugin ACASL actif")
            return report

        # Résoudre l'ordre d'exécution
        order = self._resolve_order()

        # Exécution séquentielle
        for pid in order:
            rec = active_items[pid]
            plg = rec.plugin
            start = time.perf_counter()
            try:
                plg.on_post_compile(ctx)
                duration_ms = (time.perf_counter() - start) * 1000.0
                report.add(
                    ExecutionItem(
                        plugin_id=pid,
                        name=plg.meta.name,
                        success=True,
                        duration_ms=duration_ms,
                        tags=plg.meta.tags,
                    )
                )
                _logger.info(
                    "Plugin ACASL %s exécuté avec succès (%.1f ms)", pid, duration_ms
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000.0
                report.add(
                    ExecutionItem(
                        plugin_id=pid,
                        name=plg.meta.name,
                        success=False,
                        duration_ms=duration_ms,
                        error=str(exc),
                        tags=plg.meta.tags,
                    )
                )
                _logger.error("Plugin ACASL %s a échoué: %s", pid, exc)

        _logger.info(report.summary())
        return report


# Petit utilitaire: décorateur d'enregistrement (optionnel pour les plugins)
# Usage dans un plugin:
#   @register_acasl_plugin
#   class MyPlugin(Ac_PluginBase): ...
# Puis dans acasl_register(manager): manager.add_plugin(MyPlugin(...))
# (Ce décorateur ne fait que marquer la classe; utile si l'auteur veut introspecter)


def register_acasl_plugin(cls: Any) -> Any:
    setattr(cls, "__acasl_plugin__", True)
    return cls
