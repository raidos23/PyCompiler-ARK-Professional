# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import fnmatch
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "Ac_PluginBase",
    "PluginMeta",
    "PostCompileContext",
    "ExecutionReport",
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


def register_acasl_plugin(cls: Any) -> Any:
    setattr(cls, "__acasl_plugin__", True)
    return cls
