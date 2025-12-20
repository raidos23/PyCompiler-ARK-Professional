from __future__ import annotations

import fnmatch
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


__all__ = [
    "BcPluginBase",
    "PluginMeta",
    "PreCompileContext",
    "ExecutionReport",
]

# Configuration logger par défaut (faible verbosité pour embarqué)
_logger = logging.getLogger("bcasl")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter("[%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)

BCASL_PLUGIN_REGISTER_FUNC = "bcasl_register"


@dataclass(frozen=True)
class PluginMeta:
    """Métadonnées d'un plugin.

    id: identifiant unique (stable)
    name: nom
    version: chaîne de version
    description: courte description
    author: optionnel
    """

    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    tag: str = ""

    def __post_init__(self) -> None:
        nid = (self.id or "").strip()
        if not nid:
            raise ValueError("PluginMeta invalide: 'id' requis")
        object.__setattr__(self, "id", nid)


class BcPluginBase:
    """Classe de base minimale que doivent étendre les plugins BCASL.

    Un plugin doit fournir:
    - meta: PluginMeta (avec id unique)
    - requires: dépendances (liste d'ids d'autres plugins)
    - priority: entier pour l'ordonnancement (plus petit => plus tôt)
    - on_pre_compile(ctx): hook principal exécuté avant compilation

    Remarques:
    - Les opérations doivent être idempotentes et robustes (embarqués)
    - Éviter les dépendances externes; stdlib uniquement
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

    #  principal Hook
    def on_pre_compile(
        self, ctx: PreCompileContext
    ) -> None:  # pragma: no cover - à surcharger
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Plugin {self.meta.id} v{self.meta.version} prio={self.priority}>"

    def apply_i18n(self, gui, tr: dict[str, str]) -> None:
        raise NotImplementedError


@dataclass
class PreCompileContext:
    """Contexte passé aux plugins.

    Fournit utilitaires peu coûteux pour la découverte des fichiers et la config.
    """

    project_root: Path
    config: dict[str, Any] = field(default_factory=dict)
    _iter_cache: dict[tuple[tuple[str, ...], tuple[str, ...]], list[Path]] = field(
        default_factory=dict, repr=False, compare=False
    )

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
        # Optional caching to avoid repeated globbing across plugins
        try:
            opt = (
                dict(self.config or {}).get("options", {})
                if isinstance(self.config, dict)
                else {}
            )
            enable_cache = bool(opt.get("iter_files_cache", True))
        except Exception:
            enable_cache = True
        key = None
        if enable_cache:
            try:
                key = (tuple(sorted(inc)), tuple(sorted(exc)))
                cached = self._iter_cache.get(key)
                if cached is not None:
                    for p in cached:
                        yield p
                    return
            except Exception:
                pass

        # Pré-calcul des chemins exclus sous forme posix pour fnmatch
        def is_excluded(p: Path) -> bool:
            s = p.as_posix()
            for pat in exc:
                if fnmatch.fnmatch(s, pat):
                    return True
            return False

        collected: list[Path] = []
        for pat in inc:
            for path in root.glob(pat):
                if path.is_file() and not is_excluded(path):
                    collected.append(path)
        for p in collected:
            yield p
        if enable_cache and key is not None:
            try:
                self._iter_cache[key] = collected
            except Exception:
                pass


@dataclass
class ExecutionItem:
    plugin_id: str
    name: str
    success: bool
    duration_ms: float
    error: str = ""


@dataclass
class ExecutionReport:
    """Rapport d'exécution agrégé après run_pre_compile."""

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
        return f"Plugins: {ok}/{total} ok, {ko} échec(s), temps total {dur:.1f} ms"

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

    def __init__(self, plugin: BcPluginBase, insert_idx: int) -> None:
        self.plugin = plugin
        self.active = True
        self.requires = tuple(plugin.requires)
        self.priority = plugin.priority
        self.order = 0  # calculé
        self.insert_idx = insert_idx
        self.module_path: Optional[Path] = None
        self.module_name: Optional[str] = None


def register_plugin(cls: Any) -> Any:
    setattr(cls, "__bcasl_plugin__", True)
    return cls
