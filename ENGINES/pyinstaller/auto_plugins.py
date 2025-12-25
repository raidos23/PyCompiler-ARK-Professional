# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import annotations

# Engine-controlled auto builder for PyInstaller
# Signature required by host: (matched: dict, pkg_to_import: dict) -> list[str]
from engine_sdk import register_auto_builder  # type: ignore


def AUTO_BUILDER(
    matched: dict[str, dict[str, object]], pkg_to_import: dict[str, str]
) -> list[str]:
    """
    Build PyInstaller arguments from the engine-owned mapping.

    Mapping conventions supported for an entry value under key "pyinstaller":
      - True: emit ["--collect-all", {import_name}] for the matched package
      - str: a single CLI arg; supports {import_name} placeholder
      - list[str]: multiple CLI args; supports {import_name} placeholder
      - dict: expects 'args' or 'flags' -> str | list[str]; supports placeholder
    """
    out: list[str] = []
    seen_items = set()
    seen_collect_all = set()

    for pkg, entry in matched.items():
        if not isinstance(entry, dict):
            continue
        val = entry.get("pyinstaller")
        import_name = pkg_to_import.get(pkg, pkg)

        args: list[str] = []
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
            tmp: list[str] = []
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
            a = val.get("args") or val.get("flags")
            if isinstance(a, list):
                tmp: list[str] = []
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
