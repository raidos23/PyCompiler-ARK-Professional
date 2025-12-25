
# Dynamic discovery for pluggable compilation engines
#
# Strict mode: discover engines ONLY from the ENGINES/ folder at the project root.
# Engines must self-register on import via utils.engines_loader.registry.register(MyEngine).

from __future__ import annotations

import importlib
import os
import pkgutil
import sys

from . import registry as registry  # re-export registry module
from .base import CompilerEngine  # re-export base type


def _discover_external_plugins(base_path: str) -> None:
    """Import all top-level modules and packages under base_path (ENGINES/),
    recursively importing subpackages to trigger engine registration side-effects.
    """
    try:
        if not os.path.isdir(base_path):
            return
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
        # Import only top-level PACKAGES (directories with __init__.py). Skip bare modules.
        for _finder, name, ispkg in pkgutil.iter_modules([base_path]):
            if not ispkg:
                # Enforce package-only engines
                continue
            try:
                # Import the package so its __init__ can self-register the engine
                importlib.import_module(name)
                # Import submodules to trigger additional registrations if needed
                pkg_path = os.path.join(base_path, name)
                for __f, subname, __ispkg in pkgutil.walk_packages(
                    [pkg_path], prefix=f"{name}."
                ):
                    try:
                        importlib.import_module(subname)
                    except Exception:
                        # Ignore broken submodules to avoid crashing global discovery
                        pass
            except Exception:
                # Ignore broken plugins; do not crash host discovery
                pass
    except Exception:
        # Never let discovery break the host application
        pass


def _auto_discover() -> None:
    """Discover and register external engine plugins ONLY from the 'ENGINES' folder at project root."""
    base_dir = os.path.dirname(__file__)
    try:
        project_root = os.path.abspath(os.path.join(base_dir, os.pardir, os.pardir))
        external_dir = os.path.join(project_root, "ENGINES")
        _discover_external_plugins(external_dir)
    except Exception:
        pass


# Perform discovery at import-time so engines are ready for UI/compile usage (packages under ENGINES/ only)
try:
    if str(os.environ.get("ARK_ENGINES_AUTO_DISCOVER", "1")).lower() not in (
        "0",
        "false",
        "no",
    ):
        _auto_discover()
except Exception:
    pass

__all__ = ["CompilerEngine", "registry"]
