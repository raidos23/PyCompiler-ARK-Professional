from __future__ import annotations

import fnmatch
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# Configuration logger par défaut (faible verbosité pour embarqué)
_logger = logging.getLogger("cesl")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter("[%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)

CESL_PLUGIN_REGISTER_FUNC = "cesl_register"


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


class CePluginBase:
    """Classe de base minimale que doivent étendre les plugins CESL.

    Un plugin doit fournir:
    - meta: PluginMeta (avec id unique)
    - requires: dépendances (liste d'ids d'autres plugins)
    - priority: entier pour l'ordonnancement (plus petit => plus tôt)

    Remarques:
    - Les opérations doivent être idempotentes et robustes (embarqués)

    """

    def apply_i18n(self, gui, tr: dict[str, str]) -> None:
        raise NotImplementedError


def register_plugin(cls: Any) -> Any:
    setattr(cls, "__cesl_plugin__", True)
    return cls
