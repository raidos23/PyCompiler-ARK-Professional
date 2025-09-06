# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
Backward-compatibility shim for the PyInstaller engine.
Single source of truth lives in engine_plugins/pyinstaller/engine.py.
This module simply re-exports the engine class to avoid duplicate
registrations or diverging behaviors.
"""

from .engine import PyInstallerEngine

__all__ = ["PyInstallerEngine"]
