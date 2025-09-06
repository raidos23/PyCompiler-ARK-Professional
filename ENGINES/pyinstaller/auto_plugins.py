# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from typing import Dict, List, Optional

# Engine-controlled auto builder for PyInstaller
# Signature required by host: (matched: dict, pkg_to_import: dict) -> list[str]

from engine_sdk import register_auto_builder  # type: ignore


def AUTO_BUILDER(matched: Dict[str, Dict[str, object]], pkg_to_import: Dict[str, str]) -> List[str]:
    """
    Build PyInstaller arguments from the engine-owned mapping.

    Mapping conventions supported for an entry value under key "pyinstaller":
      - True: emit ["--collect-all", {import_name}] for the matched package
      - str: a single CLI arg; supports {import_name} placeholder
      - list[str]: multiple CLI args; supports {import_name} placeholder
      - dict: expects 'args' or 'flags' -> str | list[str]; supports placeholder
    """
    out: List[str] = []
    seen_items = set()
    seen_collect_all = set()

    for pkg, entry in matched.items():
        if not isinstance(entry, dict):
            continue
        val = entry.get('pyinstaller')
        import_name = pkg_to_import.get(pkg, pkg)

        args: List[str] = []
        if val is True:
            if import_name and import_name not in seen_collect_all:
                args = ["--collect-all", import_name]
                seen_collect_all.add(import_name)
        elif isinstance(val, str):
            # Split single string into proper argv tokens (e.g. "--collect-all {import_name}")
            s = val.replace("{import_name}", import_name)
            try:
                import shlex as _shlex
                args = _shlex.split(s)
            except Exception:
                args = s.split()
        elif isinstance(val, list):
            # Flatten list entries, splitting any that contain spaces
            tmp: List[str] = []
            for x in val:
                s = str(x).replace("{import_name}", import_name)
                try:
                    import shlex as _shlex
                    parts = _shlex.split(s)
                except Exception:
                    parts = s.split()
                tmp.extend(parts)
            args = tmp
        elif isinstance(val, dict):
            a = val.get('args') or val.get('flags')
            if isinstance(a, list):
                tmp: List[str] = []
                for x in a:
                    s = str(x).replace("{import_name}", import_name)
                    try:
                        import shlex as _shlex
                        parts = _shlex.split(s)
                    except Exception:
                        parts = s.split()
                    tmp.extend(parts)
                args = tmp
            elif isinstance(a, str):
                s = str(a).replace("{import_name}", import_name)
                try:
                    import shlex as _shlex
                    args = _shlex.split(s)
                except Exception:
                    args = s.split()

        # de-dup while preserving order
        i = 0
        while i < len(args):
            item = args[i]
            key = item
            if item == "--collect-all" and (i + 1) < len(args):
                key = f"--collect-all {args[i+1]}"
            if key not in seen_items:
                out.append(item)
                seen_items.add(key)
            i += 1

    return out

# Register at import time via the SDK facade
try:
    register_auto_builder("pyinstaller", AUTO_BUILDER)
except Exception:
    pass
