# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

# Stable re-export of the host base class
from Core.engines_loader.base import CompilerEngine  # type: ignore[F401]

__all__ = ["CompilerEngine"]
