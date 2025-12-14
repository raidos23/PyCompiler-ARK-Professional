# How to Create a BCASL Plugin

BCASL (Before-Compilation Actions System & Loader) is a modular plugin system for executing actions **before** compilation starts. It provides a robust framework for pre-compilation tasks like dependency checking, code generation, and project validation.

## Architecture Overview

BCASL provides:
- **Plugin Discovery**: Automatic loading from `Plugins/` directory at project root
- **Metadata & Decorators**: Attach metadata to plugins via `@plugin` decorator (optional)
- **Dependency Management**: Specify plugin dependencies and execution order
- **Priority-Based Execution**: Control execution order via priority values
- **Sandboxing**: Optional process isolation for plugin execution
- **Parallelism**: Execute independent plugins in parallel
- **Error Isolation**: One failing plugin doesn't block others
- **File Iteration**: Efficient glob-based file discovery with caching

## Plugin Structure

Each BCASL plugin is a Python package in `Plugins/<plugin_id>/` with:

```
Plugins/
└── my_plugin/
    ├── __init__.py          # Plugin implementation
    └── languages/           # Optional: i18n translations
        ├── en.json
        └── fr.json
```

## Creating a Plugin

### 1. Basic Plugin Template

Create `Plugins/my_plugin/__init__.py`:

```python
# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from Plugins_SDK import Bc_PluginBase, PluginMeta, PreCompileContext, wrap_context


# Define plugin metadata
BCASL_ID = "my_plugin"
BCASL_VERSION = "1.0.0"
BCASL_DESCRIPTION = "Does something useful before compilation"


class MyPlugin(Bc_PluginBase):
    """My BCASL plugin."""

    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        """Execute pre-compilation actions.
        
        Args:
            ctx: PreCompileContext with project info and file iteration
        """
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][my_plugin] {exc}")
            return

        sctx.log_info("🔍 My Plugin: Starting pre-compilation checks")
        
        # Your plugin logic here
        py_files = list(sctx.iter_files(["**/*.py"], exclude=["venv/**"]))
        sctx.log_info(f"📄 Found {len(py_files)} Python file(s)")
        
        sctx.log_info("✅ My Plugin: Complete")


# Create plugin metadata
META = PluginMeta(
    id=BCASL_ID,
    name="My Plugin",
    version=BCASL_VERSION,
    description=BCASL_DESCRIPTION,
    author="Your Name",
)

# Create plugin instance
PLUGIN = MyPlugin(meta=META)


# BCASL registration function (required)
def bcasl_register(manager):
    """Register this plugin with the BCASL manager."""
    manager.add_plugin(PLUGIN)
```

### 2. Alternative: Using the @plugin Decorator

If you prefer to use the `@plugin` decorator for quick metadata:

```python
from Plugins_SDK import Bc_PluginBase, PluginMeta, PreCompileContext, plugin, wrap_context


@plugin(id="my_plugin", version="1.0.0", description="Does something useful")
class MyPlugin(Bc_PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][my_plugin] {exc}")
            return
        
        sctx.log_info("Processing...")


# Create metadata manually
META = PluginMeta(
    id="my_plugin",
    name="My Plugin",
    version="1.0.0",
    description="Does something useful",
    author="Your Name",
)

# Create instance with dependencies and priority
PLUGIN = MyPlugin(
    meta=META,
    requires=[],           # List of plugin IDs this depends on
    priority=100,          # Lower = earlier execution
)


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

### 3. Plugin Metadata

The `PluginMeta` dataclass defines plugin information:

```python
PluginMeta(
    id="unique_id",              # Unique identifier (required)
    name="Display Name",         # Human-readable name
    version="1.0.0",            # Semantic version
    description="...",          # Short description
    author="Your Name",         # Optional author
)
```

### 4. Plugin Base Class

Extend `Bc_PluginBase` and implement `on_pre_compile()`:

```python
class MyPlugin(Bc_PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        # Your implementation
        pass
```

The constructor accepts:
- `meta: PluginMeta` - Plugin metadata
- `requires: Iterable[str]` - List of plugin IDs this depends on
- `priority: int` - Execution priority (lower = earlier)

### 5. PreCompileContext

The context passed to `on_pre_compile()` provides:

```python
class PreCompileContext:
    project_root: Path              # Project root directory
    config: dict[str, Any]          # Configuration
    
    def iter_files(
        self,
        include: Iterable[str],
        exclude: Iterable[str] = ()
    ) -> Iterable[Path]:
        """Iterate over project files with glob patterns.
        
        Args:
            include: Glob patterns to include (e.g., "**/*.py")
            exclude: Glob patterns to exclude (e.g., "venv/**")
            
        Returns:
            Iterator of Path objects
        """
```

### 6. Wrapped Context (SDKContext)

Use `wrap_context()` to get a unified SDK context with helpers:

```python
from Plugins_SDK import wrap_context

sctx = wrap_context(ctx)

# Access helpers
sctx.log_info("Message")
sctx.log_warn("Warning")
sctx.log_error("Error")
sctx.msg_info("Title", "Message")
sctx.msg_question("Title", "Question?", default_yes=True)
sctx.run_command(["ls", "-la"])
sctx.require_files(["main.py", "config.json"])
sctx.iter_files(["**/*.py"])
sctx.workspace_root  # Path to workspace
```

## Plugin Dependencies & Ordering

### Priority

Lower priority values execute first:

```python
PLUGIN = MyPlugin(
    meta=META,
    priority=50,   # Executes before priority=100
)
```

### Dependencies

Specify plugins that must execute before this one:

```python
PLUGIN = MyPlugin(
    meta=META,
    requires=["dependency_plugin_id"],  # Execute after dependency_plugin_id
    priority=100,
)
```

The system uses topological sorting to resolve execution order while respecting dependencies and priorities.

## Example: Dependency Checker Plugin

```python
from Plugins_SDK import Bc_PluginBase, PluginMeta, PreCompileContext, wrap_context


class DependencyChecker(Bc_PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][dep_checker] {exc}")
            return
        
        sctx.log_info("🔍 Checking dependencies...")
        
        # Check for requirements.txt
        req_file = sctx.workspace_root / "requirements.txt"
        if not req_file.exists():
            sctx.log_warn("⚠️ requirements.txt not found")
            return
        
        # Parse and validate
        try:
            with open(req_file) as f:
                deps = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            sctx.log_info(f"✅ Found {len(deps)} dependencies")
        except Exception as e:
            raise RuntimeError(f"Failed to parse requirements.txt: {e}")


META = PluginMeta(
    id="dep_checker",
    name="Dependency Checker",
    version="1.0.0",
    description="Check project dependencies",
)

PLUGIN = DependencyChecker(meta=META, priority=10)  # Run early


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

## Example: Code Generator Plugin

```python
from Plugins_SDK import Bc_PluginBase, PluginMeta, PreCompileContext, wrap_context
from pathlib import Path


class CodeGenerator(Bc_PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][codegen] {exc}")
            return
        
        sctx.log_info("🔨 Generating code...")
        
        # Find template files
        templates = list(sctx.iter_files(["**/*.template"]))
        sctx.log_info(f"Found {len(templates)} template(s)")
        
        for template_path in templates:
            output_path = template_path.with_suffix("")
            sctx.log_info(f"Generating {output_path.name}...")
            
            # Simple template processing
            with open(template_path) as f:
                content = f.read()
            
            # Replace placeholders
            content = content.replace("${PROJECT_NAME}", "MyProject")
            content = content.replace("${VERSION}", "1.0.0")
            
            with open(output_path, "w") as f:
                f.write(content)
        
        sctx.log_info(f"✅ Generated {len(templates)} file(s)")


META = PluginMeta(
    id="codegen",
    name="Code Generator",
    version="1.0.0",
    description="Generate code from templates",
)

PLUGIN = CodeGenerator(meta=META, priority=20)


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

## Example: Validator Plugin

```python
from Plugins_SDK import Bc_PluginBase, PluginMeta, PreCompileContext, wrap_context


class Validator(Bc_PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][validator] {exc}")
            return
        
        sctx.log_info("🔍 Validating project structure...")
        
        # Check required files
        required = ["main.py", "config.json"]
        missing = sctx.require_files(required)
        
        if missing:
            raise RuntimeError(f"Missing required files: {missing}")
        
        # Check Python syntax
        py_files = list(sctx.iter_files(["**/*.py"], exclude=["venv/**"]))
        sctx.log_info(f"Checking syntax of {len(py_files)} Python file(s)...")
        
        import ast
        for py_file in py_files:
            try:
                with open(py_file) as f:
                    ast.parse(f.read())
            except SyntaxError as e:
                raise RuntimeError(f"Syntax error in {py_file}: {e}")
        
        sctx.log_info("✅ Project validation passed")


META = PluginMeta(
    id="validator",
    name="Project Validator",
    version="1.0.0",
    description="Validate project structure and syntax",
)

PLUGIN = Validator(meta=META, priority=5)  # Run very early


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

## Plugin Configuration

Plugins can read configuration from workspace config files:

```python
def on_pre_compile(self, ctx: PreCompileContext) -> None:
    sctx = wrap_context(ctx)
    cfg = sctx.config_view
    
    # Get plugin-specific config
    subcfg = cfg.for_plugin(self.meta.id)
    my_option = subcfg.get("my_option", "default_value")
    
    # Get global config
    required_files = cfg.required_files or ["main.py"]
    exclude_patterns = cfg.exclude_patterns or []
```

## Internationalization (i18n)

Create `Plugins/my_plugin/languages/` with translation files:

```
Plugins/my_plugin/
├── __init__.py
└── languages/
    ├── en.json
    └── fr.json
```

`languages/en.json`:
```json
{
  "title": "My Plugin",
  "message": "Processing files...",
  "error": "An error occurred"
}
```

Load translations:

```python
from Plugins_SDK import load_plugin_translations
import asyncio


async def load_translations():
    tr = await load_plugin_translations(__file__, "en")
    return tr


def on_pre_compile(self, ctx: PreCompileContext) -> None:
    tr = asyncio.run(load_translations())
    sctx.log_info(tr.get("message", "Default message"))
```

## Sandboxing & Parallelism

BCASL supports optional sandboxing and parallel execution:

```python
from bcasl import BCASL, PreCompileContext

# Create manager with sandbox enabled
bcasl = BCASL(
    project_root,
    sandbox=True,           # Enable process isolation
    plugin_timeout_s=3.0,   # Timeout per plugin
)

# Load plugins
bcasl.load_plugins_from_directory(project_root / "Plugins")

# Run with parallelism
ctx = PreCompileContext(project_root)
report = bcasl.run_pre_compile(ctx)
```

Configuration via `bcasl.json` or environment:

```json
{
  "options": {
    "sandbox": true,
    "plugin_parallelism": 4,
    "plugin_timeout_s": 3.0
  }
}
```

Environment variables:
- `PYCOMPILER_BCASL_PARALLELISM=4` - Number of parallel workers
- `PYCOMPILER_NONINTERACTIVE_PLUGINS=1` - Disable interactive dialogs
- `PYCOMPILER_OFFSCREEN_PLUGINS=1` - Use offscreen rendering

## Best Practices

1. **Error Handling**: Always wrap in try-except to prevent blocking other plugins
2. **Logging**: Use `sctx.log_info()`, `log_warn()`, `log_error()` for visibility
3. **Idempotency**: Make operations safe to run multiple times
4. **Dependencies**: Clearly specify plugin dependencies
5. **Priority**: Use meaningful priority values (0-50 for early, 50-100 for normal, 100+ for late)
6. **Documentation**: Document what your plugin does and its configuration
7. **Testing**: Test with various project structures
8. **Performance**: Avoid heavy operations; use file iteration caching

## Plugin Discovery & Loading

BCASL automatically discovers plugins:

1. Scans `Plugins/` directory for subdirectories
2. Looks for `__init__.py` in each subdirectory
3. Imports the module and calls `bcasl_register(manager)`
4. Registers plugins via `manager.add_plugin(plugin)`

## API Reference

### BCASL Manager

```python
from bcasl import BCASL, PreCompileContext

# Create manager
bcasl = BCASL(project_root, sandbox=True)

# Load plugins
count, errors = bcasl.load_plugins_from_directory(project_root / "Plugins")

# List plugins
plugins = bcasl.list_plugins()

# Control plugins
bcasl.enable_plugin("my_plugin")
bcasl.disable_plugin("my_plugin")
bcasl.set_priority("my_plugin", 50)

# Execute
ctx = PreCompileContext(project_root)
report = bcasl.run_pre_compile(ctx)

# Check results
for item in report:
    print(f"{item.plugin_id}: {'✅' if item.success else '❌'}")
```

### ExecutionReport

```python
report = bcasl.run_pre_compile(ctx)

# Check overall status
if report.ok:
    print("All plugins succeeded")

# Get summary
print(report.summary())

# Iterate results
for item in report:
    print(f"{item.plugin_id}: {item.duration_ms}ms")
```

### SDKContext Helpers

```python
sctx = wrap_context(ctx)

# Logging
sctx.log_info("Info message")
sctx.log_warn("Warning message")
sctx.log_error("Error message")

# Messaging
sctx.msg_info("Title", "Message")
sctx.msg_question("Title", "Question?", default_yes=True)

# File operations
files = sctx.iter_files(["**/*.py"])
missing = sctx.require_files(["main.py"])

# Command execution
rc, out, err = sctx.run_command(["python", "--version"])

# Configuration
cfg = sctx.config_view
subcfg = cfg.for_plugin("my_plugin")
value = subcfg.get("key", "default")

# Workspace access
workspace = sctx.workspace_root
```

## Troubleshooting

### Plugin not loading
- Check `__init__.py` exists in plugin directory
- Verify `bcasl_register()` function is defined
- Check logs for import errors
- Ensure plugin is in `Plugins/` directory, not `API/`

### Plugin not executing
- Verify plugin is enabled in configuration
- Check dependencies are satisfied
- Look for exceptions in logs

### Execution order wrong
- Check `priority` values (lower = earlier)
- Verify `requires` dependencies
- Check for circular dependencies

### Sandbox issues
- Check `PYCOMPILER_NONINTERACTIVE_PLUGINS` environment variable
- Verify plugin doesn't require interactive dialogs
- Check resource limits in configuration

## See Also

- [ACASL Plugin Development](how_to_create_an_acasl_plugin.md)
- [Plugins_SDK Documentation](../Plugins_SDK/__init__.py)
- [Building Engines](how_to_create_a_building_engine.md)
- [Configuration Guide](../README.md)
