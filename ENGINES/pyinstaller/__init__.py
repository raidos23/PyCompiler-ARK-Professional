# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import importlib
import pkgutil

__all__: list[str] = []

# Explicit registration to ensure the engine is available even if auto-import misses it
try:
    from engine_sdk import registry as _registry  # type: ignore

    from .engine import PyInstallerEngine as _PyInstallerEngine

    if _registry:
        _registry.register(_PyInstallerEngine)
except Exception:
    pass


def _auto_import_all() -> None:
    """
    Import all Python modules and subpackages contained in this package.
    This ensures any engine definitions or side-effects are loaded on import.
    """
    try:
        pkg_name = __name__
        for _finder, name, _ispkg in pkgutil.walk_packages(
            __path__, prefix=f"{pkg_name}."
        ):
            try:
                importlib.import_module(name)
                short = name.rsplit(".", 1)[-1]
                if short not in __all__:
                    __all__.append(short)
            except Exception:
                pass
    except Exception:
        pass


_auto_import_all()
