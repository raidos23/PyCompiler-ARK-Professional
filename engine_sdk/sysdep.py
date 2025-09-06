# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

# Pass-through to host system dependency manager
from utils.sys_dependency import SysDependencyManager  # type: ignore[F401]

__all__ = ["SysDependencyManager"]
