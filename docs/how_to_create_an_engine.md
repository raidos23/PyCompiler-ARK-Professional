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

- Package Structure: Engines are Python packages under `ENGINES/<engine_id>/` (directory with `__init__.py`)
- Self-Registration: Engines must self‑register on import via the central registry: `registry.register(MyEngine)`
- Discovery: `engines_loader` discovers engines strictly from the `ENGINES/` directory
- SDK Integration: Import the SDK and registry from `engine_sdk` for all core functionality
- Async Tool Management: venv/tool management is engine‑owned and must be non‑blocking (asynchronous patterns)
- Output Handling: Engines may define an output directory via `get_output_directory()`; engines may also open the output directory themselves from `on_success()` if appropriate for UX

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
        """Return the output directory for this engine."""
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

    def on_success(self, gui, file: str) -> None:
        """Optional post-success action (e.g., open output directory)."""
        out = self.get_output_directory(gui)
        if not out:
            return
        import platform, subprocess, os
        if os.path.isdir(out):
            if platform.system() == "Windows":
                os.startfile(out)
            elif platform.system() == "Linux":
                subprocess.run(["xdg-open", out])
            else:
                subprocess.run(["open", out])


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
        """Return engine output directory."""
        try:
            ws = getattr(gui, "workspace_dir", None) or os.getcwd()
            return os.path.join(ws, "dist")
        except Exception:
            return os.path.join(os.getcwd(), "dist")


registry.register(MyEngine)
```

Key points:
- `build_command()` returns the full command as a list (program at index 0)
- `preflight()` validates before execution; return False to abort
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
```

Key points:
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
        """Return output directory for the engine."""
        return None

    def on_success(self, gui, file: str) -> None:
        """Hook called after successful build (metadata/logging, optional opening of output directory)."""
        pass

    def environment(self, gui, file: str) -> Optional[dict[str, str]]:
        """Return environment variables to inject for the process."""
        return None

    def create_tab(self, gui):
        """Create and return (QWidget, label_str) or None."""
        return None
```

### The `get_output_directory` Method

```python
def get_output_directory(self, gui) -> Optional[str]:
    """Return the output directory to open after successful build.
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
        return os.path.join(os.getcwd(), "dist")
```

Principles:
- Return the actual output directory path where your engine produces files
- Use a priority system: engine-specific fields → global fields → sensible defaults
- Never return `None` unless absolutely no output directory can be determined
- Handle exceptions gracefully with fallbacks

See `ENGINES/pyinstaller/engine.py` and `ENGINES/nuitka/engine.py` for real-world examples.

---

## 5) Engine‑owned venv/tool management (async, non‑blocking)

- The UI never auto‑installs engine tools; engines decide when to verify and install
- Keep the UI thread responsive; rely on asynchronous checks and installations
- Prefer venv‑local tools; engines should resolve and use the workspace venv

---

## 6) Environment and process execution

The SDK exposes safe helpers in `engine_sdk.utils` and related modules to:
- Build sanitized environments
- Run processes with timeouts and streaming

---

## 7) Internationalization (i18n)

- Engines can provide translations for UI elements via `languages/*.json`
- Always include `en.json` as fallback
- Apply translations in `create_tab()` and/or `apply_i18n()`

---

## 8) Developer checklist and anti‑patterns

Checklist
- [ ] Package under `ENGINES/<engine_id>/` with `__init__.py`
- [ ] `registry.register(MyEngine)` at module level
- [ ] `build_command()` returns full command as list
- [ ] `preflight()` validates before execution
- [ ] `get_output_directory()` returns correct output path
- [ ] Venv/tool management is engine-owned and non-blocking
- [ ] `create_tab()` returns `(widget, label)` or `None`
- [ ] Exception handling prevents UI crashes
- [ ] i18n support with `apply_i18n()` method

Anti‑patterns
- Blocking the UI thread
- Hardcoded absolute paths
- Interactive tools without non-interactive flags
- Passing combined strings as single argv tokens
- Driving venv/tool management from UI layer
- Raising exceptions from `create_tab()` or `apply_i18n()`

---

## 9) Troubleshooting (decision tree)

Engine not visible
- Ensure `ENGINES/<engine_id>/` exists with `__init__.py`
- Ensure `registry.register(MyEngine)` executes at import
- Check application logs for registry/discovery messages

Engine tab not bound
- If using `create_tab()`, ensure you return `(QWidget, "Label")`
- Verify the widget is a valid `QWidget` instance

Command not found
- Check PATH; prefer `resolve_project_venv()` for venv tools
- Resolve tool binary from `venv/bin` (Linux/macOS) or `venv/Scripts` (Windows)

Process hangs or times out
- Lower timeout; make tool non-interactive
- Inspect stderr/stdout for blocking prompts

Venv/tool not installed
- Follow the preflight pattern: heuristic → async check → async install
- Return `False` from `preflight()` while async ops run

Output directory not opened
- Ensure `get_output_directory()` returns a valid path

---

## Conclusion

- Follow the patterns for consistency
- Keep operations non-blocking
- Embrace modularity (self-contained engines)
- Test thoroughly across platforms and edge cases

Happy engine building! 🚀

