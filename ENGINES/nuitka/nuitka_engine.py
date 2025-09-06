# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
Backward-compatibility shim for the Nuitka engine.
The canonical implementation is in engine_plugins/nuitka/engine.py.
This module only re-exports the engine class to avoid duplication.
"""

from .engine import NuitkaEngine

__all__ = ["NuitkaEngine"]
