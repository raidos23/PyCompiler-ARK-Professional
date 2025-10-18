# How to Create a BCASL API Plugin (Updated)

Author: Samuel Amen Ague
License: GPL-3.0-only

Quick Navigation
- [TL;DR](#tldr-copy-paste-template)
- [Checklist](#1-quick-checklist)
- [Layout](#2-folder-layout)
- [Minimal plugin](#3-minimal-plugin-with-metadata)
- [Tags](#4-tag-taxonomy-and-default-ordering-minify-before-obfuscation)
  - [Why tags matter](#why-tags-matter)
- [Progress](#5-progress-and-non-interactive-considerations)
- [Configuration](#6-configuration-patterns)
- [System installs (6.1)](#61-system-install-helpers-pip-global--package-managers)
- [Context](#7-context-essentials)
- [i18n](#8-i18n-async)
- [Workspace](#9-workspace-switching-safe)
- [Examples](#10-examples)
- [Troubleshooting](#11-troubleshooting)

This guide explains how to implement a pre‑compile (BCASL) plugin for PyCompiler ARK++ using the namespaced API_SDK.BCASL_SDK.

Highlights (what changed)
- Extended plugin metadata: declare BCASL_NAME, BCASL_VERSION, BCASL_AUTHOR, BCASL_CREATED, BCASL_LICENSE, BCASL_COMPATIBILITY, BCASL_TAGS.
- Tag‑based default ordering: the host prioritizes plugins by tags (e.g., clean → validation → prepare → license → lint → minify → obfuscation → packaging → manifest → docs → publish). Minification is automatically prioritized before obfuscation.
- Non‑interactive safety: plugins must avoid blocking the UI and cooperate with headless/non‑interactive mode.
- System install helpers: standardized helpers to install Python packages system‑wide (pip) and native packages (apt/dnf/pacman/zypper/winget/choco/brew) with user consent.
- Better examples: minimal plugin, minifier sample, obfuscation sample, and system installs sample.

Strict rules (BCASL package signature)

> IMPORTANT: BCASL plugins must always live under API/<plugin_id>/ as Python packages (folder with an __init__.py). Paths such as bcasl/<plugin_id>/ or acasl/<plugin_id>/ are invalid and will not be discovered.
- Your plugin must be a Python package under API/<plugin_id>/ with an __init__.py (not under acasl/ or bcasl/).
- In __init__.py, declare at least:
  - BCASL_PLUGIN = True
  - BCASL_ID = "your_id"
  - BCASL_DESCRIPTION = "short description"
- New recommended metadata (parsed by the loader UI and used for UX and default ordering):
  - BCASL_NAME, BCASL_VERSION, BCASL_AUTHOR, BCASL_CREATED, BCASL_LICENSE
  - BCASL_COMPATIBILITY: list[str]
  - BCASL_TAGS: list[str] (see Tag taxonomy below)

Imports (facade)
- Prefer the BCASL facade for a stable surface:
  from API_SDK.BCASL_SDK import PluginBase, PluginMeta, PreCompileContext, wrap_context, ensure_min_sdk, progress, ensure_settings_file, ensure_system_pip_install, ensure_system_packages
- Decorator (compat):
  try: from API_SDK.BCASL_SDK import plugin
  except: from API_SDK import plugin

Table of contents
- 0) TL;DR template
- 1) Quick checklist
- 2) Folder layout
- 3) Minimal plugin (with metadata)
- 4) Tag taxonomy and default ordering (minify before obfuscation)
- 5) Progress and non‑interactive considerations
- 6) Configuration patterns
- 6.1) System install helpers (pip global + package managers)
- 7) Context essentials (safe paths, scans)
- 8) i18n (async)
- 9) Workspace switching (safe)
- 10) Examples
  - A) Minifier (ordered before obfuscation via tags)
  - B) Obfuscation (ordered after minify via tags)
  - C) System installs: native pkgs and pip
- 11) Troubleshooting

---

## 0) TL;DR (copy‑paste template) {#0-tldr-copy-paste-template}

```python
# API/my_plugin/__init__.py
from __future__ import annotations
from API_SDK.BCASL_SDK import (
    PluginBase, PluginMeta, PreCompileContext, wrap_context,
    ensure_min_sdk, progress, ensure_settings_file,
    ensure_system_pip_install, ensure_system_packages,
)
try:
    from API_SDK.BCASL_SDK import plugin  # preferred
except Exception:  # fallback for older SDKs
    from API_SDK import plugin

# Mandatory BCASL package signature
BCASL_PLUGIN = True
BCASL_ID = "my_plugin"
BCASL_DESCRIPTION = "My plugin"

# Extended metadata (recommended)
BCASL_NAME = "MyPlugin"
BCASL_VERSION = "0.1.0"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_LICENSE = "GPL-3.0-only"
BCASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
BCASL_TAGS = ["prepare", "validation"]

@plugin(id=BCASL_ID, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
class MyPlugin(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        if not ensure_min_sdk("3.2.3"):
            raise RuntimeError("API_SDK >= 3.2.3 required")
        sctx = wrap_context(ctx)
        sctx.log_info("Starting my plugin…")
        # Do work here
        sctx.log_info("Done")

META = PluginMeta(id=BCASL_ID, name=BCASL_NAME, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
PLUGIN = MyPlugin(META)

def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

---

## 1) Quick checklist {#1-quick-checklist}
- [ ] Package under API/<plugin_id>/ with __init__.py
- [ ] BCASL signature: BCASL_PLUGIN=True, BCASL_ID, BCASL_DESCRIPTION
- [ ] Extended metadata (recommended): NAME, VERSION, AUTHOR, CREATED, LICENSE, COMPATIBILITY, TAGS
- [ ] Use @plugin decorator + bcasl_register(manager)
- [ ] Guard with ensure_min_sdk("3.2.3") if using new features
- [ ] Use progress(...) for long tasks; never block the UI thread
- [ ] Respect non‑interactive mode (avoid modal prompts if headless)
- [ ] Favor sctx.safe_path and sctx.write_text_atomic for file IO
- [ ] Narrow file_patterns/exclude_patterns for performance

---

## 2) Folder layout {#2-folder-layout}

Place plugins exclusively under API/<plugin_id>/ (never under acasl/ or bcasl/):
```
<project root>
└── API/
    └── my_plugin/
        └── __init__.py
```

---

## 3) Minimal plugin (with metadata) {#3-minimal-plugin-with-metadata}

```python
from __future__ import annotations
from API_SDK.BCASL_SDK import (
    PluginBase, PluginMeta, PreCompileContext, wrap_context,
    ensure_min_sdk, progress
)
try:
    from API_SDK.BCASL_SDK import plugin
except Exception:
    from API_SDK import plugin

BCASL_PLUGIN = True
BCASL_ID = "hello_world"
BCASL_DESCRIPTION = "Example plugin"

BCASL_NAME = "HelloWorld"
BCASL_VERSION = "0.1.0"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_LICENSE = "GPL-3.0-only"
BCASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
BCASL_TAGS = ["docs", "tests"]

@plugin(id=BCASL_ID, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
class HelloWorld(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        if not ensure_min_sdk("3.2.3"):
            raise RuntimeError("API_SDK >= 3.2.3 required")
        sctx = wrap_context(ctx)
        sctx.msg_info("Hello", "Your plugin is running!")

META = PluginMeta(id=BCASL_ID, name=BCASL_NAME, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
PLUGIN = HelloWorld(META)

def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

---

## 4) Tag taxonomy and default ordering (minify before obfuscation) {#4-tag-taxonomy-and-default-ordering-minify-before-obfuscation}

The host computes a default order from BCASL_TAGS (no IDs are hard‑coded):
- clean, cleanup, sanitize, prune, tidy → earliest
- validation, presence, sanity, policy, requirements, check, audit, scan, security, sast, compliance, license-check
- tests (unit/integration)
- prepare, codegen, generate, fetch, resources, download, install, bootstrap, configure
- license, header, normalize, inject, spdx, banner, copyright
- lint, format, typecheck (mypy), flake8/ruff/pep8
- minify, uglify, shrink, compress-code (minification runs before obfuscation)
- obfuscation, obfuscate, transpile, protect, encrypt
- package, packaging, bundle, archive, compress, zip
- manifest, version, metadata, bump, changelog
- docs, documentation, generate-docs
- publish, deploy, release (rare in BCASL)

Notes:
- Using tags improves default ordering and UX; the user remains free to override order in bcasl.* or via the UI.
- Absence of tags falls back to textual heuristics on name/description with the same taxonomy.

### Why tags matter
- Drive default ordering deterministically across projects and workspaces.
- Prevent anti-patterns like running obfuscation before minification or packaging before validation.
- Improve the UI: grouping, filtering, and tooltips leverage tags to present clearer pipelines.
- Reduce manual configuration: fewer per-workspace overrides and fewer ordering mistakes.
- Aid onboarding: contributors understand intent and stage from tags at a glance.

Recommended baseline tags by stage:
- Early: clean, validation
- Prepare: prepare, resources, configure, codegen
- Quality: lint, format, typecheck
- Transform: minify, obfuscation
- Package: packaging, bundle, archive
- Meta: manifest, version, docs
- Delivery: publish, release

---

## 5) Progress and non‑interactive considerations {#5-progress-and-non-interactive-considerations}

- Always use progress(...) for long operations; it is non‑blocking and UI‑safe.
- Ask confirmation only when interactive. Detect non‑interactive mode (best‑effort):
  try: noninteractive = bool(getattr(sctx, "noninteractive", False) or getattr(sctx, "is_noninteractive", False))
  except: noninteractive = False
- If noninteractive: avoid QMessageBox.question; log a warning or proceed with safe defaults.

Example (guarded prompt):
```python
# Don't block UI or headless runs
ask = False
try:
    noninteractive = bool(getattr(sctx, "noninteractive", False) or getattr(sctx, "is_noninteractive", False))
    ask = not noninteractive
except Exception:
    ask = True
if ask and not sctx.msg_question("Proceed?", "Run heavy step now?", default_yes=False):
    sctx.log_warn("Step canceled by user")
    return
```

---

## 6) Configuration patterns {#6-configuration-patterns}

- Workspace config (bcasl.*) can be JSON/YAML/TOML/INI/CFG; the UI can create and edit it.
- Per‑plugin settings: use ensure_settings_file(...) to materialize a user‑editable file under the workspace.

```python
from API_SDK.BCASL_SDK import ensure_settings_file
settings = ensure_settings_file(sctx, subdir="config", basename="my_plugin", fmt="yaml", defaults={"enabled": True})
```

---

## 6.1) System install helpers (pip global + package managers) {#61-system-install-helpers-pip-global--package-managers}

- Use the standardized helpers to request consent and install dependencies system‑wide.
- In non‑interactive mode these helpers return False and skip installation safely.

Install Python tools globally (pip):
```python
from API_SDK.BCASL_SDK import ensure_system_pip_install
ok = ensure_system_pip_install(
    sctx,
    ["mypy"],
    title="Install Python tool",
    body="Install 'mypy' system-wide now?",
    python_candidates=["/usr/bin/python3", "python3", "python"],
    timeout_s=600,
)
if not ok:
    sctx.log_warn("mypy not installed; skipping type checks")
    return
```

Install native packages via OS manager (Linux/Windows/macOS):
```python
from API_SDK.BCASL_SDK import ensure_system_packages
ok = ensure_system_packages(
    sctx,
    ["patchelf", "p7zip-full"],
    title="Install native tools",
    body="Install 'patchelf' and 'p7zip' with your system package manager?",
)
if not ok:
    sctx.log_warn("Native tools missing; skipping packaging step")
    return
```

---

## 7) Context essentials {#7-context-essentials}

- Safe paths: sctx.safe_path(rel_or_abs) and sctx.is_within_workspace(Path)
- Scans: sctx.iter_files(patterns=[...], exclude=[...], enforce_workspace=True)
- Atomic writes: sctx.write_text_atomic(path, text)
- Parallel: sctx.parallel_map(func, iterable)

---

## 8) i18n (async) {#8-i18n-async}

Goal
- Ship a languages/ folder with your plugin so UI strings are localized.
- Load translations at runtime with the SDK helper and always provide safe English fallbacks.
- Use string placeholders and tr.get(...) consistently, as illustrated in API/cleaner.

Folder layout
```
API/
  └── my_plugin/
      ├── __init__.py
      └── languages/
          ├── en.json
          ├── fr.json
          ├── es.json
          └── de.json
```

Minimal en.json (example keys)
```json
{
  "_meta": { "code": "en", "name": "English" },
  "title": "MyPlugin",
  "start": "Starting {plugin}…",
  "done": "Done",
  "confirm_run": "Run this step now?",
  "canceled": "Canceled by user",
  "error_fmt": "Error: {error}"
}
```

Loading translations (async helper)
```python
import asyncio
from API_SDK.BCASL_SDK import load_plugin_translations

# Language can be a code ("en", "fr" …) or "System" for auto-detection
tr = asyncio.run(load_plugin_translations(__file__, "System")) or {}
```

Using translations with robust fallbacks and placeholders
```python
# Always provide an English fallback when using tr.get
sctx.log_info(tr.get("start", "Starting {plugin}…").format(plugin=BCASL_NAME))

# Guarded prompt (respect non-interactive mode)
noninteractive = bool(getattr(sctx, "noninteractive", False) or getattr(sctx, "is_noninteractive", False))
if (not noninteractive):
    if not sctx.msg_question(tr.get("title", BCASL_NAME), tr.get("confirm_run", "Run this step now?"), default_yes=False):
        sctx.log_warn(tr.get("canceled", "Canceled by user"))
        return

# Formatting example for errors
try:
    ...
except Exception as e:
    sctx.log_warn(tr.get("error_fmt", "Error: {error}").format(error=e))
```

Keys and conventions (inspired by API/cleaner)
- Use explicit, short keys: title, confirm_*, progress_*, *_fmt for formatted messages.
- Keep placeholders explicit and named (e.g., {file}, {error}, {current}, {total}).
- Provide a complete en.json as the baseline and add locales incrementally (fr, es, de …).
- For progress handles, update text with translated strings and placeholders:
  - tr.get("deleting_pyc", "Deleting .pyc ({current}/{total})").format(current=i, total=n)

Best practices
- Do not block UI for i18n; loading JSON is local I/O.
- Normalize the language via the SDK helper (System auto-detect). Keep values UTF-8.
- Keep English as the code fallback when a key is missing.
- Avoid string concatenation; prefer .format with named placeholders.

Complete pattern (typical flow)
```python
from API_SDK.BCASL_SDK import progress
tr = asyncio.run(load_plugin_translations(__file__, "System")) or {}

with progress(tr.get("title", BCASL_NAME), tr.get("start", "Starting {plugin}…").format(plugin=BCASL_NAME), maximum=1) as ph:
    # … work …
    ph.update(1, tr.get("done", "Done"))
    sctx.log_info(tr.get("done", "Done"))
```

---

## 9) Workspace switching (safe) {#9-workspace-switching-safe}

```python
from API_SDK import set_selected_workspace
ok = set_selected_workspace("/path/to/project")
if ok:
    sctx = wrap_context(ctx)
```

---

## 10) Examples {#10-examples}

A) Minifier (minify before obfuscation via tags)
```python
# API/minifier/__init__.py
from __future__ import annotations
from API_SDK.BCASL_SDK import (
    PluginBase, PluginMeta, PreCompileContext, wrap_context,
    ensure_min_sdk, progress
)
try:
    from API_SDK.BCASL_SDK import plugin
except Exception:
    from API_SDK import plugin

BCASL_PLUGIN = True
BCASL_ID = "minifier"
BCASL_DESCRIPTION = "Minify Python sources"
BCASL_NAME = "Minifier"
BCASL_VERSION = "0.1.0"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_LICENSE = "GPL-3.0-only"
BCASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
BCASL_TAGS = ["minify", "shrink"]  # ensures it runs before obfuscation by default

@plugin(id=BCASL_ID, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
class Minifier(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        if not ensure_min_sdk("3.2.3"):
            raise RuntimeError("API_SDK >= 3.2.3 required")
        sctx = wrap_context(ctx)
        # example: just log; replace with a real minification logic
        with progress("Minifier", "Minifying...", maximum=1) as ph:
            # ... your minify steps ...
            ph.update(1, "Done")
        sctx.log_info("minifier: completed")

META = PluginMeta(id=BCASL_ID, name=BCASL_NAME, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
PLUGIN = Minifier(META)

def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

B) Obfuscation (after minify via tags)
```python
# API/obfuscation_demo/__init__.py
from __future__ import annotations
from API_SDK.BCASL_SDK import PluginBase, PluginMeta, PreCompileContext, wrap_context, ensure_min_sdk, progress
try:
    from API_SDK.BCASL_SDK import plugin
except Exception:
    from API_SDK import plugin

BCASL_PLUGIN = True
BCASL_ID = "obfuscation_demo"
BCASL_DESCRIPTION = "Obfuscate sources after minification"
BCASL_NAME = "ObfuscationDemo"
BCASL_VERSION = "0.1.0"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_LICENSE = "GPL-3.0-only"
BCASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
BCASL_TAGS = ["obfuscation", "protect"]  # runs after minify by default

@plugin(id=BCASL_ID, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
class ObfuscationDemo(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        if not ensure_min_sdk("3.2.3"):
            raise RuntimeError("API_SDK >= 3.2.3 required")
        sctx = wrap_context(ctx)
        with progress("Obfuscation", "Obfuscating...", maximum=1) as ph:
            # ... your obfuscation steps ...
            ph.update(1, "Done")
        sctx.log_info("obfuscation_demo: completed")

META = PluginMeta(id=BCASL_ID, name=BCASL_NAME, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
PLUGIN = ObfuscationDemo(META)

def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

C) System installs: native pkgs and pip
```python
# API/setup_tools/__init__.py
from __future__ import annotations
from API_SDK.BCASL_SDK import (
    PluginBase, PluginMeta, PreCompileContext, wrap_context,
    ensure_min_sdk, progress, ensure_system_pip_install, ensure_system_packages,
)
try:
    from API_SDK.BCASL_SDK import plugin
except Exception:
    from API_SDK import plugin

BCASL_PLUGIN = True
BCASL_ID = "setup_tools"
BCASL_DESCRIPTION = "Ensure native and Python tools are installed system-wide"
BCASL_NAME = "SetupTools"
BCASL_VERSION = "0.1.0"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_LICENSE = "GPL-3.0-only"
BCASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
BCASL_TAGS = ["prepare", "validation"]

@plugin(id=BCASL_ID, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
class SetupTools(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        if not ensure_min_sdk("3.2.3"):
            raise RuntimeError("API_SDK >= 3.2.3 required")
        sctx = wrap_context(ctx)

        # 1) Native packages (Linux/Windows/macOS)
        if not ensure_system_packages(
            sctx,
            ["patchelf", "p7zip-full"],
            title="Install native tools",
            body="Install 'patchelf' and 'p7zip' with your system package manager?",
        ):
            sctx.log_warn("Native tools missing; skipping this step")
            return

        # 2) Global Python tools via pip (mypy as example)
        if not ensure_system_pip_install(
            sctx,
            ["mypy"],
            title="Install Python tool",
            body="Install 'mypy' system-wide now?",
            python_candidates=["/usr/bin/python3", "python3", "python"],
        ):
            sctx.log_warn("mypy not installed; skipping type checks")
            return

        sctx.log_info("System prerequisites ensured")

META = PluginMeta(id=BCASL_ID, name=BCASL_NAME, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
PLUGIN = SetupTools(META)

def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
```

---

## 11) Troubleshooting {#11-troubleshooting}
- Plugin not visible → ensure BCASL_PLUGIN/ID/DESCRIPTION exist; it's under API/<plugin_id>/ (not under acasl/ or bcasl/); use @plugin; register via bcasl_register; open API Loader; check logs
- Config invalid → use UI raw editor; validate formats; fall back to JSON
- Long operations → use progress; split work; no modal blocking in background
- Ordering not as expected → add/adjust BCASL_TAGS (e.g., "minify", "obfuscation") or override order in the UI
- Missing tools → use ensure_system_packages and/or ensure_system_pip_install to request consent and install prerequisites
- SDK too old → ensure_min_sdk("3.2.3"); inspect capabilities via sdk_info()/get_capabilities()

Happy building!
