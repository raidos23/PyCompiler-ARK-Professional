# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

# Pass-through to host system dependency manager
from Core.sys_deps import SysDependencyManager  # type: ignore[F401]

__all__ = ["SysDependencyManager"]
