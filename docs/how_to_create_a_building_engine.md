# How to Create a Building Engine

## Quick Navigation
- [TL;DR](#0-tldr-copy-paste-template)
- [Layout & discovery](#1-folder-layout-and-discovery)
- [Minimal engine](#2-minimal-engine-implementation)
- [UI tab](#3-ui-tab-create_tab-example)
- [Lifecycle](#4-full-engine-shape-and-lifecycle-hooks)
- [Venv/Tools](#5-engine-owned-venvtool-management-async-non-blocking)
- [Environment/Process](#6-environment-and-process-execution)
- [Auto-plugins](#7-auto-plugins-mapping-plug-and-play)
- [i18n](#8-internationalization-i18n)
- [Checklist](#9-developer-checklist-and-anti-patterns)
- [Troubleshooting](#10-troubleshooting-decision-tree)

This guide explains how to implement a pluggable compilation engine for PyCompiler ARK++ 3.2.3 using the Engine SDK.

## Key Highlights

- **Package Structure**: Engines are Python packages under `ENGINES/<engine_id>/` (directory with `__init__.py`)
- **Self-Registration**: Engines must self‑register on import via the central registry: `registry.register(MyEngine)`
- **Discovery**: `engines_loader` discovers engines strictly from the `ENGINES/` directory
- **SDK Integration**: Import the SDK and registry from `engine_sdk` for all core functionality
- **Async Tool Management**: Venv/tool management is engine‑owned and must be non‑blocking (asynchronous patterns)
- **Output Handling**: Output directory opening is handled exclusively by ACASL; engines must not open paths or invoke the OS file browser

---

## 0) TL;DR (copy‑paste template) {#0-tldr-copy-paste-template}
```python
from engine_sdk import CompilerEngine, registry
from engine_sdk.utils import (
    resolve_executable,
    validate_args,
    normalized_program_and_args,
)
import os
from typing import Optional

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

    def get_output_directory(self, gui) -> Optional[str]:
        """Return the output directory for ACASL to open after successful build.
        ACASL-only method: engines define their output directory but never open it themselves.
        """
        try:
            # Try GUI output_dir_input field first
            w = getattr(gui, "output_dir_input", None)
            if w and hasattr(w, "text") and callable(w.text):
                v = str(w.text()).strip()
                if v:
                    return v
            # Fallback to workspace/dist
            ws = getattr(gui, "workspace_dir", None) or os.getcwd()
            return os.path.join(ws, "dist")
        except Exception:
            # Ultimate fallback
            return os.path.join(os.getcwd(), "dist")

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
- **get_output_directory(self, gui) -> Optional[str]** — **IMPORTANT**: return output directory for ACASL to open after successful build
- on_success(self, gui, file) -> None — optional hook for metadata/logging only; do NOT open output directories (ACASL owns opening and the host does not call this hook to open)

### The `get_output_directory` Method

This is a crucial method that enables ACASL to automatically open the correct output directory after a successful build. **Engines must never open directories themselves** - this is exclusively handled by ACASL.

```python
def get_output_directory(self, gui) -> Optional[str]:
    """Return the output directory for ACASL to open after successful build.
    ACASL-only method: engines define their output directory but never open it themselves.
    """
    try:
        # Priority 1: Engine-specific output field (if your engine has one)
        if hasattr(self, '_output_dir_input') and self._output_dir_input:
            v = self._output_dir_input.text().strip()
            if v:
                return v

        # Priority 2: Global GUI output_dir_input field
        w = getattr(gui, "output_dir_input", None)
        if w and hasattr(w, "text") and callable(w.text):
            v = str(w.text()).strip()
            if v:
                return v

        # Priority 3: Workspace/dist fallback
        ws = getattr(gui, "workspace_dir", None) or os.getcwd()
        return os.path.join(ws, "dist")
    except Exception:
        # Ultimate fallback
        return os.path.join(os.getcwd(), "dist")
```

**Key principles:**
- Return the actual output directory path where your engine produces files
- Use a priority system: engine-specific fields → global fields → sensible defaults
- Never return `None` unless absolutely no output directory can be determined
- Handle exceptions gracefully with fallbacks
- **Never open the directory yourself** - ACASL handles all directory opening

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

---

## 8) Internationalization (i18n) {#8-internationalization-i18n}

Engines can provide their own translations to support multiple languages in the PyCompiler ARK++ interface. This allows your engine's UI elements to be displayed in the user's preferred language.

### Folder Structure

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

### Translation Files

Each language file should follow this structure:

**en.json** (English - always required as fallback)
```json
{
  "_meta": {"code": "en", "name": "English"},
  "engine_title": "MyEngine Options",
  "output_dir": "Output directory",
  "browse": "Browse…",
  "onefile": "Create single file",
  "optimize": "Optimize",
  "icon": "Icon file",
  "add": "Add",
  "remove": "Remove"
}
```

**fr.json** (French example)
```json
{
  "_meta": {"code": "fr", "name": "Français"},
  "engine_title": "Options MyEngine",
  "output_dir": "Répertoire de sortie",
  "browse": "Parcourir…",
  "onefile": "Créer un fichier unique",
  "optimize": "Optimiser",
  "icon": "Fichier d'icône",
  "add": "Ajouter",
  "remove": "Supprimer"
}
```

### Implementation in Engine

Add the `apply_i18n` method to your engine class:

```python
from engine_sdk import CompilerEngine, registry
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton
import os
import json
import importlib.resources as ilr
from typing import Optional, Dict

class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"

    def create_tab(self, gui):
        w = QWidget()
        lay = QVBoxLayout(w)

        # Create UI elements and store references for i18n
        self._title_label = QLabel("MyEngine Options")
        self._onefile_cb = QCheckBox("Create single file")
        self._browse_btn = QPushButton("Browse…")

        lay.addWidget(self._title_label)
        lay.addWidget(self._onefile_cb)
        lay.addWidget(self._browse_btn)

        # Apply current translations
        try:
            self.apply_i18n(gui, getattr(gui, '_tr', {}) or {})
        except Exception:
            pass

        return w, "MyEngine"

    def apply_i18n(self, gui, tr: Dict[str, str]) -> None:
        """Apply engine-local i18n from ENGINES/<id>/languages/*.json.
        Synchronize with app language; robust fallbacks to gui.tr when keys are missing.
        """
        try:
            # 1) Get current language code from app translations
            code = 'en'  # default
            try:
                meta = tr.get('_meta', {}) if isinstance(tr, dict) else {}
                if isinstance(meta, dict) and 'code' in meta:
                    code = meta['code']
            except Exception:
                pass

            # 2) Normalize language variants
            code_variants = [code]
            if '-' in code:
                base = code.split('-')[0]
                if base not in code_variants:
                    code_variants.append(base)
            code_variants.append('en')  # Always fallback to English

            # 3) Load engine translations
            data = {}
            try:
                pkg = __package__  # e.g., 'ENGINES.my_engine'
                for variant in code_variants:
                    try:
                        with ilr.as_file(ilr.files(pkg).joinpath('languages', f'{variant}.json')) as p:
                            if os.path.isfile(str(p)):
                                with open(str(p), 'r', encoding='utf-8') as f:
                                    data = json.load(f) or {}
                                break
                    except Exception:
                        continue
            except Exception:
                pass

            # 4) Helper function to get translated text
            def get_text(key: str, fallback: str = "") -> str:
                return data.get(key, fallback) if isinstance(data, dict) else fallback

            # 5) Apply translations to UI elements
            if hasattr(self, '_title_label') and self._title_label:
                self._title_label.setText(get_text('engine_title', 'MyEngine Options'))

            if hasattr(self, '_onefile_cb') and self._onefile_cb:
                self._onefile_cb.setText(get_text('onefile', 'Create single file'))

            if hasattr(self, '_browse_btn') and self._browse_btn:
                self._browse_btn.setText(get_text('browse', 'Browse…'))

        except Exception:
            # Never raise from i18n; keep UI responsive
            pass

registry.register(MyEngine)
```

### Key Points

- **Always include `en.json`** as the fallback language
- **Use consistent keys** across all language files
- **Store widget references** in `create_tab` for later translation updates
- **Call `apply_i18n`** at the end of `create_tab` to apply initial translations
- **Handle exceptions gracefully** - i18n should never break the engine
- **Use UTF-8 encoding** for all JSON files
- **Keep translations concise** and appropriate for UI elements

### Language Codes

Use standard language codes:
- `en` - English
- `fr` - French
- `es` - Spanish
- `de` - German
- `ko` - Korean
- `ja` - Japanese
- `zh-CN` - Chinese (Simplified)
- `pt-BR` - Portuguese (Brazil)
- `ru` - Russian

### Host Integration

The host application will automatically call your `apply_i18n` method when:
- The user changes the application language
- Your engine tab is created
- The application starts up

You don't need to manually trigger language updates - the host handles this automatically.

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
- [ ] **get_output_directory implemented** to return the correct output path for ACASL
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

---

## Conclusion

This guide provides a comprehensive foundation for creating robust, production-ready compilation engines for PyCompiler ARK++ 3.2.3. The Engine SDK offers powerful abstractions while maintaining flexibility for custom implementations.

### Key Takeaways
- **Follow the patterns**: Use the provided templates and patterns for consistency
- **Prioritize user experience**: Keep operations non-blocking and provide clear feedback
- **Embrace modern Python**: Use type hints, async patterns, and proper error handling
- **Test thoroughly**: Validate your engine across platforms and edge cases
- **Document well**: Clear documentation helps both users and maintainers

### Getting Help
- Check existing engines in `ENGINES/` for real-world examples
- Review the Engine SDK source code for advanced patterns
- Test your engine with the provided test suite
- Follow the troubleshooting guide for common issues

### Contributing
When contributing engines to the project:
1. Follow the coding standards outlined in this guide
2. Include comprehensive tests
3. Provide complete documentation
4. Ensure cross-platform compatibility
5. Add internationalization support

Happy engine building! 🚀
