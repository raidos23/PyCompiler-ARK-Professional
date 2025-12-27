# About SDKs

This document provides an overview of the development SDKs available in PyCompiler ARK++ and how they fit together.

- **Audience:** Plugin and engine developers
- **Scope:** High-level concepts and links to concrete guides

## Overview

PyCompiler ARK++ exposes two main SDKs:

### 1) Plugins_SDK (BC Plugins via BCASL)

**Purpose:** Create **BC (Before Compilation) plugins** managed by BCASL (Before-Compilation Actions System Loader) that execute before a build starts.

**What are BC Plugins?**
BC plugins are pre-compilation plugins that validate, prepare, and optimize the workspace before compilation engines run. They are distinct from compilation engines (PyInstaller, Nuitka, etc.).

**Typical Responsibilities:**
- Validate project structure and dependencies
- Prepare artifacts (generate files, clean up, configure pathing)
- Perform pre-flight checks and block the build when necessary
- Clean workspace before compilation

**Key Characteristics:**
- **Registration:** Uses `bcasl_register(manager)` function to register with BCASL
- **Version Compatibility:** Plugins declare required versions for BCASL, Core, and SDK components
- **User Interaction:** Uses `Dialog` API from `Plugins_SDK.GeneralContext` for logging and user prompts
- **Context Access:** Receives `PreCompileContext` with workspace info and file iteration utilities
- **Tag-Based Ordering:** Execution order determined by tags (e.g., "clean", "check", "prepare")
- **Configuration:** Managed via `bcasl.yml` (YML only) and `ARK_Main_Config.yml`
- **No i18n:** Plugins use static English messages (internationalization removed)

**Start Here:** [How to Create a BC Plugin](./how_to_create_a_BC_plugin.md)

### 2) Engine SDK

**Purpose:** Implement **compilation engines** (e.g., PyInstaller, Nuitka, cx_Freeze) with pluggable UI and behavior.

**What are Engines?**
Engines are compilation tools that transform Python code into executables. They are distinct from BC plugins - engines perform the actual compilation, while BC plugins prepare the workspace before compilation.

**Typical Responsibilities:**
- Build command composition (program and arguments)
- Engine-owned venv/tooling checks and non-blocking installation flows
- Tab UI creation with PySide6
- Post-success hook for user feedback (logs, opening directories, etc.)
- Engine-specific configuration management

**Key Characteristics:**
- **Registration:** Self-register via `registry.register(MyEngine)` on import
- **Version Compatibility:** Engines declare `required_core_version` and `required_sdk_version`
- **Discovery:** Auto-discovered from `ENGINES/` directory (packages only)
- **UI Integration:** Optional tab creation via `create_tab(gui)` method
- **Internationalization:** Supports `apply_i18n(gui, tr)` for multi-language UI
- **State Persistence:** UI state automatically saved to `ARK_Main_Config.yml`
- **Configuration:** Engine-specific options in `ARK_Main_Config.yml`

**Start Here:** [How to Create an Engine](./how_to_create_an_engine.md)

---

## Lifecycle

The typical lifecycle when compiling a project:

### 1. User Selection
- User selects workspace directory in GUI
- User selects file(s) to compile
- User selects compilation engine (PyInstaller, Nuitka, etc.)

### 2. BCASL Plugins (Plugins_SDK)
- **When:** Before compilation starts
- **Order:** Determined by plugin tags and priority
- **Execution:**
  - Plugins receive `PreCompileContext` with workspace information
  - Plugins can use `Dialog` for user interaction and logging
  - Plugins can abort build by raising exceptions
- **Output:** Validated and prepared workspace

### 3. Engine Execution (Engine SDK)
- **Preflight:** Engine performs validation checks
- **Tool Resolution:** Resolves tools in workspace venv
- **Command Building:** Constructs compilation command
- **Process Execution:** Runs build using QProcess with streaming logs
- **Progress:** Real-time output streamed to GUI log

### 4. Post-Success Hook
- **When:** After successful compilation
- **Actions:**
  - Engine may open output directory automatically
  - Engine may log artifact details
  - Engine may update metadata

---

## Version Compatibility System

Both SDKs include robust version compatibility validation:

### Plugins (BCASL)

Plugins declare required versions in `PluginMeta`:

```python
META = PluginMeta(
    id="my.plugin",
    name="My Plugin",
    version="1.0.0",
    required_bcasl_version="2.0.0",
    required_core_version="1.0.0",
    required_plugins_sdk_version="1.0.0",
    required_bc_plugin_context_version="1.0.0",
    required_general_context_version="1.0.0",
)
```

### Engines

Engines declare required versions as class attributes:

```python
class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"
    version = "1.0.0"
    required_core_version = "1.0.0"
    required_sdk_version = "1.0.0"
```

### Version Format

Supported formats:
- `"1.0.0"` → (1, 0, 0)
- `"1.0.0+"` → (1, 0, 0) [+ means "or higher"]
- `"1.0.0-beta"` → (1, 0, 0)
- `"1.0.0+build123"` → (1, 0, 0)

**Compatibility uses >= semantics:** If a plugin requires version 1.0.0, it accepts 1.0.0, 1.0.1, 1.1.0, 2.0.0, etc.

---

## Registration Mechanisms

### BCASL Plugin Registration

```python
# Create plugin instance
PLUGIN = MyPlugin()

# Define registration function
def bcasl_register(manager):
    """Called by BCASL loader during discovery"""
    manager.add_plugin(PLUGIN)
```

**Discovery:**
1. BCASL scans `Plugins/` directory
2. Imports packages (directories with `__init__.py`)
3. Calls `bcasl_register(manager)` if present
4. Validates version compatibility
5. Filters out incompatible plugins

### Engine Registration

```python
# Self-register at module level
class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"
    # ...

registry.register(MyEngine)
```

**Discovery:**
1. `engines_loader` scans `ENGINES/` directory
2. Imports packages (directories with `__init__.py`)
3. Engines self-register via `registry.register()`
4. Validates version compatibility
5. `bind_tabs()` creates UI tabs for compatible engines

---

## Configuration Integration

### BCASL Configuration (BC Plugins Only)

**Note:** This configuration applies to **BC plugins only**, not compilation engines.

BC plugins are configured in two places:

1. **bcasl.yml (YML only)** - Plugin-specific configuration
   ```yaml
   plugins:
     my.plugin.id:
       enabled: true
       priority: 0
   plugin_order:
     - my.plugin.id
   ```

2. **ARK_Main_Config.yml** - Global plugin settings
   ```yaml
   plugins:
     bcasl_enabled: true
     plugin_timeout: 30.0
   ```

**Priority:** ARK configuration overrides BCASL configuration.

See [BCASL Configuration Guide](./BCASL_Configuration.md) for BC plugin configuration details.

### Engine Configuration

Engines are configured in `ARK_Main_Config.yml`:

```yaml
pyinstaller:
  onefile: true
  windowed: false
  additional_options: []

nuitka:
  onefile: true
  standalone: true
  additional_options: []

# Engine UI state (auto-managed)
engines:
  pyinstaller:
    ui:
      widgets: {}
```

See [ARK Configuration Guide](./ARK_Configuration.md) for details.

---

## Design Principles

### Non-Blocking UI
- All long operations must be asynchronous or off the GUI thread
- BCASL uses QThread for background execution
- Engines use QProcess for compilation
- Progress updates stream to GUI without blocking

### Version Compatibility
- All components declare version requirements
- Incompatible plugins/engines are rejected during discovery
- Clear error messages for version mismatches
- Semantic versioning with >= comparison

### Least Privileges
- Engines/tools run with minimal environment variables
- Sandboxed execution when appropriate
- No unnecessary file system access

### Reproducibility
- Prefer venv-local tools over system tools
- Deterministic command lines
- Configuration-driven behavior
- State persistence for consistency

### User Experience
- Clear logging and progress feedback
- User confirmation for destructive operations
- Automatic state persistence
- Internationalization support (engines only)

---

## Directory Structure

```
<project root>
├── ENGINES/
│   ├── pyinstaller/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── languages/          # i18n support
│   │       ├── en.json
│   │       ├── fr.json
│   │       └── ...
│   ├── nuitka/
│   │   └── __init__.py
│   └── cx_freeze/
│       └── __init__.py
│
├── Plugins/
│   ├── Cleaner/
│   │   └── __init__.py         # No languages/ - uses static messages
│   └── my.plugin.id/
│       └── __init__.py
│
├── Core/
│   ├── engines_loader/         # Engine discovery and registry
│   └── ark_config_loader.py    # Configuration management
│
├── bcasl/
│   ├── Loader.py               # Plugin discovery and execution
│   ├── Base.py                 # Plugin base classes
│   └── validator.py            # Version compatibility
│
├── engine_sdk/
│   └── base.py                 # Engine base class re-export
│
└── Plugins_SDK/
    ├── BcPluginContext.py      # Plugin base classes and context
    └── GeneralContext.py       # Dialog API for user interaction
```

---

## Key Differences: Plugins vs Engines

| Aspect | BC Plugins (BCASL) | Engines |
|--------|---------------------|---------|
| **Purpose** | Pre-compilation validation/preparation (BC phase) | Compilation execution |
| **When** | Before build starts | During build |
| **Registration** | `bcasl_register(manager)` | `registry.register(MyEngine)` |
| **Discovery** | `Plugins/` directory | `ENGINES/` directory |
| **UI** | None (uses Dialog API) | Optional tab via `create_tab()` |
| **i18n** | No (static messages) | Yes (via `apply_i18n()`) |
| **User Interaction** | Dialog API (thread-safe) | Direct Qt widgets |
| **State Persistence** | Via configuration files | Automatic UI state saving |
| **Execution** | Sequential with priorities | Single engine at a time |
| **Can Abort Build** | Yes (raise exception) | Yes (return False from preflight) |

---

## Development Quick Start

### Creating a BCASL Plugin

1. Create package: `Plugins/my.plugin.id/__init__.py`
2. Import SDK: `from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta`
3. Define metadata with version requirements
4. Implement `on_pre_compile(ctx)` method
5. Create Dialog instances for logging
6. Add `bcasl_register(manager)` function

**Example:**
```python
from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta
from Plugins_SDK.GeneralContext import Dialog

log = Dialog()

META = PluginMeta(
    id="my.plugin",
    name="My Plugin",
    version="1.0.0",
    required_bcasl_version="2.0.0",
)

class MyPlugin(BcPluginBase):
    def __init__(self):
        super().__init__(META)
    
    def on_pre_compile(self, ctx):
        log.log_info("Running my plugin...")

PLUGIN = MyPlugin()

def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

### Creating an Engine

1. Create package: `ENGINES/my_engine/__init__.py`
2. Import SDK: `from engine_sdk import CompilerEngine, registry`
3. Define engine class with version attributes
4. Implement required methods: `preflight()`, `build_command()`
5. Implement optional methods: `create_tab()`, `apply_i18n()`, `on_success()`
6. Self-register: `registry.register(MyEngine)`

**Example:**
```python
from engine_sdk import CompilerEngine, registry

class MyEngine(CompilerEngine):
    id = "my_engine"
    name = "My Engine"
    version = "1.0.0"
    required_core_version = "1.0.0"
    required_sdk_version = "1.0.0"
    
    def preflight(self, gui, file: str) -> bool:
        return bool(file)
    
    def build_command(self, gui, file: str) -> list[str]:
        return ["my_compiler", "--output", "dist", file]

registry.register(MyEngine)
```

---

## See Also

- [How to Create a BC Plugin](./how_to_create_a_BC_plugin.md) - Complete BC plugin development guide
- [How to Create an Engine](./how_to_create_an_engine.md) - Complete engine development guide
- [BCASL Configuration Guide](./BCASL_Configuration.md) - BC plugin configuration (BCASL-specific)
- [ARK Configuration Guide](./ARK_Configuration.md) - Global configuration system (includes engine configuration)