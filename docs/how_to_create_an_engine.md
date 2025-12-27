# How to Create a Building Engine

## Quick Navigation
- [TL;DR](#0-tldr-copy-paste-template)
- [Layout & discovery](#1-folder-layout-and-discovery)
- [Minimal engine](#2-minimal-engine-implementation)
- [UI tab](#3-ui-tab-create_tab-example)
- [Lifecycle](#4-full-engine-shape-and-lifecycle-hooks)
- [Venv/Tools](#5-engine-owned-venvtool-management-async-non-blocking)
- [Environment/Process](#6-environment-and-process-execution)
- [ARK Config](#7-ark-configuration-integration)
- [i18n](#8-internationalization-i18n)
- [UI State](#9-ui-state-persistence)
- [Checklist](#10-developer-checklist-and-anti-patterns)
- [Registry](#11-registry-and-discovery-details)
- [Troubleshooting](#12-troubleshooting-decision-tree)

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
    version = "1.0.0"
    required_core_version = "1.0.0"
    required_sdk_version = "1.0.0"

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
    version = "1.0.0"
    required_core_version = "1.0.0"
    required_sdk_version = "1.0.0"

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
    version = "1.0.0"
    required_core_version = "1.0.0"
    required_sdk_version = "1.0.0"
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
    version: str = "1.0.0"              # Engine version
    required_core_version: str = "1.0.0"  # Minimum required Core version
    required_sdk_version: str = "1.0.0"   # Minimum required SDK version

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

    def apply_i18n(self, gui, tr: dict) -> None:
        """Apply internationalization translations to engine UI elements."""
        pass
```

### Version Compatibility System

The engine loader includes a robust version compatibility validation system:

```python
from Core.engines_loader.validator import (
    check_engine_compatibility,
    validate_engines_compatibility,
)

# Version strings support formats like "1.0.0", "1.0.0+", "1.0.0-beta"
# Compatibility uses >= semantics: if engine requires 1.0.0, it accepts 1.0.0, 1.0.1, 1.1.0, etc.
```

**Version Requirements:**
- `version`: Your engine's own version (for tracking/logging)
- `required_core_version`: Minimum Core version your engine needs (uses >= comparison)
- `required_sdk_version`: Minimum Engine SDK version your engine needs (uses >= comparison)

**Key Points:**
- Engines without explicit version requirements may be rejected in strict mode
- Version comparison uses semantic versioning with >= semantics
- The + suffix in version strings (e.g., "1.0.0+") explicitly indicates "or higher" compatibility
- Incompatible engines are filtered out during auto-discovery with detailed error messages

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

## 7) ARK Configuration Integration

Engines can leverage the ARK configuration system for engine-specific settings:

### Loading ARK Configuration

```python
from Core.ark_config_loader import load_ark_config, get_compiler_options

class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"

    def preflight(self, gui, file: str) -> bool:
        """Load engine options from ARK_Main_Config.yml"""
        try:
            workspace_dir = getattr(gui, "workspace_dir", None)
            if not workspace_dir:
                return True
            
            ark_config = load_ark_config(workspace_dir)
            engine_opts = get_compiler_options(ark_config, self.id)
            
            # Apply engine-specific options from config
            self.onefile = engine_opts.get("onefile", True)
            self.windowed = engine_opts.get("windowed", False)
            
            return True
        except Exception:
            return True  # Fail gracefully
```

### ARK_Main_Config.yml Example

```yaml
# Engine-specific options
my_engine:
  onefile: true
  windowed: false
  additional_options:
    - "--hidden-import=module_name"

# Global output configuration
output:
  directory: "dist"
  clean_before_build: false

# Exclusion patterns (used by engines for file filtering)
exclusion_patterns:
  - "**/__pycache__/**"
  - "**/*.pyc"
  - ".git/**"
  - "venv/**"
  - ".venv/**"
```

### Using Exclusion Patterns

```python
from Core.ark_config_loader import load_ark_config, should_exclude_file

class MyEngine(CompilerEngine):
    def build_command(self, gui, file: str) -> list[str]:
        """Build command respecting ARK exclusion patterns"""
        try:
            workspace_dir = getattr(gui, "workspace_dir", None)
            if workspace_dir:
                ark_config = load_ark_config(workspace_dir)
                exclusion_patterns = ark_config.get("exclusion_patterns", [])
                
                # Check if file should be excluded
                if should_exclude_file(file, workspace_dir, exclusion_patterns):
                    return []  # Skip this file
        except Exception:
            pass
        
        return ["my_compiler", "--onefile", file]
```

### Key Points

- **Configuration Priority**: Engine options in `ARK_Main_Config.yml` override defaults
- **Graceful Fallback**: Always handle missing config gracefully
- **Workspace-Aware**: Always check for workspace directory before loading config
- **Exclusion Patterns**: Use `should_exclude_file()` to respect global exclusion rules
- **Output Directory**: Use `get_output_options()` to respect global output settings

---

## 8) Internationalization (i18n)

Engines can support multiple languages through the `apply_i18n()` method:

```python
class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"
    
    def apply_i18n(self, gui, tr: dict) -> None:
        """Apply internationalization translations to engine UI elements.
        
        Args:
            gui: Main GUI object
            tr: Translation dictionary loaded from language files
        """
        try:
            # Access your engine's tab widget
            tabs = getattr(gui, "compiler_tabs", None)
            if not tabs:
                return
            
            # Find your widgets by object name
            container = tabs.findChild(QWidget, "my_engine_container")
            if not container:
                return
            
            # Apply translations
            label = container.findChild(QLabel, "options_label")
            if label:
                label.setText(tr.get("my_engine_options", "Options"))
            
            checkbox = container.findChild(QCheckBox, "onefile_checkbox")
            if checkbox:
                checkbox.setText(tr.get("my_engine_onefile", "Single File"))
                
        except Exception:
            # Fail gracefully - never crash on i18n updates
            pass
```

**Translation Flow:**
1. The registry calls `apply_i18n()` on all engine instances when language changes
2. Engines receive the full translation dictionary from `languages/*.json`
3. Engines should look up their own translation keys (prefix with engine_id recommended)
4. Always handle exceptions gracefully - i18n should never crash the UI

**Best Practices:**
- Set `objectName` on all widgets you want to translate
- Use a consistent naming pattern: `{engine_id}_{widget_purpose}`
- Fail silently if widgets or translations are missing
- Test with multiple languages during development

---

## 9) UI State Persistence

Engines can persist their UI state automatically through the ARK configuration system:

```python
from Core.engines_loader.registry import save_engine_ui

class MyEngine(CompilerEngine):
    def create_tab(self, gui):
        w = QWidget()
        lay = QVBoxLayout(w)
        
        # Set objectName on widgets you want to persist
        cb = QCheckBox("Onefile")
        cb.setObjectName("onefile_checkbox")
        cb.setChecked(True)
        
        # Connect signal to save state
        cb.stateChanged.connect(lambda: self._save_ui_state(gui))
        lay.addWidget(cb)
        
        return w, "MyEngine"
    
    def _save_ui_state(self, gui):
        """Persist UI state to ARK_Main_Config.yml"""
        try:
            # Build state dictionary: {widgetName: {property: value}}
            state = {
                "onefile_checkbox": {"checked": self._onefile},
            }
            save_engine_ui(gui, self.id, state)
        except Exception:
            pass
```

**Supported Properties:**
- `checked`: For checkboxes (bool)
- `text`: For text inputs (str)
- `enabled`: For enabling/disabling widgets (bool)
- `visible`: For showing/hiding widgets (bool)
- `currentIndex`: For combo boxes (int)

**Key Points:**
- State is saved per workspace in `ARK_Main_Config.yml`
- State is automatically restored when `bind_tabs()` is called
- Always use `objectName` for widgets you want to persist
- The registry handles loading state before your tab is shown

---

## 10) Developer checklist and anti‑patterns

Checklist
- [ ] Package under `ENGINES/<engine_id>/` with `__init__.py`
- [ ] `registry.register(MyEngine)` at module level
- [ ] Version attributes defined: `version`, `required_core_version`, `required_sdk_version`
- [ ] `build_command()` returns full command as list
- [ ] `preflight()` validates before execution
- [ ] `get_output_directory()` returns correct output path
- [ ] Venv/tool management is engine-owned and non-blocking
- [ ] `create_tab()` returns `(widget, label)` or `None`
- [ ] Widget `objectName` attributes set for state persistence
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

## 11) Registry and Discovery Details

The engine loader provides several utilities through the registry:

```python
from Core.engines_loader import registry

# Check if an engine is registered
engine_cls = registry.get_engine("my_engine")

# List all available engine IDs
engine_ids = registry.available_engines()

# Create an instance of an engine
engine_instance = registry.create("my_engine")

# Unregister an engine (cleanup/testing)
registry.unregister("my_engine")

# Map tab index to engine ID
engine_id = registry.get_engine_for_tab(tab_index)
```

**Discovery Process:**
1. At startup, `_auto_discover()` scans the `ENGINES/` directory
2. Only packages (directories with `__init__.py`) are imported
3. Engines must self-register via `registry.register(MyEngine)` during import
4. Each engine's `__init__.py` and all submodules are imported
5. Version compatibility is validated against Core and SDK versions
6. Incompatible engines are filtered out with detailed error messages
7. `bind_tabs()` creates UI tabs for engines implementing `create_tab()`

**Environment Control:**
- Set `ARK_ENGINES_AUTO_DISCOVER=0` to disable auto-discovery
- Useful for testing or controlled engine loading scenarios

---

## 12) Troubleshooting (decision tree)

Engine not visible
- Ensure `ENGINES/<engine_id>/` exists with `__init__.py`
- Ensure `registry.register(MyEngine)` executes at import
- Check version compatibility requirements match your Core/SDK versions
- Check application logs for registry/discovery messages
- Verify `ARK_ENGINES_AUTO_DISCOVER` is not set to 0

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

Version compatibility errors
- Check engine's `required_core_version` and `required_sdk_version` attributes
- Ensure versions use semantic versioning format (e.g., "1.0.0")
- Use "1.0.0+" format to explicitly indicate "or higher" compatibility
- Run compatibility validator manually if needed: `check_engine_compatibility()`

UI state not persisting
- Ensure widgets have `objectName` set
- Verify `save_engine_ui()` is called with correct state dictionary
- Check `ARK_Main_Config.yml` in workspace directory for saved state
- Verify supported properties are used: checked, text, enabled, visible, currentIndex

i18n not working
- Implement `apply_i18n(gui, tr)` method in your engine class
- Ensure translation keys exist in `languages/*.json` files
- Set `objectName` on widgets you want to translate
- Check that the registry properly stores your engine instance

---

## Conclusion

- Follow the patterns for consistency
- Keep operations non-blocking
- Embrace modularity (self-contained engines)
- Test thoroughly across platforms and edge cases

Happy engine building! 🚀

