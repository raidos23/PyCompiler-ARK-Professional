# How to Create a BC Plugin (BCASL)

This guide explains how to implement a **BC (Before Compilation) plugin** for PyCompiler ARK++ using the Plugins_SDK.

**What are BC Plugins?**
BC plugins are pre-compilation plugins managed by BCASL (Before-Compilation Actions System Loader) that execute before the build process starts. They validate, prepare, and optimize the workspace before compilation engines (PyInstaller, Nuitka, etc.) run.

**Note:** This guide is for BC plugins only. For creating compilation engines, see [How to Create an Engine](./how_to_create_an_engine.md).

## Quick Navigation
- [TL;DR](#0-tldr-copy-paste-template)
- [Folder layout](#1-folder-layout)
- [Minimal plugin](#2-minimal-plugin)
- [Metadata and version compatibility](#3-metadata-and-version-compatibility)
- [User interaction and logging](#4-user-interaction-and-logging)
- [Configuration integration](#5-configuration-integration)
- [Testing and debugging](#6-testing-and-debugging)
- [Checklist](#7-developer-checklist)

## 0) TL;DR (copy‑paste template)

Create `Plugins/my.plugin.id/__init__.py`:

```python
from __future__ import annotations

from pathlib import Path
from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta, PreCompileContext
from Plugins_SDK.GeneralContext import Dialog

# Create Dialog instances for user interaction and logging
log = Dialog()
dialog = Dialog()

META = PluginMeta(
    id="my.plugin.id",
    name="My BC Plugin",
    version="1.0.0",
    description="Describe what this BC plugin does before compilation.",
    author="Your Name",
    tags=("check",),   # e.g., ("clean", "check", "optimize", "prepare", ...)
    required_bcasl_version="2.0.0",
    required_core_version="1.0.0",
    required_plugins_sdk_version="1.0.0",
    required_bc_plugin_context_version="1.0.0",
    required_general_context_version="1.0.0",
)


class MyPlugin(BcPluginBase):
    def __init__(self) -> None:
        super().__init__(META)

    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        """Execute pre-compilation actions.
        
        Args:
            ctx: PreCompileContext with workspace information and utilities
        """
        try:
            # Example: Ask user for confirmation
            response = dialog.msg_question(
                title="My Plugin",
                text="Proceed with pre-build checks?",
                default_yes=True,
            )
            
            if not response:
                log.log_info("Plugin cancelled by user")
                return
            
            # Example: Check for Python files
            files = list(ctx.iter_files(["*.py"], []))
            if not files:
                log.log_warn("No Python files found in workspace")
                raise RuntimeError("No Python files found in workspace")
            
            log.log_info(f"Found {len(files)} Python files")
            # Perform additional preparation...
            
        except Exception as e:
            log.log_error(f"Plugin error: {e}")
            raise


# Create plugin instance
PLUGIN = MyPlugin()


def bcasl_register(manager):
    """Register the plugin with the BCASL manager."""
    manager.add_plugin(PLUGIN)
```

## 1) Folder layout

```
<project root>
└── Plugins/
    └── my.plugin.id/
        └── __init__.py
```

**Key Points:**
- The plugin package must be importable (contains `__init__.py`)
- The global variable `PLUGIN` must point to an instance of your plugin class
- The function `bcasl_register(manager)` must be defined to register the plugin
- Plugin directory name should match the plugin ID for clarity

## 2) Minimal plugin

A minimal BCASL plugin requires:

1. **Import necessary classes:**
```python
from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta, PreCompileContext
from Plugins_SDK.GeneralContext import Dialog
```

2. **Create Dialog instances for logging and user interaction:**
```python
log = Dialog()
dialog = Dialog()
```

3. **Define plugin metadata:**
```python
META = PluginMeta(
    id="my.plugin.id",          # Unique identifier
    name="My Plugin",            # Display name
    version="1.0.0",             # Plugin version
    description="...",           # Brief description
    author="Your Name",          # Optional
    tags=("check",),             # Tags for ordering
    required_bcasl_version="2.0.0",
    required_core_version="1.0.0",
    required_plugins_sdk_version="1.0.0",
    required_bc_plugin_context_version="1.0.0",
    required_general_context_version="1.0.0",
)
```

4. **Implement the plugin class:**
```python
class MyPlugin(BcPluginBase):
    def __init__(self):
        super().__init__(META)
    
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        # Implement your pre-compilation logic here
        pass
```

5. **Create instance and registration function:**
```python
PLUGIN = MyPlugin()

def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

**Important:**
- Raise an exception to abort the build when a blocking condition is met
- The plugin should be idempotent (safe to run multiple times)
- Never block the UI thread with long operations

## 3) Metadata and version compatibility

### PluginMeta Fields

```python
@dataclass(frozen=True)
class PluginMeta:
    id: str                                      # Unique identifier (required)
    name: str                                    # Display name
    version: str                                 # Plugin version
    description: str = ""                        # Brief description
    author: str = ""                             # Author name
    tags: tuple[str, ...] = ()                   # Tags for ordering
    required_bcasl_version: str = "1.0.0"        # Minimum BCASL version
    required_core_version: str = "1.0.0"         # Minimum Core version
    required_plugins_sdk_version: str = "1.0.0"  # Minimum Plugins SDK version
    required_bc_plugin_context_version: str = "1.0.0"  # Minimum BcPluginContext version
    required_general_context_version: str = "1.0.0"    # Minimum GeneralContext version
```

### Version Compatibility System

The BCASL loader validates plugin compatibility using semantic versioning with >= semantics:

```python
# Version formats supported:
# - "1.0.0" -> (1, 0, 0)
# - "1.0.0+" -> (1, 0, 0) [+ means "or higher"]
# - "1.0.0-beta" -> (1, 0, 0)
# - "1.0.0+build123" -> (1, 0, 0)

# If plugin requires BCASL 2.0.0:
# ✓ Compatible: 2.0.0, 2.0.1, 2.1.0, 3.0.0
# ✗ Incompatible: 1.9.9, 1.0.0
```

**Key Points:**
- Plugins without explicit version requirements may be rejected in strict mode
- Version comparison uses >= semantics (accepts equal or higher versions)
- Incompatible plugins are filtered out during auto-discovery with detailed error messages
- The + suffix explicitly indicates "or higher" compatibility

### Tags for Plugin Ordering

Tags are used to determine plugin execution order. Common tags include:

- `"clean"`: Cleanup operations (runs first)
- `"check"`: Validation checks
- `"prepare"`: Preparation tasks
- `"optimize"`: Optimization operations
- `"generate"`: Code generation
- `"package"`: Packaging operations (runs last)

**Tag Normalization:**
- Tags are automatically normalized to lowercase
- Multiple tags can be specified: `tags=("clean", "check")`
- Plugins with the same tags are ordered alphabetically by ID
- Custom tags can be used; ordering is determined by tag phase mapping

## 4) User interaction and logging

### Dialog API

The `Dialog` class from `Plugins_SDK.GeneralContext` provides thread-safe UI interactions:

```python
from Plugins_SDK.GeneralContext import Dialog

log = Dialog()
dialog = Dialog()

# Logging methods
log.log_info("Information message")
log.log_warn("Warning message")
log.log_error("Error message")

# User confirmation
response = dialog.msg_question(
    title="Plugin Name",
    text="Do you want to proceed?",
    default_yes=True,
)
if not response:
    log.log_info("Operation cancelled by user")
    return

# Progress dialog
progress = dialog.progress(title="Processing...", cancelable=True)
progress.show()
try:
    progress.set_message("Step 1: Scanning files...")
    progress.set_progress(0, total_items)
    
    for idx, item in enumerate(items):
        if progress.is_canceled():
            break
        # Process item...
        progress.set_progress(idx + 1, total_items)
finally:
    progress.close()
```

**Key Features:**
- All dialogs automatically execute in the main Qt thread
- Dialogs inherit application theme and styling
- Progress dialogs support cancellation
- Logging appears in the main application log window

## 5) Configuration integration

### Accessing Configuration

The `PreCompileContext` provides access to configuration:

```python
def on_pre_compile(self, ctx: PreCompileContext) -> None:
    # Access workspace path
    workspace_path = Path(ctx.workspace) if hasattr(ctx, 'workspace') else ctx.project_root
    
    # Access configuration
    config = ctx.config
    
    # Get plugin-specific options from bcasl.yml
    plugin_opts = config.get("plugins", {}).get(self.meta.id, {})
    enabled = plugin_opts.get("enabled", True)
    priority = plugin_opts.get("priority", 100)
```

### File Iteration

Use `ctx.iter_files()` to scan workspace files efficiently:

```python
def on_pre_compile(self, ctx: PreCompileContext) -> None:
    # Find all Python files, excluding common directories
    py_files = list(ctx.iter_files(
        include=["**/*.py"],
        exclude=["**/__pycache__/**", "**/venv/**", "**/.venv/**"]
    ))
    
    # Results are cached by default for performance
    # Multiple calls with same patterns reuse cached results
```

**Performance Tips:**
- Use specific include patterns to minimize scanning
- Leverage caching (enabled by default)
- Avoid calling `list()` if you only need to iterate once

## 6) Testing and debugging

### Testing Checklist

- [ ] Plugin loads without errors during discovery
- [ ] Plugin metadata is correctly displayed in BCASL Loader UI
- [ ] Plugin executes successfully with valid workspace
- [ ] Plugin handles missing files/directories gracefully
- [ ] Plugin respects user cancellation in dialogs
- [ ] Plugin logs informative messages
- [ ] Plugin raises exceptions for critical failures
- [ ] Plugin is idempotent (can run multiple times safely)

### Debugging Tips

1. **Check Plugin Discovery:**
```bash
# Set environment variable to see discovery logs
export PYCOMPILER_VERBOSE=1
```

2. **Test Plugin Isolation:**
```python
# Disable other plugins in bcasl.yml to test individually
plugins:
  my.plugin.id:
    enabled: true
  other.plugin:
    enabled: false
```

3. **Use Logging Extensively:**
```python
try:
    log.log_info(f"Starting {self.meta.name}...")
    # Your code here
    log.log_info(f"Completed successfully")
except Exception as e:
    log.log_error(f"Failed: {e}")
    raise
```

4. **Test Version Compatibility:**
```python
# Check compatibility manually
info = PLUGIN.get_full_compatibility_info()
print(f"Plugin requirements: {info}")
```

## 7) Developer checklist

**Plugin Structure:**
- [ ] Valid package under `Plugins/<plugin_id>/` with `__init__.py`
- [ ] Global `PLUGIN` instance defined
- [ ] `bcasl_register(manager)` function defined
- [ ] Plugin ID is unique and descriptive

**Metadata:**
- [ ] All version requirements specified (bcasl, core, sdk, contexts)
- [ ] Appropriate tags assigned for execution order
- [ ] Clear description and author information
- [ ] Version follows semantic versioning

**Implementation:**
- [ ] `on_pre_compile(ctx)` implemented correctly
- [ ] Dialog instances created for logging and user interaction
- [ ] Robust error handling (raise to abort if necessary)
- [ ] Idempotent operations (safe to run multiple times)
- [ ] Long operations use progress dialogs with cancellation support
- [ ] File operations use `ctx.iter_files()` efficiently

**Testing:**
- [ ] Tested with various workspace configurations
- [ ] Tested with BCASL enabled and disabled
- [ ] Tested cancellation behavior
- [ ] Verified compatibility with current system versions
- [ ] No blocking UI operations

**Documentation:**
- [ ] Clear comments explaining plugin purpose
- [ ] Documented any special requirements or dependencies
- [ ] Examples of expected input/output

## Anti-patterns to Avoid

❌ **Don't:**
- Use i18n (internationalization) - plugins use static messages
- Block the UI thread with long synchronous operations
- Hardcode absolute paths
- Assume workspace structure without validation
- Ignore exceptions silently
- Rely on external dependencies not in stdlib
- Modify files without user confirmation
- Skip version compatibility requirements

✅ **Do:**
- Use `Dialog` for all user interaction and logging
- Implement progress dialogs for long operations
- Handle exceptions gracefully with informative messages
- Use `ctx.iter_files()` for file discovery
- Raise exceptions to abort build on critical failures
- Test plugin with various workspace configurations
- Follow semantic versioning for plugin updates
- Document plugin behavior clearly

## See Also

- [BCASL Configuration Guide](./BCASL_Configuration.md) - BC plugin configuration (file format and options)
- [ARK Configuration Guide](./ARK_Configuration.md) - Global configuration system (includes engine configuration)
- [About SDKs](./About_Sdks.md) - Overview of BC plugins vs engines
- [How to Create an Engine](./how_to_create_an_engine.md) - Creating compilation engines (PyInstaller, Nuitka, etc.)