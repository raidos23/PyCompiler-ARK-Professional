# SPDX-License-Identifier: GPL-3.0-only
# cx_Freeze engine package - auto-register
from __future__ import annotations

__all__: list[str] = []

try:
    from engine_sdk import registry as _registry  # type: ignore
    from .engine import CxFreezeEngine as _CxFreezeEngine
    if _registry:
        _registry.register(_CxFreezeEngine)
except Exception:
    pass
