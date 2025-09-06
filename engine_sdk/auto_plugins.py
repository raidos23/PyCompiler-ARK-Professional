# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

# Pass-through to host auto_plugins helpers
from utils.auto_plugins import (
    compute_auto_for_engine,
    compute_for_all,
    register_aliases,
    register_auto_builder,
    register_import_alias,
    register_package_import_name,
)

__all__ = [
    "compute_auto_for_engine",
    "compute_for_all",
    "register_auto_builder",
    "register_aliases",
    "register_import_alias",
    "register_package_import_name",
]
