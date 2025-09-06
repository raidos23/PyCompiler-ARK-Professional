# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from typing import Dict, List

# Engine-controlled auto builder for Nuitka
# Signature required by host: (matched: dict, pkg_to_import: dict) -> list[str]

from engine_sdk import register_auto_builder  # type: ignore


def _normalize_plugin_arg(val: str) -> str:
    v = (val or '').strip()
    if not v:
        return v
    if v.startswith('--enable-plugin=') or v.startswith('--plugin-enable='):
        name = v.split('=', 1)[1]
        return f"--enable-plugin={name}"
    return f"--enable-plugin={v}"


def AUTO_BUILDER(matched: Dict[str, Dict[str, object]], pkg_to_import: Dict[str, str]) -> List[str]:
    """
    Build Nuitka arguments from the engine-owned mapping.

    Mapping conventions supported for an entry value under key "nuitka":
      - str: plugin name or full flag; normalized as --enable-plugin=<name>
      - list[str]: multiple plugins/flags
      - dict: expects 'args' or 'flags' -> str | list[str]
      - True: ignored by default (no generic meaning)
    """
    out: List[str] = []
    seen = set()

    for pkg, entry in matched.items():
        if not isinstance(entry, dict):
            continue
        val = entry.get('nuitka')
        if val is True:
            continue
        args: List[str] = []
        if isinstance(val, str):
            args = [_normalize_plugin_arg(val)]
        elif isinstance(val, list):
            args = [_normalize_plugin_arg(str(x)) for x in val]
        elif isinstance(val, dict):
            a = val.get('args') or val.get('flags')
            if isinstance(a, list):
                args = [str(x) for x in a]
            elif isinstance(a, str):
                args = [str(a)]
        for a in args:
            if a not in seen:
                out.append(a)
                seen.add(a)

    return out

# Register at import time via the SDK facade
try:
    register_auto_builder("nuitka", AUTO_BUILDER)
except Exception:
    pass
