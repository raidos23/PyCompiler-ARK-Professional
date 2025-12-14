"""
Plugins_SDK
===========

Kit de développement pour plugins ARK++ couvrant:
- Contexte BC (Before Compilation)
- Contexte AC (After Compilation)
- Contexte UI (boîtes de dialogue, i18n)

Ce package expose une API stable pour les plugins tiers.
"""

# Expose uniquement les sous-packages pour éviter les imports précoces
# Les Context concrets (Ac/Bc) sont disponibles dans leurs sous-modules respectifs.

from . import AcPluginContext as AcPluginContext  # noqa: F401
from . import BcPluginContext as BcPluginContext  # noqa: F401
from . import GeneralContext as GeneralContext  # noqa: F401

__all__ = [
    "AcPluginContext",
    "BcPluginContext",
    "GeneralContext",
]
