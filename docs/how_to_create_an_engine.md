# How to Create a Building Engine

## Quick Navigation
- [TL;DR](#0-tldr-copy-paste-template)
- [Layout & discovery](#1-folder-layout-and-discovery)
- [Minimal engine](#2-minimal-engine-implementation)
- [UI tab](#3-ui-tab-create_tab-example)
- [Lifecycle](#4-full-engine-shape-and-lifecycle-hooks)
- [Venv/Tools](#5-engine-owned-venvtool-management-async-non-blocking)
- [Environment/Process](#6-environment-and-process-execution)
- [i18n](#7-internationalization-i18n)
- [Checklist](#8-developer-checklist-and-anti-patterns)
- [Troubleshooting](#9-troubleshooting-decision-tree)

This guide explains how to implement a pluggable compilation engine for PyCompiler ARK++ using the Engine SDK.

## Key Highlights

- **Package Structure**: Engines are Python packages under `ENGINES/<engine_id>/` (directory with `__init__.py`)
- **Self-Registration**: Engines must self‑register on import via the central registry: `registry.register(MyEngine)`
- **Discovery**: `engines_loader` discovers engines strictly from the `ENGINES/` directory
- **SDK Integration**: Import the SDK and registry from `engine_sdk` for all core functionality
- **Async Tool Management**: Venv/tool management is engine‑owned and must be non‑blocking (asynchronous patterns)
- **Output Handling**: Engines define output directory via `get_output_directory()` but never open it themselves

---

## 0) TL;DR (copy‑paste template)

Create `ENGINES/my_engine/__init__.py`:

```python

from __future__ import annotations

import os
from typing import Optional

from engine_sdk import CompilerEngine, registry


class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"

    def preflight(self, gui, file: str) -> bool:
        """Quick validation before build."""
        return bool(file)

    def build_command(self, gui, file: str) -> list[str]:
        """Return full command: [program, arg1, arg2, ...]"""
        return ["pyinstaller", "--onefile", file]

    def get_output_directory(self, gui) -> Optional[str]:
        """Return output directory for ACASL to open after build."""
        try:
            w = getattr(gui, "output_dir_input", None)
            if w and hasattr(w, "text") and callable(w.text):
                v = str(w.text()).strip()
                if v:
                    return v
            ws = getattr(gui, "workspace_dir", None) or os.getcwd()
            return os.path.join(ws, "dist")
        except Exception:
            return os.path.join(os.getcwd(), "dist")


registry.register(MyEngine)
```

That's it! Your engine is now discoverable and ready to use.

---

## 1) Folder layout and discovery

```
<project root>
└── ENGINES/
    └── my_engine/
        └── __init__.py
```

- The package under `ENGINES/<engine_id>/` must contain `__init__.py`
- Engines must self‑register on import: `registry.register(MyEngine)`
- `engines_loader` discovers engines strictly from `ENGINES/`
- Engines are imported at application startup; registration happens automatically

---

## 2) Minimal engine implementation

```python
from __future__ import annotations

import os
from typing import Optional

from engine_sdk import CompilerEngine, registry


class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"

    def preflight(self, gui, file: str) -> bool:
        """Perform preflight checks. Return True if OK, False to abort."""
        if not file:
            try:
                gui.log.append("[ERROR] No input file")
            except Exception:
                pass
            return False
        return True

    def build_command(self, gui, file: str) -> list[str]:
        """Return the full command as a list: [program, arg1, arg2, ...]"""
        return ["pyinstaller", "--onefile", file]

    def get_output_directory(self, gui) -> Optional[str]:
        """Return output directory for ACASL to open after successful build."""
        try:
            ws = getattr(gui, "workspace_dir", None) or os.getcwd()
            return os.path.join(ws, "dist")
        except Exception:
            return os.path.join(os.getcwd(), "dist")


registry.register(MyEngine)
```

**Key points:**
- `build_command()` returns the full command as a list (program at index 0)
- `preflight()` validates before execution; return False to abort
- `get_output_directory()` tells ACASL where to open after build
- Always register the engine class at module level

---

## 3) UI tab (create_tab) example

```python
from __future__ import annotations

from engine_sdk import CompilerEngine, registry
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox


class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"
    _onefile = True

    def create_tab(self, gui):
        """Create and return (QWidget, label_str) for the engine tab."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("MyEngine Options"))
        
        cb = QCheckBox("Onefile")
        cb.setChecked(self._onefile)
        cb.stateChanged.connect(lambda s: setattr(self, "_onefile", bool(s)))
        lay.addWidget(cb)
        
        return w, "MyEngine"

    def build_command(self, gui, file: str) -> list[str]:
        """Build command based on UI state."""
        args = []
        if self._onefile:
            args.append("--onefile")
        args.append(file)
        return ["pyinstaller"] + args

    def get_output_directory(self, gui) -> Optional[str]:
        """Return output directory."""
        try:
            ws = getattr(gui, "workspace_dir", None) or os.getcwd()
            return os.path.join(ws, "dist")
        except Exception:
            return os.path.join(os.getcwd(), "dist")


registry.register(MyEngine)
```

**Key points:**
- `create_tab()` returns `(QWidget, label_str)` or `None`
- Store UI state in instance variables (e.g., `self._onefile`)
- Connect signals to update state
- Return `None` if your engine doesn't need a UI tab

---

## 4) Full engine shape and lifecycle hooks

A production engine typically implements:

```python
class CompilerEngine:
    id: str = "base"                    # Unique identifier (required)
    name: str = "BaseEngine"            # Display name

    def preflight(self, gui, file: str) -> bool:
        """Perform preflight checks. Return True if OK, False to abort."""
        return True

    def build_command(self, gui, file: str) -> list[str]:
        """Return full command: [program, arg1, arg2, ...]"""
        raise NotImplementedError

    def program_and_args(self, gui, file: str) -> Optional[tuple[str, list[str]]]:
        """Resolve program and args. Default splits build_command."""
        cmd = self.build_command(gui, file)
        if not cmd:
            return None
        return cmd[0], cmd[1:]

    def get_output_directory(self, gui) -> Optional[str]:
        """Return output directory for ACASL to open after build."""
        return None

    def on_success(self, gui, file: str) -> None:
        """Hook called after successful build (metadata/logging only)."""
        pass

    def environment(self, gui, file: str) -> Optional[dict[str, str]]:
        """Return environment variables to inject for the process."""
        return None

    def create_tab(self, gui):
        """Create and return (QWidget, label_str) or None."""
        return None
```

### The `get_output_directory` Method

This method is crucial for ACASL integration. It tells ACASL where to open the output directory after a successful build.

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

See `ENGINES/pyinstaller/engine.py` and `ENGINES/nuitka/engine.py` for real-world examples.

---

## 5) Engine‑owned venv/tool management (async, non‑blocking)

### Principles
- The UI never auto‑installs engine tools; engines decide when to verify and install
- Keep the UI thread responsive; rely on asynchronous checks and installations
- Prefer venv‑local tools; engines should resolve and use the workspace venv

### Recommended pattern (preflight)

```python
from engine_sdk import resolve_project_venv, pip_executable, pip_show, pip_install

def preflight(self, gui, file: str) -> bool:
    """Ensure venv and tools are ready."""
    try:
        # Resolve venv
        vroot = resolve_project_venv(gui)
        if not vroot:
            # Ask UI to create venv if missing
            vm = getattr(gui, 'venv_manager', None)
            if vm and getattr(gui, 'workspace_dir', None):
                vm.create_venv_if_needed(gui.workspace_dir)
            else:
                gui.log.append("❌ No venv detected. Create a venv in the workspace.")
            return False

        # Fast heuristic: check if tool is installed
        vm = getattr(gui, 'venv_manager', None)
        if vm and vm.is_tool_installed(vroot, 'pyinstaller'):
            return True

        # Async confirmation via pip show
        if vm:
            gui.log.append("🔎 Verifying PyInstaller in venv (async)…")
            
            def _on_check(ok: bool):
                if ok:
                    gui.log.append("✅ PyInstaller already installed")
                else:
                    gui.log.append("📦 Installing PyInstaller in venv (async)…")
                    vm.ensure_tools_installed(vroot, ['pyinstaller'])
            
            vm.is_tool_installed_async(vroot, 'pyinstaller', _on_check)
            return False  # Retry later when async op completes

        # Fallback: blocking pip (last resort)
        pip = pip_executable(vroot)
        if pip_show(gui, pip, 'pyinstaller') != 0:
            return pip_install(gui, pip, 'pyinstaller') == 0
        return True

    except Exception:
        return False
```

**Key points:**
- Return `False` when you launch an asynchronous operation; the engine will be retried later
- Use `VenvManager` for non-blocking operations
- Avoid blocking subprocess calls in the UI thread
- Always provide fallbacks for headless/CI environments

---

## 6) Environment and process execution

The SDK exposes safe helpers:

```python
from engine_sdk import resolve_project_venv, pip_executable, pip_show, pip_install
from engine_sdk.utils import build_env, run_process

# Resolve venv
vroot = resolve_project_venv(gui)

# Get pip executable
pip = pip_executable(vroot)

# Check if package is installed
code = pip_show(gui, pip, 'pyinstaller')  # 0 if installed

# Install package
code = pip_install(gui, pip, 'pyinstaller')  # 0 if success

# Build environment (reduced, deterministic)
env = build_env(extra={"LC_ALL": "C.UTF-8"})

# Run process with timeout and streaming
code, out, err = run_process(gui, "python", ["--version"], env=env, timeout_ms=60000)
```

**Best practices:**
- Always construct args as a list of tokens. Do not pass combined strings
- Use `build_env()` for safe, minimal environment setup
- Use `get_timeout_seconds()` to bound long‑running tools
- Prefer venv‑local executables when applicable

---

## 7) Internationalization (i18n)

Engines can provide translations for UI elements. Create a `languages/` folder with JSON files:

```
ENGINES/my_engine/
├── __init__.py
└── languages/
    ├── en.json
    ├── fr.json
    └── es.json
```

**en.json** (English - always required as fallback):
```json
{
  "_meta": {"code": "en", "name": "English"},
  "engine_title": "MyEngine Options",
  "onefile": "Create single file",
  "optimize": "Optimize"
}
```

**fr.json** (French example):
```json
{
  "_meta": {"code": "fr", "name": "Français"},
  "engine_title": "Options MyEngine",
  "onefile": "Créer un fichier unique",
  "optimize": "Optimiser"
}
```

### Implementation in Engine

```python
from engine_sdk import CompilerEngine, registry
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox
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

        # Store references for i18n
        self._title_label = QLabel("MyEngine Options")
        self._onefile_cb = QCheckBox("Create single file")

        lay.addWidget(self._title_label)
        lay.addWidget(self._onefile_cb)

        # Apply current translations
        try:
            self.apply_i18n(gui, getattr(gui, '_tr', {}) or {})
        except Exception:
            pass

        return w, "MyEngine"

    def apply_i18n(self, gui, tr: Dict[str, str]) -> None:
        """Apply engine-local i18n from ENGINES/<id>/languages/*.json."""
        try:
            # Get current language code
            code = 'en'
            try:
                meta = tr.get('_meta', {}) if isinstance(tr, dict) else {}
                if isinstance(meta, dict) and 'code' in meta:
                    code = meta['code']
            except Exception:
                pass

            # Load engine translations
            data = {}
            try:
                pkg = __package__
                for variant in [code, code.split('-')[0] if '-' in code else None, 'en']:
                    if not variant:
                        continue
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

            # Apply to UI elements
            if hasattr(self, '_title_label') and self._title_label:
                self._title_label.setText(data.get('engine_title', 'MyEngine Options'))

            if hasattr(self, '_onefile_cb') and self._onefile_cb:
                self._onefile_cb.setText(data.get('onefile', 'Create single file'))

        except Exception:
            pass


registry.register(MyEngine)
```

**Key points:**
- Always include `en.json` as fallback
- Store widget references in `create_tab` for later updates
- Call `apply_i18n()` at the end of `create_tab()`
- Handle exceptions gracefully - i18n should never break the engine
- Use UTF-8 encoding for all JSON files

---

## 8) Developer checklist and anti‑patterns

### Checklist
- [ ] Package under `ENGINES/<engine_id>/` with `__init__.py`
- [ ] `registry.register(MyEngine)` at module level
- [ ] `build_command()` returns full command as list
- [ ] `preflight()` validates before execution
- [ ] `get_output_directory()` returns correct output path
- [ ] Venv/tool management is engine-owned and non-blocking
- [ ] `create_tab()` returns `(widget, label)` or `None`
- [ ] Exception handling prevents UI crashes
- [ ] i18n support with `apply_i18n()` method

### Anti‑patterns
- ❌ Blocking the UI thread
- ❌ Hardcoded absolute paths
- ❌ Interactive tools without non-interactive flags
- ❌ Passing combined strings as single argv tokens
- ❌ Driving venv/tool management from UI layer
- ❌ Opening output directories from engines (ACASL owns this)
- ❌ Raising exceptions from `create_tab()` or `apply_i18n()`

---

## 9) Troubleshooting (decision tree)

**Engine not visible**
- Ensure `ENGINES/<engine_id>/` exists with `__init__.py`
- Ensure `registry.register(MyEngine)` executes at import
- Check application logs for registry/discovery messages

**Engine tab not bound**
- If using `create_tab()`, ensure you return `(QWidget, "Label")`
- Verify the widget is a valid `QWidget` instance

**Command not found**
- Check PATH; prefer `resolve_project_venv()` for venv tools
- Resolve tool binary from `venv/bin` (Linux/macOS) or `venv/Scripts` (Windows)

**Process hangs or times out**
- Lower timeout; make tool non-interactive
- Inspect stderr/stdout for blocking prompts

**Venv/tool not installed**
- Follow the preflight pattern: heuristic → async check → async install
- Return `False` from `preflight()` while async ops run

**Output directory not opened**
- Ensure `get_output_directory()` returns a valid path
- ACASL handles opening; engines must not open directories themselves

---

## Conclusion

This guide provides a foundation for creating robust compilation engines for PyCompiler ARK++. The Engine SDK offers powerful abstractions while maintaining flexibility for custom implementations.

### Key Takeaways
- **Follow the patterns**: Use provided templates for consistency
- **Prioritize responsiveness**: Keep operations non-blocking
- **Embrace modularity**: Engines are self-contained and discoverable
- **Test thoroughly**: Validate across platforms and edge cases

### Getting Help
- Check existing engines in `ENGINES/` for real-world examples
- Review the Engine SDK source code for advanced patterns
- Follow the troubleshooting guide for common issues

Happy engine building! 🚀
