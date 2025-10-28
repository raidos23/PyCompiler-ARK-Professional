# SPDX-License-Identifier: GPL-3.0-only
# Nuitka engine package - auto-import all submodules

# Copyright (C) 2025 Samuel Amen Ague
# Author: Samuel Amen Ague
from __future__ import annotations

import importlib
import pkgutil

__all__: list[str] = []

# Explicit registration to ensure the engine is available even if auto-import misses it
try:
    from engine_sdk import registry as _registry  # type: ignore

    from .engine import NuitkaEngine as _NuitkaEngine

    if _registry:
        _registry.register(_NuitkaEngine)
except Exception:
    pass

def _auto_import_all() -> None:
    """
    Import all Python modules and subpackages contained in this package.
    This ensures any engine definitions or side-effects are loaded on import.
    """
    try:
        pkg_name = __name__
        # __path__ is defined for packages; walk through all nested modules/packages
        for _finder, name, _ispkg in pkgutil.walk_packages(
            __path__, prefix=f"{pkg_name}."
        ):
            try:
                importlib.import_module(name)
                # Optionally track short module names in __all__
                short = name.rsplit(".", 1)[-1]
                if short not in __all__:
                    __all__.append(short)
            except Exception:
                # Avoid breaking package import if some submodule import fails
                pass
    except Exception:
        # Be resilient to environments where __path__ is unusual
        pass

_auto_import_all()
