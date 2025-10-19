# How to Create an ACASL Plugin

ACASL (After-Compilation Actions System & Loader) is a modular plugin system for executing actions **after** compilation completes. It's inspired by BCASL but tailored for post-compilation tasks like cleanup, optimization, and artifact transformation.

## Architecture Overview

ACASL provides:
- **Plugin Discovery**: Automatic loading from `Plugins/` directory at project root
- **Metadata & Tags**: Classify plugins with tags (e.g., "cleanup", "optimization")
- **Dependency Management**: Specify plugin dependencies and execution order
- **Priority-Based Execution**: Control execution order via priority values
- **Error Isolation**: One failing plugin doesn't block others
- **Artifact Access**: Direct access to compiled artifacts and project files

## Plugin Structure

Each ACASL plugin is a Python package in `Plugins/<plugin_id>/` with:

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

from API_SDK.ACASL_SDK import Ac_PluginBase, PluginMeta, PostCompileContext, wrap_post_context


# Define plugin metadata
META = PluginMeta(
    id="my_plugin",
    name="My Plugin",
    version="1.0.0",
    description="Does something useful after compilation",
    author="Your Name",
    tags=("cleanup", "optimization"),  # Tags for classification
)


class MyPlugin(Ac_PluginBase):
    """My ACASL plugin."""

    def on_post_compile(self, ctx: PostCompileContext) -> None:
        """Execute post-compilation actions.
        
        Args:
            ctx: PostCompileContext with artifacts and project info
        """
        try:
            sctx = wrap_post_context(ctx)
        except Exception as exc:
            print(f"[ERROR][my_plugin] {exc}")
            return

        sctx.log_info("��� My Plugin: Starting post-compilation processing")
        
        # Your plugin logic here
        artifacts = list(ctx.iter_artifacts())
        sctx.log_info(f"📦 Found {len(artifacts)} artifact(s)")
        
        sctx.log_info("✅ My Plugin: Complete")


# Create plugin instance
PLUGIN = MyPlugin(
    meta=META,
    requires=[],           # List of plugin IDs this depends on
    priority=100,          # Lower = earlier execution
)


# ACASL registration function (required)
def acasl_register(manager):
    """Register this plugin with the ACASL manager."""
    manager.add_plugin(PLUGIN)
```

### 2. Plugin Metadata

The `PluginMeta` dataclass defines plugin information:

```python
PluginMeta(
    id="unique_id",              # Unique identifier (required)
    name="Display Name",         # Human-readable name
    version="1.0.0",            # Semantic version
    description="...",          # Short description
    author="Your Name",         # Optional author
    tags=("tag1", "tag2"),      # Tags for classification
)
```

**Tags** are used to classify and filter plugins:
- `"cleanup"` - Cleanup operations
- `"optimization"` - Performance optimization
- `"packaging"` - Artifact packaging
- `"validation"` - Post-compile validation
- `"custom"` - Custom tags

### 3. Plugin Base Class

Extend `Ac_PluginBase` and implement `on_post_compile()`:

```python
class MyPlugin(Ac_PluginBase):
    def on_post_compile(self, ctx: PostCompileContext) -> None:
        # Your implementation
        pass
```

The constructor accepts:
- `meta: PluginMeta` - Plugin metadata
- `requires: Iterable[str]` - List of plugin IDs this depends on
- `priority: int` - Execution priority (lower = earlier)

### 4. PostCompileContext

The context passed to `on_post_compile()` provides:

```python
class PostCompileContext:
    project_root: Path              # Project root directory
    artifacts: list[str]            # Compiled artifact paths
    output_dir: Optional[str]       # Engine output directory
    config: dict[str, Any]          # Configuration
    
    def iter_artifacts(
        self,
        include: Iterable[str] = (),
        exclude: Iterable[str] = ()
    ) -> Iterable[Path]:
        """Iterate over artifacts with glob patterns."""
        
    def iter_files(
        self,
        include: Iterable[str],
        exclude: Iterable[str] = ()
    ) -> Iterable[Path]:
        """Iterate over project files with glob patterns."""
```

### 5. Wrapped Context (SDKContext)

Use `wrap_post_context()` to get a unified SDK context:

```python
from API_SDK.ACASL_SDK import wrap_post_context

sctx = wrap_post_context(ctx)

# Access helpers
sctx.log_info("Message")
sctx.log_warn("Warning")
sctx.log_error("Error")
sctx.msg_info("Title", "Message")
sctx.run_command(["ls", "-la"])
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
    requires=["other_plugin_id"],  # Execute after other_plugin_id
    priority=100,
)
```

The system uses topological sorting to resolve execution order while respecting dependencies and priorities.

## Example: Cleanup Plugin

```python
from API_SDK.ACASL_SDK import Ac_PluginBase, PluginMeta, PostCompileContext, wrap_post_context
import shutil
from pathlib import Path


META = PluginMeta(
    id="cleanup",
    name="Cleanup",
    version="1.0.0",
    description="Clean temporary files after compilation",
    tags=("cleanup",),
)


class CleanupPlugin(Ac_PluginBase):
    def on_post_compile(self, ctx: PostCompileContext) -> None:
        sctx = wrap_post_context(ctx)
        sctx.log_info("🧹 Cleaning temporary files...")
        
        # Clean build artifacts
        build_dir = ctx.project_root / "build"
        if build_dir.exists():
            shutil.rmtree(build_dir)
            sctx.log_info(f"Removed {build_dir}")
        
        sctx.log_info("✅ Cleanup complete")


PLUGIN = CleanupPlugin(meta=META, priority=100)


def acasl_register(manager):
    manager.add_plugin(PLUGIN)
```

## Example: Validation Plugin

```python
from API_SDK.ACASL_SDK import Ac_PluginBase, PluginMeta, PostCompileContext, wrap_post_context


META = PluginMeta(
    id="validator",
    name="Validator",
    version="1.0.0",
    description="Validate compiled artifacts",
    tags=("validation",),
)


class ValidatorPlugin(Ac_PluginBase):
    def on_post_compile(self, ctx: PostCompileContext) -> None:
        sctx = wrap_post_context(ctx)
        sctx.log_info("🔍 Validating artifacts...")
        
        artifacts = list(ctx.iter_artifacts())
        if not artifacts:
            raise RuntimeError("No artifacts found!")
        
        for art in artifacts:
            if art.stat().st_size == 0:
                raise RuntimeError(f"Empty artifact: {art}")
        
        sctx.log_info(f"✅ Validated {len(artifacts)} artifact(s)")


PLUGIN = ValidatorPlugin(meta=META, priority=50)  # Run early


def acasl_register(manager):
    manager.add_plugin(PLUGIN)
```

## Plugin Configuration

Plugins can read configuration from `acasl.json`:

```json
{
  "plugins": {
    "my_plugin": {
      "enabled": true,
      "priority": 100
    }
  },
  "plugin_order": ["my_plugin"],
  "options": {
    "enabled": true,
    "plugin_timeout_s": 0.0
  }
}
```

Access configuration:

```python
def on_post_compile(self, ctx: PostCompileContext) -> None:
    sctx = wrap_post_context(ctx)
    cfg = sctx.config_view
    subcfg = cfg.for_plugin(self.id)
    
    my_option = subcfg.get("my_option", "default_value")
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
  "message": "Processing artifacts..."
}
```

Load translations:

```python
from API_SDK.ACASL_SDK import load_plugin_translations
import asyncio

async def load_translations():
    tr = await load_plugin_translations(__file__, "en")
    return tr

def on_post_compile(self, ctx: PostCompileContext) -> None:
    tr = asyncio.run(load_translations())
    sctx.log_info(tr.get("message", "Default message"))
```

## Best Practices

1. **Error Handling**: Always wrap in try-except to prevent blocking other plugins
2. **Logging**: Use `sctx.log_info()`, `log_warn()`, `log_error()` for visibility
3. **Idempotency**: Make operations safe to run multiple times
4. **Dependencies**: Clearly specify plugin dependencies
5. **Tags**: Use meaningful tags for plugin classification
6. **Documentation**: Document what your plugin does and its configuration
7. **Testing**: Test with various artifact types and project structures

## Plugin Discovery & Loading

ACASL automatically discovers plugins:

1. Scans `Plugins/` directory for subdirectories
2. Looks for `__init__.py` in each subdirectory
3. Imports the module and calls `acasl_register(manager)`
4. Registers plugins via `manager.add_plugin(plugin)`

## API Reference

### ACASL Manager

```python
from acasl import ACASL, PostCompileContext

# Create manager
acasl = ACASL(project_root)

# Load plugins
count, errors = acasl.load_plugins_from_directory(project_root / "Plugins")

# List plugins
plugins = acasl.list_plugins(tag_filter="cleanup")

# Control plugins
acasl.enable_plugin("my_plugin")
acasl.disable_plugin("my_plugin")
acasl.set_priority("my_plugin", 50)

# Execute
ctx = PostCompileContext(project_root, artifacts=[...])
report = acasl.run_post_compile(ctx)

# Check results
for item in report:
    print(f"{item.plugin_id}: {'✅' if item.success else '❌'}")
```

### ExecutionReport

```python
report = acasl.run_post_compile(ctx)

# Check overall status
if report.ok:
    print("All plugins succeeded")

# Get summary
print(report.summary())

# Filter by tag
cleanup_results = report.by_tag("cleanup")

# Iterate results
for item in report:
    print(f"{item.plugin_id}: {item.duration_ms}ms")
```

## Troubleshooting

### Plugin not loading
- Check `__init__.py` exists in plugin directory
- Verify `acasl_register()` function is defined
- Check logs for import errors

### Plugin not executing
- Verify plugin is enabled in `acasl.json`
- Check dependencies are satisfied
- Look for exceptions in logs

### Execution order wrong
- Check `priority` values (lower = earlier)
- Verify `requires` dependencies
- Check for circular dependencies

## See Also

- [BCASL Plugin Development](how_to_create_a_bcasl_API.md)
- [API_SDK Documentation](about_sdks.md)
- [Configuration Guide](../README.md)
