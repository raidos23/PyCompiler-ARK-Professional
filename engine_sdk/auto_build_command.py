# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

# Pass-through to host auto_plugins helpers
from Core.Auto_Command_Builder import (
    compute_auto_for_engine,
    compute_for_all,
    register_aliases,
    register_auto_builder,
    register_import_alias,
    register_package_import_name,
    _tr,
)

__all__ = [
    "compute_auto_for_engine",
    "compute_for_all",
    "register_auto_builder",
    "register_aliases",
    "register_import_alias",
    "register_package_import_name",
    "_tr",
]
