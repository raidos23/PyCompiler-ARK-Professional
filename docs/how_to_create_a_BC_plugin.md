# How to Create a BCASL Plugin

This guide explains how to implement a pre‑compilation plugin (BCASL) for PyCompiler ARK++ using the Plugins_SDK.

## Quick Navigation
- [TL;DR](#0-tldr-copy-paste-template)
- [Folder layout](#1-folder-layout)
- [Minimal plugin](#2-minimal-plugin)
- [Metadata and dependencies](#3-metadata-and-dependencies)
- [i18n](#4-internationalization)
- [Testing and logging](#5-testing-and-logging)
- [Checklist](#6-developer-checklist)

## 0) TL;DR (copy‑paste template)

Create `Plugins/my.plugin.id/__init__.py`:

```python
from __future__ import annotations

from Plugins_SDK.BcPluginContext import PluginMeta, BcPluginBase, PreCompileContext

META = PluginMeta(
    id="my.plugin.id",
    name="My BC Plugin",
    version="0.1.0",
    description="Describe what this BC plugin does before compilation.",
    author="Your Name",
    tags=("check",),   # e.g. ("clean", "check", "optimize", "prepare", ...)
)

class MyPlugin(BcPluginBase):
    def __init__(self) -> None:
        super().__init__(meta=META, requires=(), priority=100)

    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        # Example: ensure at least one Python file exists in workspace
        files = list(ctx.iter_files(["*.py"], []))
        if not files:
            raise RuntimeError("No Python files found in workspace")
        # Perform additional preparation.

PLUGIN = MyPlugin()
```

## 1) Folder layout

```
<project root>
└── Plugins/
    └── my.plugin.id/
        ├── __init__.py
        └── languages/
            ├── en.json
            ├── fr.json
            └── es.json
```

- The plugin package must be importable (contains `__init__.py`)
- The global variable `PLUGIN` should point to an instance of your plugin class

## 2) Minimal plugin

- Inherit from `BcPluginBase`
- Provide `META` (PluginMeta) and pass it to the base initializer
- Implement `on_pre_compile(self, ctx: PreCompileContext)`
- Raise an exception to abort the build when a blocking condition is met

## 3) Metadata and dependencies

- `PluginMeta` fields:
  - `id` (unique), `name`, `version`, `description`, `author`
  - `tags`: used for ordering (e.g., `("clean",)`, `("check",)`, `("optimize",)`)
- `requires`: tuple of plugin ids that must run before this plugin
- `priority`: smaller numbers run earlier (used when tags are equal)

## 4) Internationalization

- Place JSON translation files under `languages/`
- Always include `en.json` as the fallback
- Use `apply_i18n(gui, tr)` in your plugin to update UI if any is exposed

Example `languages/en.json`:
```json
{
  "_meta": {"code": "en", "name": "English"},
  "title": "My BC Plugin",
  "question": "Proceed with pre‑build checks?"
}
```

## 5) Testing and logging

- Use the GUI log (`gui.log.append(...)`) to provide feedback when applicable
- Ensure code is idempotent and resilient to being called multiple times
- Avoid blocking the UI thread; long operations should be asynchronous

## 6) Developer checklist

- [ ] Valid package under `Plugins/<plugin_id>/`
- [ ] Global `PLUGIN` instance
- [ ] `on_pre_compile()` implemented and safe
- [ ] Robust error handling (raise to abort build if necessary)
- [ ] i18n files with `en.json` fallback
- [ ] Clear logs for users

