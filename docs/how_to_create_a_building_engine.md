# How to Create a Building Engine (Industrial-Grade, Supra+)

Quick Navigation
- [TL;DR](#0-tldr-copy-paste-template)
- [Layout & discovery](#1-folder-layout-and-discovery)
- [Minimal engine](#2-minimal-engine-implementation)
- [UI tab](#3-ui-tab-create_tab-example)
- [Lifecycle](#4-full-engine-shape-and-lifecycle-hooks)
- [Venv/Tools](#5-engine-owned-venvtool-management-async-non-blocking)
- [Environment/Process](#6-environment-and-process-execution)
- [Auto-plugins](#7-auto-plugins-mapping-plug-and-play)
- [CI / Headless](#8-ci-considerations-and-non-interactive-setups)
- [Checklist](#9-developer-checklist-and-anti-patterns)
- [Troubleshooting](#10-troubleshooting-decision-tree)
- [i18n](#11-localizing-your-engine-languages)
- [i18n template](#111-recommended-i18n-implementation-template-synchronized-with-app)
- [Adapter engine](#12-adapter-engine-external-cli--complete-example)
- [Linux adapter](#13-linux-first-adapter-example)

This guide explains how to implement a pluggable compilation engine for PyCompiler Pro++ using the Engine SDK. It includes step‑by‑step templates, UI integration, auto‑plugins mapping, execution environment guidance, CI considerations, and a troubleshooting checklist.

Highlights
- Engines are Python packages under ENGINES/<engine_id> (directory with __init__.py)
- Engines must self‑register on import via the central registry
- engines_loader discovers engines strictly from ENGINES/
- Selection is explicit by tab mapping (no hidden fallbacks)
- Import the SDK and registry from engine_sdk
- Venv/tool management is engine‑owned and must be non‑blocking (asynchronous patterns)
- Output directory opening is handled exclusively by ACASL; engines must not open paths or invoke the OS file browser

Table of contents
- 0) TL;DR (copy‑paste template)
- 1) Folder layout and discovery
- 2) Minimal engine implementation
- 3) UI tab (create_tab) example
- 4) Full engine shape and lifecycle hooks
- 5) Engine‑owned venv/tool management (async, non‑blocking)
- 6) Environment and process execution
- 7) Auto‑plugins mapping (plug‑and‑play)
- 8) CI considerations and non‑interactive setups
- 9) Developer checklist and anti‑patterns
- 10) Troubleshooting (decision tree)

---

## 0) TL;DR (copy‑paste template) {#0-tldr-copy-paste-template}
```python
from engine_sdk import CompilerEngine, registry
from engine_sdk.utils import (
    resolve_executable,
    validate_args,
    normalized_program_and_args,
)

class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"

    def preflight(self, gui, file):
        # quick validation or environment checks (optional)
        return bool(file)

    def program_and_args(self, gui, file):
        prog = resolve_executable("pyinstaller")
        args = validate_args(["--onefile", file])
        return normalized_program_and_args(prog, args)

registry.register(MyEngine)
```

---

## 1) Folder layout and discovery {#1-folder-layout-and-discovery}

```
<project root>
└── ENGINES/
    └── my_engine/
        └── __init__.py
```

- The package under ENGINES/<engine_id>/ must contain __init__.py.
- Engines must self‑register on import: registry.register(MyEngine).
- engines_loader discovers engines strictly from ENGINES/.

Tip: If your engine also ships mapping.json (for auto‑plugins), place it next to __init__.py in the same ENGINES/<engine_id>/ folder.

---

## 2) Minimal engine implementation {#2-minimal-engine-implementation}

```python
from __future__ import annotations
from engine_sdk import CompilerEngine, registry
from engine_sdk.utils import resolve_executable, validate_args, normalized_program_and_args

class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"

    def preflight(self, gui, file):
        if not file:
            try:
                gui.log.append("[ERROR] No input file")
            except Exception:
                pass
            return False
        return True

    def program_and_args(self, gui, file):
        prog = resolve_executable("pyinstaller")
        args = validate_args(["--onefile", file])
        return normalized_program_and_args(prog, args)

registry.register(MyEngine)
```

Notes
- program_and_args must return (program, args) as (str, list[str]). normalized_program_and_args enforces this.
- validate_args ensures safe argv (rejects None, control chars, overly long items) and normalizes to list[str].

---

## 3) UI tab (create_tab) example {#3-ui-tab-create_tab-example}

```python
from engine_sdk import CompilerEngine, registry
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox

class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"
    _onefile = True

    def create_tab(self, gui):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("MyEngine Options"))
        cb = QCheckBox("Onefile")
        cb.setChecked(self._onefile)
        cb.stateChanged.connect(lambda s: setattr(self, "_onefile", bool(s)))
        lay.addWidget(cb)
        return w, "MyEngine"

    def program_and_args(self, gui, file):
        args = []
        if self._onefile:
            args.append("--onefile")
        args.append(file)
        return "pyinstaller", args

registry.register(MyEngine)
```

Notes
- Returning ("pyinstaller", [..]) is valid; the host will pass program and args to QProcess.
- If you need absolute paths or venv resolution, use resolve_executable or resolve_executable_path.

---

## 4) Full engine shape and lifecycle hooks {#4-full-engine-shape-and-lifecycle-hooks}

A production engine typically implements some of the following:
- id: str — stable identifier (required)
- name: str — display name
- create_tab(self, gui) -> (QWidget, str) | None — optional UI tab
- preflight(self, gui, file) -> bool — quick validation before running
- build_command(self, gui, file) -> list[str] | None — optional, for display/preview
- program_and_args(self, gui, file) -> (program: str, args: list[str]) — required to execute
- environment(self, gui, file) -> dict[str,str] | None — optional extra env vars
- get_timeout_seconds(self, gui) -> int — optional process timeout in seconds
- on_success(self, gui, file) -> None — optional hook for metadata/logging only; do NOT open output directories (ACASL owns opening and the host does not call this hook to open)

See ENGINES/pyinstaller/engine.py and ENGINES/nuitka/engine.py for robust real‑world examples, including venv‑local tool resolution.

---

## 5) Engine‑owned venv/tool management (async, non‑blocking) {#5-engine-owned-venvtool-management-async-non-blocking}

Principles
- The UI never auto‑installs engine tools; engines decide when to verify and install.
- Keep the UI thread responsive; rely on asynchronous checks and installations.
- Prefer venv‑local tools; engines should resolve and use the workspace venv.

Recommended pattern (preflight)
```python
# Inside preflight(self, gui, file)
vm = getattr(gui, 'venv_manager', None)
vroot = None
try:
    from engine_sdk import resolve_project_venv
    vroot = resolve_project_venv(gui)
except Exception:
    vroot = None

# Ask UI to create venv if missing, then stop preflight (engine will be retried later)
if not vroot:
    if vm and getattr(gui, 'workspace_dir', None):
        vm.create_venv_if_needed(gui.workspace_dir)  # async QProcess
    else:
        gui.log.append("❌ No venv detected. Create a venv in the workspace.")
    return False

# Fast non‑blocking heuristic: check console script/binary presence in venv
if vm and vm.is_tool_installed(vroot, 'pyinstaller'):
    return True

# Asynchronous confirmation via pip show; if missing, trigger async install and stop preflight
if vm:
    gui.log.append("🔎 Verifying PyInstaller in venv (async)…")
    def _on_check(ok: bool):
        if ok:
            gui.log.append("✅ PyInstaller already installed")
        else:
            gui.log.append("📦 Installing PyInstaller in venv (async)…")
            vm.ensure_tools_installed(vroot, ['pyinstaller'])  # async pipeline
    vm.is_tool_installed_async(vroot, 'pyinstaller', _on_check)
    return False

# Fallback (no VenvManager): blocking pip, last resort in CI/headless
from engine_sdk import pip_executable, pip_show, pip_install
pip = pip_executable(vroot)
if pip_show(gui, pip, 'pyinstaller') != 0:
    return pip_install(gui, pip, 'pyinstaller') == 0
return True
```

Notes
- Return False when you launch an asynchronous operation; the engine will be tried again when the user retries the build.
- VenvManager internally uses QProcess and enforces safety timeouts (no UI freeze). Avoid subprocess in the UI thread for checks.
- For Nuitka engines, reuse the same pattern with 'nuitka'. Keep system dependencies management (gcc, etc.) engine‑owned as well.

---

## 6) Environment and process execution {#6-environment-and-process-execution}

The SDK exposes safe helpers:

```python
from engine_sdk.utils import resolve_executable, resolve_executable_path
from engine_sdk.utils import validate_args, build_env, run_process

# Executable resolution
exe = resolve_executable("python")  # shutil.which + normalization
exe2 = resolve_executable_path("pyinstaller")  # alias that may be overridden by host

# Environment (reduced, deterministic)
env = build_env(extra={"LC_ALL": "C.UTF-8"})

# Non‑blocking run with timeout and streaming callbacks
code, out, err = run_process(gui, exe, ["--version"], env=env, timeout_ms=60000)
```

Best practices
- Always construct args as a list of tokens. Do not pass combined strings that include spaces.
- Use validate_args on the final argv list.
- Use get_timeout_seconds to bound long‑running external tools.
- Prefer venv‑local executables when applicable (resolve from venv/bin or venv/Scripts).

6.2) Universal output discovery (ACASL-only)

ACASL is the only component that opens the output directory after a successful build. It uses a universal, plug-and-play discovery routine from the SDK:

```python
from engine_sdk.utils import open_output_directory, discover_output_candidates

# Called by ACASL internally; listed here for documentation
opened = open_output_directory(gui, engine_id=active_engine_id, source_file=last_file, artifacts=artifacts)
# discover_output_candidates(gui, ...) returns the ordered list of candidates used above
```

Discovery strategy (no engine-specific code):
- GUI fields that look like output directories (heuristic: names/objectName/accessibleName contain both one of ["output", "dist"] and one of ["dir", "path"]).
- Parent directories of known artifacts (most recent first).
- Conventional fallbacks under the workspace: dist/, build/, and <base>.dist (if source_file is known).

Recommendations for engine authors
- Do not open any path from your engine (on_success is metadata/logging only).
- If you expose an output directory field in your engine tab, make it discoverable by ACASL’s heuristic by setting a clear objectName/accessibleName:
  ```python
  out_edit.setObjectName("my_engine_output_dir")
  # or ensure the attribute name includes both tokens, e.g. _output_dir_input
  ```
- Optionally write a manifest (e.g., manifest.json) under the workspace that lists output_dir or produced artifacts. ACASL will also consider parent folders of artifacts.
- Do not rely on engine-specific wiring in ACASL; the discovery is generic and plug-and-play.

---

## 7) Auto‑plugins mapping (plug‑and‑play) {#7-auto-plugins-mapping-plug-and-play}

Concept
- Engines may ship mapping.json to declare automatic flags/plugins based on detected packages (requirements/imports).
- Lookup priority: engine package (embedded) > ENGINES/<engine_id>/mapping.json > PYCOMPILER_MAPPING env path (merged, lowest priority).
- Builders: an engine can provide an auto‑arguments builder at <engine_id>.auto_plugins with an AUTO_BUILDER(matched, pkg_to_import) -> list[str]. If none is provided, a generic builder is used.

Authoring mapping.json
- Values can be one of:
  - string (engine‑specific semantics)
  - list of strings
  - object with {"args": list[str]|str} or {"flags": list[str]|str}
  - boolean True (engine‑specific meaning; for PyInstaller it commonly means ["--collect-all", import_name])

Tokenization rules (important)
- Provide arguments as separate tokens whenever possible, e.g. ["--flag", "value"].
- PyInstaller engine: string values containing spaces are split safely (shlex). For example, "--collect-all {import_name}" becomes ["--collect-all", "PySide6"].
- Generic/default builder for other engines does NOT split strings with spaces; use lists to avoid passing a combined token.

Examples (PyInstaller)
```jsonc
{
  "PySide6": {"pyinstaller": true},             // emits ["--collect-all", "PySide6"]
  "numpy":   {"pyinstaller": "--collect-all {import_name}"},
  "pandas":  {"pyinstaller": ["--collect-all", "{import_name}"]}
}
```

Integration
- The host orchestrator calls utils.auto_plugins.compute_for_all(self) and merges engine‑specific args into your command.
- For PyInstaller, args are de‑duplicated while preserving order; repeated "--collect-all X" will be emitted once per package.

6.1) Engine-provided auto builder example (correct import)

```
<project root>
└── ENGINES/
    └── my_engine/
        ├── __init__.py
        ├── auto_plugins.py
        └── mapping.json
```

mapping.json (example)
```jsonc
{
  "__aliases__": {
    "import_to_package": { "cv2": "opencv-python" },
    "package_to_import_name": { "Pillow": "PIL" }
  },
  "numpy":   { "my_engine": "--enable-numpy {import_name}" },
  "Pillow":  { "my_engine": ["--include", "{import_name}"] }
}
```

auto_plugins.py (use the top-level import)
```python
from __future__ import annotations
from typing import Dict, List
from engine_sdk import register_auto_builder  # correct import

# Builder signature: (matched: dict, pkg_to_import: dict) -> list[str]
def AUTO_BUILDER(matched: Dict[str, Dict[str, object]], pkg_to_import: Dict[str, str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for pkg, entry in matched.items():
        if not isinstance(entry, dict):
            continue
        val = entry.get("my_engine")
        if not val:
            continue
        imp = pkg_to_import.get(pkg, pkg)
        args: List[str] = []
        if isinstance(val, str):
            # Tokenize conservatively for this engine
            args.extend(str(val).replace("{import_name}", imp).split())
        elif isinstance(val, list):
            for x in val:
                args.extend(str(x).replace("{import_name}", imp).split())
        elif isinstance(val, dict):
            a = val.get("args") or val.get("flags")
            if isinstance(a, str):
                args.extend(str(a).replace("{import_name}", imp).split())
            elif isinstance(a, list):
                for x in a:
                    args.extend(str(x).replace("{import_name}", imp).split())
        for a in args:
            if a not in seen:
                out.append(a)
                seen.add(a)
    return out

# Register at import time via the SDK facade
try:
    register_auto_builder("my_engine", AUTO_BUILDER)
except Exception:
    pass
```

Notes
- Import path is from engine_sdk import register_auto_builder (not engine_sdk.auto_plugins).
- Choose your tokenization strategy per engine; pass each CLI flag/value as a separate token to avoid parsing issues.
- For PyInstaller engines, see ENGINES/pyinstaller/auto_plugins.py for a reference that safely splits strings with spaces.

---

## 8) CI considerations and non‑interactive setups {#8-ci-considerations-and-non-interactive-setups}
- Keep engines non‑interactive; always pass flags to external tools rather than prompting.
- Respect timeouts; surface stderr/stdout to logs.
- Resolve executables deterministically (prefer venv‑local tools when applicable).
- Avoid UI‑thread blocking work; rely on run_process or the host’s QProcess pipeline.

---

## 9) Developer checklist and anti‑patterns {#9-developer-checklist-and-anti-patterns}

Checklist
- [ ] Package under ENGINES/<engine_id>/ with __init__.py
- [ ] registry.register(MyEngine) on import
- [ ] create_tab returns (widget, label) if UI controls are needed
- [ ] Resolve commands via resolve_executable/resolve_executable_path
- [ ] Validate argv with validate_args; each CLI token separate
- [ ] Non‑blocking runs with timeouts; log stderr
- [ ] Engine‑owned venv/tool flows (heuristic → async confirm → async install)
- [ ] mapping.json kept minimal and tokenized per rules above

Anti‑patterns
- Blocking the UI thread
- Hardcoded absolute paths
- Interactive tools without non‑interactive flags
- Passing combined strings as single argv tokens (e.g., "--flag value"). Always split into ["--flag", "value"].
- Driving venv/tool management from the UI layer; engines must own it.
- Opening output directories from engines; ACASL exclusively handles folder opening after post-compile.

---

## 10) Troubleshooting (decision tree) {#10-troubleshooting-decision-tree}
- Engine not visible
  - Ensure ENGINES/<engine_id>/ exists with __init__.py
  - Ensure registry.register(MyEngine) executes at import
  - Check application logs for registry/discovery messages
- Engine tab not bound
  - If using create_tab, ensure you return (QWidget, "Label")
  - Verify engines_loader tab mapping
- Command not found
  - Check PATH; prefer resolve_executable/resolve_executable_path
  - If using venv, resolve tool binary from venv/bin (Linux/macOS) or venv/Scripts (Windows)
- Process hangs or times out
  - Lower timeout; make tool non‑interactive; inspect stderr/stdout
- Auto‑plugins arguments not applied
  - Confirm mapping.json location/priority
  - For generic engines, ensure tokenization is per‑item in lists (strings with spaces are not split)
  - For PyInstaller, strings with spaces are split (shlex) and de‑duplicated per option+value
- Arguments misparsed (e.g., "Script file '--collect-all X' does not exist")
  - You passed a single combined token that includes a space
  - Fix: pass tokens separately ["--collect-all", "X"], or rely on the PyInstaller builder which splits appropriately
- Tool not installed in venv
  - Follow the preflight pattern: heuristic → async check → async install; return False while async ops run

## 11) Localizing your engine (languages/) {#11-localizing-your-engine-languages}

Purpose
- Ship your engine with its own translations so the final application has a languages folder out of the box (no user setup).
- Keep examples English-only in code; JSON files carry the translations.

Folder layout
```
<project root>
└── ENGINES/
    └── my_engine/
        ├── __init__.py
        ├── engine.py
        └── languages/
            ├── en.json
            ├── fr.json
            ├── es.json
            ├── de.json
            ├── ko.json
            ├── ja.json
            └── zh-CN.json
```

Minimal en.json (example)
```json
{
  "_meta": {"code": "en", "name": "English"},
  "engine_title": "MyEngine Options",
  "output_dir_ph": "Output directory (--output-dir)",
  "browse": "Browse…",
  "gui_windows": "GUI application (no console) [Windows]",
  "include_encodings": "Include encodings",
  "icon": "Icon",
  "packages_title": "Packages to include",
  "add": "Add",
  "remove": "Remove",
  "modules_title": "Modules to include",
  "data_title": "Data files/directories to include",
  "optimize": "Optimize"
}
```

Additional languages follow the same shape; only values change. Keep keys stable across languages.

Applying engine-local i18n at runtime (synchronized with app language) — see section 11.1 for the recommended template
Engines must load their own JSON from ENGINES/<engine_id>/languages at runtime and synchronize with the application language code (tr._meta.code). Use robust normalization (map variants like fr-FR → fr, pt_BR → pt-BR, zh → zh-CN) and fallbacks (base code, then 'en'). Do not bundle these files into the final application build; they localize the editor UI only.

Wiring
- The host calls registry.apply_translations(gui, tr) after language changes.
- Implement apply_i18n(gui, tr) in your engine. Read tr._meta.code to synchronize with the app language, normalize variants, then load your packaged languages and update titles/buttons/tooltips accordingly.

Using labels in the tab (English-first)
- Prefer passing English strings to Qt widgets. The host UI may wrap texts with a translator (gui.tr) when appropriate.
- Example:
```python
from PySide6.QtWidgets import QLabel
lbl = QLabel("MyEngine Options")
```
- If you want to wire dynamic texts via JSON, keep the key naming consistent and map values before you create widgets.

Best practices
- Always include en.json as a complete fallback (_meta.code/name present).
- Keep your keys engine-scoped (prefix like engine_/my_engine_*) to avoid collisions.
- Do not block the UI to load translations; either use built-in gui translations or pre-render English and let the host refresh if needed.
- Validate files are UTF‑8 (BOMless). Keep values short, avoid trailing spaces.

Examples
- Example A — English-only engine: Ship only ENGINES/my_engine/languages/en.json. The app runs fully in English.
- Example B — Multilingual engine: Add fr/es/de/ko/ja/zh-CN/ru.json with the same keys. The app picks the selected/system language when available; otherwise falls back to English.
- Example C — Headless builds: Engine-local i18n targets only the editor UI; no changes are required for built applications.

Troubleshooting
- “My engine tab does not change language”
  - Ensure your engine implements apply_i18n(gui, tr) and that registry.apply_translations(gui, tr) is called by the host (already wired in this project).
  - Verify ENGINES/<id>/languages/<code>.json exists and contains the expected keys; confirm fallback to en.json works.
- “Locale variant not matched (e.g., fr-FR, pt_BR)”
  - Normalize codes: map variants to base (fr-FR → fr) or canonical (pt_BR → pt-BR, zh → zh-CN) and try candidates in order [mapped, base, lower, raw, "en"].
- “Wrong language at runtime”
  - Confirm the app’s language selector/system language matches a file code in languages/*.json.
  - Verify _meta.code in your JSON matches the filename (e.g., fr.json → "fr").

## 11.1) Recommended i18n implementation template (synchronized with app) {#111-recommended-i18n-implementation-template-synchronized-with-app}

Goal
- Provide a ready-to-use apply_i18n implementation that:
  - Uses the app’s current language (tr._meta.code) when available
  - Normalizes locale variants (fr-FR → fr, pt_BR → pt-BR, zh → zh-CN)
  - Loads engine-local JSON from ENGINES/<id>/languages with robust fallbacks
  - Falls back to gui.tr("Fr", "En") when a JSON key is missing, so the engine still updates on language changes
  - Avoids blocking the UI (no network I/O) and avoids reloading translations on theme changes

JSON files
- Place engine-local JSON files in ENGINES/<engine_id>/languages/
- Always include en.json with a complete set of keys
- Example minimal en.json:
```json
{
  "_meta": {"code": "en", "name": "English"},
  "engine_title": "MyEngine Options",
  "output_dir_ph": "Output directory (--output-dir)",
  "browse": "Browse…",
  "gui_windows": "GUI application (no console) [Windows]",
  "include_encodings": "Include encodings",
  "icon": "Icon",
  "packages_title": "Packages to include",
  "add": "Add",
  "remove": "Remove",
  "modules_title": "Modules to include",
  "data_title": "Data files/directories to include",
  "optimize": "Optimize"
}
```

Engine code — apply_i18n template
```python
# Inside your engine class (engine.py)
import os, json, importlib.resources as ilr
from typing import Optional, Dict

def apply_i18n(self, gui, tr: Dict[str, str]) -> None:
    """Apply engine-local i18n from ENGINES/<id>/languages/*.json.
    Synchronize with app language; robust fallbacks to gui.tr when keys are missing.
    """
    try:
        # 1) Resolve effective language code from app translations or GUI prefs
        code = None
        try:
            meta = tr.get('_meta', {}) if isinstance(tr, dict) else {}
            code = meta.get('code') if isinstance(meta, dict) else None
        except Exception:
            code = None
        if not code:
            try:
                pref = getattr(gui, 'language_pref', getattr(gui, 'language', 'System'))
                if isinstance(pref, str) and pref != 'System':
                    code = pref
            except Exception:
                pass
        code = code or 'en'

        # 2) Normalize variants and build fallback candidates
        raw = str(code)
        low = raw.lower().replace('_', '-')
        aliases = {
            'en-us': 'en', 'en_gb': 'en', 'en-uk': 'en',
            'fr-fr': 'fr', 'fr_ca': 'fr', 'fr-ca': 'fr',
            'pt-br': 'pt-BR', 'pt_br': 'pt-BR',
            'zh': 'zh-CN', 'zh_cn': 'zh-CN', 'zh-cn': 'zh-CN'
        }
        mapped = aliases.get(low, raw)
        cands = []
        if mapped not in cands: cands.append(mapped)
        base = None
        try:
            if '-' in mapped: base = mapped.split('-', 1)[0]
            elif '_' in mapped: base = mapped.split('_', 1)[0]
        except Exception:
            base = None
        if base and base not in cands: cands.append(base)
        if low not in cands: cands.append(low)
        if raw not in cands: cands.append(raw)
        if 'en' not in cands: cands.append('en')

        # 3) Load first available engine-local language JSON
        data = {}
        try:
            pkg = __package__  # e.g., 'ENGINES.my_engine'
            def _try(c: str) -> bool:
                try:
                    with ilr.as_file(ilr.files(pkg).joinpath('languages', f'{c}.json')) as p:
                        if os.path.isfile(str(p)):
                            with open(str(p), 'r', encoding='utf-8') as f:
                                d = json.load(f) or {}
                            nonlocal data
                            data = d if isinstance(d, dict) else {}
                            return isinstance(data, dict)
                except Exception:
                    pass
                return False
            for cand in cands:
                if _try(cand):
                    break
        except Exception:
            data = {}

        # 4) Helper: engine-local value with robust fallback to gui.tr
        def g(key: str, fr: Optional[str] = None, en: Optional[str] = None) -> Optional[str]:
            try:
                v = data.get(key)
                if isinstance(v, str) and v.strip():
                    return v
            except Exception:
                pass
            if fr is not None and en is not None:
                try:
                    return gui.tr(fr, en)
                except Exception:
                    return en
            return None

        # 5) Apply texts/tooltips/placeholders on engine widgets
        if getattr(self, '_title_label', None):
            self._title_label.setText(g('engine_title', 'MyEngine Options', 'MyEngine Options'))
        if getattr(self, '_output_dir_input', None):
            ph = g('output_dir_ph', 'Output directory (--output-dir)', 'Output directory (--output-dir)')
            if ph:
                try: self._output_dir_input.setPlaceholderText(ph)
                except Exception: pass
        if getattr(self, '_browse_btn', None):
            self._browse_btn.setText(g('browse', 'Browse…', 'Browse…') or 'Browse…')
        if getattr(self, '_cb_gui', None):
            self._cb_gui.setText(g('gui_windows', 'GUI application (no console) [Windows]', 'GUI application (no console) [Windows]') or 'GUI application (no console) [Windows]')
        if getattr(self, '_cb_enc', None):
            self._cb_enc.setText(g('include_encodings', 'Include encodings', 'Include encodings') or 'Include encodings')
        if getattr(self, '_icon_title', None):
            self._icon_title.setText(g('icon', 'Icon', 'Icon') or 'Icon')
        if getattr(self, '_packages_title', None):
            self._packages_title.setText(g('packages_title', 'Packages to include', 'Packages to include') or 'Packages to include')
        if getattr(self, '_pkg_add_btn', None):
            self._pkg_add_btn.setText(g('add', 'Add', 'Add') or 'Add')
        if getattr(self, '_pkg_rm_btn', None):
            self._pkg_rm_btn.setText(g('remove', 'Remove', 'Remove') or 'Remove')
        if getattr(self, '_modules_title', None):
            self._modules_title.setText(g('modules_title', 'Modules to include', 'Modules to include') or 'Modules to include')
        if getattr(self, '_mod_add_btn', None):
            self._mod_add_btn.setText(g('add', 'Add', 'Add') or 'Add')
        if getattr(self, '_mod_rm_btn', None):
            self._mod_rm_btn.setText(g('remove', 'Remove', 'Remove') or 'Remove')
        if getattr(self, '_data_title', None):
            self._data_title.setText(g('data_title', 'Data files/directories to include', 'Data files/directories to include') or 'Data files/directories to include')
        if getattr(self, '_data_add_file_btn', None):
            self._data_add_file_btn.setText(g('add_file', 'Add file', 'Add file') or 'Add file')
        if getattr(self, '_data_add_dir_btn', None):
            self._data_add_dir_btn.setText(g('add_directory', 'Add directory', 'Add directory') or 'Add directory')
        if getattr(self, '_data_rm_btn', None):
            self._data_rm_btn.setText(g('remove', 'Remove', 'Remove') or 'Remove')
        if getattr(self, '_optimize_title', None):
            self._optimize_title.setText(g('optimize', 'Optimize', 'Optimize') or 'Optimize')
    except Exception:
        # Never raise from i18n; keep UI responsive
        pass
```

Engine code — where to call apply_i18n
- In create_tab, after creating your widgets, call apply_i18n using the app’s active translations when available:
```python
# At the end of create_tab(self, gui):
try:
    # Use active app translations if present; fall back to empty dict
    self.apply_i18n(gui, getattr(gui, '_tr', {}) or {})
except Exception:
    pass
return tab, gui.tr("MyEngine", "MyEngine")
```

Host wiring (already provided by the app)
- The host calls registry.apply_translations(gui, tr) after any app language change; your apply_i18n is invoked with the app’s translations.
- On tab creation, the host immediately applies the current translations to the engine if available, so the tab opens in the right language.
- Do not reload i18n inside theme updates; reuse the active translation (the app stores it on gui._tr).

Troubleshooting (i18n)
- Tab does not change language: ensure your engine implements apply_i18n(gui, tr) and that it uses tr._meta.code to sync language; verify registry.apply_translations is being called (host does this automatically).
- Missing keys in your JSON: add robust fallbacks to gui.tr("Fr", "En") as in the template above so your UI still updates in the app language.
- Locale variants not picked: ensure your normalization map includes common aliases and try candidates in order [mapped, base, lower, raw, "en"].

## 12) Adapter engine (external CLI) — complete example {#12-adapter-engine-external-cli--complete-example}

Purpose
- Wrap an external CLI binary (any language) with a Python engine package that integrates perfectly with the host UI and lifecycle.
- Keep the UI non‑blocking, arguments safe, and outputs deterministic.

Folder layout
```
<project root>
└── ENGINES/
    └── ext_cli/
        ├── __init__.py
        ├── engine.py
        ├── mapping.json        # optional: auto-plugins mapping
        └── auto_plugins.py     # optional: custom builder
```

Expected CLI contract
- Non‑interactive mode (no prompts): all behavior controlled via flags/config file
- Stable version output: "ext-cli --version" → "ext-cli 1.4.2"
- Optional capabilities: "ext-cli --capabilities --json" → parseable JSON
- Deterministic outputs: produces a known output directory and/or a manifest JSON listing artifacts
- Clear exit codes and stderr

Engine implementation (complete)
```python
from __future__ import annotations
import os, platform, json
from typing import List, Tuple, Optional, Dict

from engine_sdk import CompilerEngine, registry
from engine_sdk.utils import (
    resolve_executable,
    validate_args,
    build_env,
    run_process,
)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton, QFileDialog
)


class ExtCliEngine(CompilerEngine):
    id = "ext_cli"
    name = "External CLI"

    # Internal state bound to UI controls
    _enable_gui = False
    _optimize = False
    _cli_path: Optional[str] = None   # optional override

    def create_tab(self, gui):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("External CLI Options"))

        # GUI toggle (Windows-only example)
        row1 = QHBoxLayout()
        cb_gui = QCheckBox("GUI application (no console) [Windows]")
        if platform.system() != "Windows":
            cb_gui.setEnabled(False)
            cb_gui.setToolTip("Available on Windows only")
        cb_gui.stateChanged.connect(lambda s: setattr(self, "_enable_gui", bool(s)))
        row1.addWidget(cb_gui)
        row1.addStretch(1)
        lay.addLayout(row1)

        # Optimize
        row2 = QHBoxLayout()
        cb_opt = QCheckBox("Optimize")
        cb_opt.stateChanged.connect(lambda s: setattr(self, "_optimize", bool(s)))
        row2.addWidget(cb_opt)
        row2.addStretch(1)
        lay.addLayout(row2)

        # Output directory (discoverable by ACASL heuristic)
        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Output directory"))
        ed_out = QLineEdit()
        ed_out.setObjectName("ext_cli_output_dir")
        btn_out = QPushButton("Browse…")
        def _browse_out():
            p = QFileDialog.getExistingDirectory(w, "Select output directory", "")
            if p:
                ed_out.setText(p)
        btn_out.clicked.connect(_browse_out)
        row_out.addWidget(ed_out)
        row_out.addWidget(btn_out)
        lay.addLayout(row_out)
        # keep a reference (optional)
        self._ext_out_widget = ed_out

        # Optional CLI path override
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("CLI path (optional)"))
        ed_cli = QLineEdit()
        btn_cli = QPushButton("Browse…")
        def _browse_cli():
            p, _ = QFileDialog.getOpenFileName(w, "Select CLI executable", "")
            if p:
                ed_cli.setText(p)
                setattr(self, "_cli_path", p)
        btn_cli.clicked.connect(_browse_cli)
        row3.addWidget(ed_cli)
        row3.addWidget(btn_cli)
        lay.addLayout(row3)

        return w, "Ext CLI"

    def preflight(self, gui, file: str) -> bool:
        # Resolve executable either from override, env, or PATH
        prog = None
        try:
            if self._cli_path and os.path.isfile(self._cli_path):
                prog = self._cli_path
            else:
                # Allow ENV override EXT_CLI_PATH, fallback to PATH
                prog = os.environ.get("EXT_CLI_PATH") or resolve_executable("ext-cli")
        except Exception:
            prog = None

        if not prog:
            try: gui.log.append("❌ ext-cli not found. Set EXT_CLI_PATH or install it in PATH.")
            except Exception: pass
            return False

        # Check version quickly, non-blocking style using run_process with timeout
        try:
            code, out, err = run_process(gui, prog, ["--version"], timeout_ms=5000)
            if code != 0:
                try: gui.log.append(f"⚠️ ext-cli --version failed: {err.strip() or out.strip()}")
                except Exception: pass
                # Let it proceed; user may still try to run
            else:
                try: gui.log.append(f"✅ ext-cli detected: {out.strip()}")
                except Exception: pass
        except Exception:
            pass
        return True

    def build_command(self, gui, file: str) -> List[str]:
        # Build the nominal argv (used for preview); auto-args merged in program_and_args
        argv: List[str] = [file]
        if self._optimize:
            argv += ["--optimize"]
        if self._enable_gui and platform.system() == "Windows":
            argv += ["--windows-gui"]
        return ["ext-cli"] + argv

    def program_and_args(self, gui, file: str) -> Optional[Tuple[str, List[str]]]:
        # Resolve program
        prog = self._cli_path or os.environ.get("EXT_CLI_PATH") or resolve_executable("ext-cli")
        if not prog:
            try: gui.log.append("❌ ext-cli not found. Cannot start.")
            except Exception: pass
            return None

        # Base args from UI
        args: List[str] = []
        if self._optimize:
            args += ["--optimize"]
        if self._enable_gui and platform.system() == "Windows":
            args += ["--windows-gui"]
        # Optional output dir argument (discoverable by ACASL)
        try:
            ed_out = getattr(self, '_ext_out_widget', None)
            if ed_out:
                ov = ed_out.text().strip()
                if ov:
                    args += ["--output-dir", ov]
        except Exception:
            pass
        args += [file]

        # Merge engine auto-plugins mapping (optional)
        auto_args: List[str] = []
        try:
            from engine_sdk import auto_plugins as ap  # facade to host auto-plugins
            auto_args = ap.compute_auto_for_engine(gui, self.id) or []
        except Exception:
            auto_args = []

        final = validate_args(args + auto_args)
        return prog, final

    def environment(self, gui, file: str) -> Optional[Dict[str, str]]:
        # Minimal deterministic environment; add any CLI-specific vars here
        env = build_env(extra={})
        return env

    def get_timeout_seconds(self, gui) -> int:
        # Upper bound for long runs (e.g., 30 minutes); adjust or make it configurable
        return 1800

    def on_success(self, gui, file: str) -> None:
        # ACASL-only policy: engines must not open output directories. Use this hook only for lightweight metadata/logging if needed.
        try:
            base = getattr(gui, 'workspace_dir', None) or os.getcwd()
            # Optionally: write/update a manifest.json describing outputs for tooling; do not open UI or paths here.
            # Example (commented):
            # manifest_path = os.path.join(base, "manifest.json")
            # with open(manifest_path, "w", encoding="utf-8") as f:
            #     json.dump({"output_dir": os.path.join(base, "build")}, f)
            return
        except Exception:
            pass

# Register on import
try:
    registry.register(ExtCliEngine)
except Exception:
    pass
```

mapping.json (optional)
```jsonc
{
  "__aliases__": {
    "import_to_package": { "cv2": "opencv-python" },
    "package_to_import_name": { "Pillow": "PIL" }
  },
  "numpy":   { "ext_cli": ["--enable", "numpy"] },
  "Pillow":  { "ext_cli": ["--include", "{import_name}"] },
  "PySide6": { "ext_cli": ["--ui", "qt"] }
}
```

Key points
- Non‑interactive: all CLI behavior is controlled via flags.
- Deterministic: resolve_executable, validate_args, and build_env ensure safety and repeatability.
- Non‑blocking: version checks and runs use run_process/host QProcess with timeouts; the UI stays responsive.
- OS‑aware UI: Windows‑only options are disabled on other OSes.
- Auto‑mapping: optional, merges import‑based flags so users configure less.
- Manifest-aware: produce or update a manifest to guide UX; ACASL will open the output directory after post-compile.

Tests (suggested)
- Unit: program_and_args tokenization and OS‑specific flags
- Integration: preflight with missing CLI (return False, log message)
- E2E (CI): run with a sample project using a mock ext-cli that prints a manifest.json

## 13) Linux-first adapter example {#13-linux-first-adapter-example}

Context
- This section shows a Linux-focused engine adapter that pilots an external CLI with Linux‑aware defaults (headless detection, parallel jobs, locale, LD_LIBRARY_PATH hints).
- It keeps the UI non‑blocking and uses only Engine SDK facilities.

Engine implementation (Linux‑first)
```python
from __future__ import annotations
import os, sys, json
from typing import List, Tuple, Optional, Dict

from engine_sdk import CompilerEngine, registry
from engine_sdk.utils import resolve_executable, validate_args, build_env, run_process
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton
)


class ExtCliLinuxEngine(CompilerEngine):
    id = "ext_cli_linux"
    name = "External CLI (Linux)"

    _headless = False
    _jobs: int = max(1, (os.cpu_count() or 1))
    _use_system = True
    _ld_extra: str = ""
    _cli_path: Optional[str] = None

    def create_tab(self, gui):
        if not sys.platform.startswith("linux"):
            # Do not render a tab on non-Linux; the engine can also be hidden by the registry mapping.
            return None
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("External CLI (Linux) Options"))

        # Headless mode (auto-enabled if no DISPLAY/WAYLAND)
        row1 = QHBoxLayout()
        cb_head = QCheckBox("Headless mode (add --headless if no DISPLAY)")
        # Pre-detect headless
        try:
            auto_headless = (not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"))
        except Exception:
            auto_headless = False
        cb_head.setChecked(auto_headless)
        self._headless = auto_headless
        cb_head.stateChanged.connect(lambda s: setattr(self, "_headless", bool(s)))
        row1.addWidget(cb_head)
        row1.addStretch(1)
        lay.addLayout(row1)

        # Parallel jobs
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Parallel jobs"))
        ed_jobs = QLineEdit(str(self._jobs))
        def _set_jobs():
            try:
                v = int(ed_jobs.text().strip())
                self._jobs = v if v > 0 else 1
            except Exception:
                self._jobs = 1
        ed_jobs.editingFinished.connect(_set_jobs)
        row2.addWidget(ed_jobs)
        row2.addStretch(1)
        lay.addLayout(row2)

        # Use system toolchain
        row3 = QHBoxLayout()
        cb_sys = QCheckBox("Use system toolchain (add --use-system)")
        cb_sys.setChecked(True)
        cb_sys.stateChanged.connect(lambda s: setattr(self, "_use_system", bool(s)))
        row3.addWidget(cb_sys)
        row3.addStretch(1)
        lay.addLayout(row3)

        # Extra LD_LIBRARY_PATH hints
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Extra LD_LIBRARY_PATH (colon-separated)"))
        ed_ld = QLineEdit()
        def _set_ld():
            setattr(self, "_ld_extra", ed_ld.text().strip())
        ed_ld.editingFinished.connect(_set_ld)
        row4.addWidget(ed_ld)
        row4.addStretch(1)
        lay.addLayout(row4)

        # Output directory (discoverable by ACASL heuristic)
        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Output directory"))
        ed_out = QLineEdit()
        ed_out.setObjectName("ext_cli_linux_output_dir")
        btn_out = QPushButton("Browse…")
        def _browse_out():
            from PySide6.QtWidgets import QFileDialog
            p = QFileDialog.getExistingDirectory(w, "Select output directory", "")
            if p:
                ed_out.setText(p)
        btn_out.clicked.connect(_browse_out)
        row_out.addWidget(ed_out)
        row_out.addWidget(btn_out)
        lay.addLayout(row_out)
        self._linux_out_widget = ed_out

        # Optional CLI path override
        row5 = QHBoxLayout()
        row5.addWidget(QLabel("CLI path (optional)"))
        ed_cli = QLineEdit()
        btn_cli = QPushButton("Browse…")
        def _browse_cli():
            from PySide6.QtWidgets import QFileDialog
            p, _ = QFileDialog.getOpenFileName(w, "Select CLI executable", "")
            if p:
                ed_cli.setText(p)
                setattr(self, "_cli_path", p)
        btn_cli.clicked.connect(_browse_cli)
        row5.addWidget(ed_cli)
        row5.addWidget(btn_cli)
        lay.addLayout(row5)

        return w, "Ext CLI (Linux)"

    def preflight(self, gui, file: str) -> bool:
        if not sys.platform.startswith("linux"):
            try: gui.log.append("ℹ️ ext-cli-linux is Linux-only.")
            except Exception: pass
            return False
        prog = self._cli_path or os.environ.get("EXT_CLI_PATH") or resolve_executable("ext-cli")
        if not prog:
            try: gui.log.append("❌ ext-cli not found in PATH. Set EXT_CLI_PATH or install it.")
            except Exception: pass
            return False
        # Quick version check with timeout (non-blocking)
        try:
            code, out, err = run_process(gui, prog, ["--version"], timeout_ms=4000)
            if code == 0:
                try: gui.log.append(f"✅ ext-cli detected: {out.strip()}")
                except Exception: pass
        except Exception:
            pass
        return True

    def build_command(self, gui, file: str) -> List[str]:
        argv: List[str] = []
        if self._headless or (not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")):
            argv += ["--headless"]
        if self._use_system:
            argv += ["--use-system"]
        if (self._jobs or 0) > 1:
            argv += ["--jobs", str(int(self._jobs))]
        argv += [file]
        return ["ext-cli"] + argv

    def program_and_args(self, gui, file: str) -> Optional[Tuple[str, List[str]]]:
        prog = self._cli_path or os.environ.get("EXT_CLI_PATH") or resolve_executable("ext-cli")
        if not prog:
            return None
        base: List[str] = []
        if self._headless or (not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")):
            base += ["--headless"]
        if self._use_system:
            base += ["--use-system"]
        if (self._jobs or 0) > 1:
            base += ["--jobs", str(int(self._jobs))]
        # Optional output dir argument (discoverable by ACASL)
        try:
            ed_out = getattr(self, '_linux_out_widget', None)
            if ed_out:
                ov = ed_out.text().strip()
                if ov:
                    base += ["--output-dir", ov]
        except Exception:
            pass
        base += [file]
        # Auto-plugins merge (optional)
        try:
            from engine_sdk import auto_plugins as ap
            auto_args = ap.compute_auto_for_engine(gui, self.id) or []
        except Exception:
            auto_args = []
        final = validate_args(base + auto_args)
        return prog, final

    def environment(self, gui, file: str) -> Optional[Dict[str, str]]:
        extra: Dict[str, str] = {"LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}
        # Inject extra LD_LIBRARY_PATH if provided
        if self._ld_extra:
            cur = os.environ.get("LD_LIBRARY_PATH", "")
            extra["LD_LIBRARY_PATH"] = f"{self._ld_extra}:{cur}" if cur else self._ld_extra
        return build_env(extra=extra)

    def get_timeout_seconds(self, gui) -> int:
        return 1800

    def on_success(self, gui, file: str) -> None:
        # ACASL-only policy: do not open output directories here. Reserve this hook for optional metadata/logging.
        try:
            base = getattr(gui, 'workspace_dir', None) or os.getcwd()
            # Optionally update a manifest.json or emit lightweight logs; no UI actions.
            return
        except Exception:
            pass

try:
    registry.register(ExtCliLinuxEngine)
except Exception:
    pass
```

Notes for Linux
- Headless detection: if DISPLAY and WAYLAND_DISPLAY are absent, the engine adds --headless (when supported by the CLI).
- Parallelism: defaults to os.cpu_count(); users can override.
- Toolchain: use-system flag illustrates selecting distro packages over vendored toolchains.
- Environment: enforce UTF‑8 locale and allow augmenting LD_LIBRARY_PATH when needed.
- Signals/timeouts: the host will kill the process tree on timeout; ensure your CLI exits cleanly on SIGTERM/SIGKILL.
- No shell: arguments are tokenized and validated (validate_args) — no shell expansion or injection.

Happy hacking!
