# How to create an ACASL API (After Compilation Advanced System Loader) — Updated

Author: Samuel Amen Ague
License: GPL-3.0-only

Quick Navigation
- [What is ACASL?](#what-is-acasl)
- [Execution flow](#execution-flow-and-integration)
- [Output directory policy](#output-directory-policy)
- [Package layout](#where-to-place-your-plugins-package-layout)
- [Templates](#plugin-templates)
- [SDK facade & Context](#acasl-sdk-facade-and-context-available-api)
- [Configuration](#configuration-acasljson)
- [System installs](#system-installs-pip-global-and-os-package-managers)
- [UI: ACASL Loader](#ui-acasl-loader-enable-and-order-plugins)
- [Cancellation & robustness](#cancellation-and-robustness)
- [i18n (plugin-local + core)](#i18n-plugin-local--core)
- [Best practices](#best-practices-security-ux-logs)
- [Troubleshooting](#troubleshooting)
- [Extended examples](#extended-examples-rich-collection)
- [Recap](#recap)

This guide explains how to write, configure, and run ACASL plugins that operate on build artifacts after compilation (post‑build). Typical use cases include code signing, notarization, packaging installers, integrity checks, SBOM generation, hashing, smoke tests, and publishing releases.

Highlights (what changed)
- Orchestrated output opening: the host resolves and opens the engine output directory after ACASL; plugins must not open folders themselves.
- Artifacts are filtered to the engine-defined output directory.
- Global enable/disable switch in the ACASL loader; when disabled, ACASL is skipped but the output folder can still be opened by the orchestrator.
- Soft timeout prompt (non-blocking) when plugins are unlimited; robust worker threading.
- Extended plugin metadata supported in the UI: ACASL_NAME, ACASL_VERSION, ACASL_AUTHOR, ACASL_CREATED, ACASL_LICENSE, ACASL_COMPATIBILITY, ACASL_TAGS.
- System install helpers available in the ACASL SDK: ensure_system_pip_install, ensure_system_packages.

---

## What is ACASL? {#what-is-acasl}
ACASL is the post‑compilation counterpart to BCASL. It runs automatically after builds finish and lets you handle distribution: signing, notarization, packaging, integrity checks, SBOM, hashing, smoke tests, publishing, etc.

## Execution flow and integration {#execution-flow-and-integration}
- ACASL is triggered after all builds complete.
- Discovery is strict: only packages under `API/<plugin_id>/` that declare `ACASL_PLUGIN = True` and expose `acasl_run(ctx)` are considered. The runtime validates `ACASL_ID`/`ACASL_DESCRIPTION`; extended metadata are optional but recommended.
- ACASL runs asynchronously (non‑blocking UI). Each plugin run is measured (duration in ms). A soft timeout prompt may appear when the configured timeout is unlimited.
- The host computes the engine output directory and filters artifacts to files under that directory before passing them to plugins.

## Output directory policy {#output-directory-policy}
- The orchestrator (host) — not plugins — opens the output directory on success.
- Resolution: the host queries the active engine (via `get_output_directory(gui)`) and common UI fields; see `acasl/acasl_loader.py`.
- After ACASL ends (or when ACASL is disabled), the host attempts to open the resolved output folder.
- Plugins must not open OS file browsers or paths. Log paths instead and leave folder opening to the host.

## Where to place your plugins (package layout) {#where-to-place-your-plugins-package-layout}
Create Python packages under API/ (not loose .py files). Do not place ACASL plugins under acasl/ or bcasl/:
```
API/
  ├── hash_report/
  │   └── __init__.py
  ├── compress_zip/
  │   └��─ __init__.py
  ├── signer_windows/
  │   └── __init__.py
  ├── codesign_macos/
  │   └── __init__.py
  ├── sbom_cyclonedx/
  │   └── __init__.py
  └── …
```
Rules for each package (`__init__.py`):
- Must set `ACASL_PLUGIN = True`
- Must define `ACASL_ID` and `ACASL_DESCRIPTION`
- Must define `acasl_run(ctx)`
- Always import from `API_SDK.ACASL_SDK`
- Optional: extended metadata (`ACASL_NAME/ACASL_VERSION/ACASL_AUTHOR/ACASL_CREATED/ACASL_LICENSE/ACASL_COMPATIBILITY/ACASL_TAGS`) for a better UI

## Plugin templates {#plugin-templates}
### Minimal plugin (facade‑based)
```python
# API/hello/__init__.py
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "hello"
ACASL_DESCRIPTION = "Example plugin"

# Optional extended metadata (recommended for UI)
ACASL_NAME = "Hello"
ACASL_VERSION = "0.1.0"
ACASL_AUTHOR = "Samuel Amen Ague"
ACASL_CREATED = "2025-09-06"
ACASL_LICENSE = "GPL-3.0-only"
ACASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
ACASL_TAGS = ["post-compilation", "report"]

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)  # convert host context to SDKContext
    # use sctx.* helpers (artifacts, file utils, subprocess, i18n, messages, ...)
    sctx.log_info("[hello] ACASL plugin started")
    for a in sctx.artifacts:
        sctx.log_info(f"[hello] artifact: {a}")
    sctx.log_info("[hello] finished")
```

### Respecting cancellation and progress/messages
```python
# API/sample_long/__init__.py
import time
from API_SDK.ACASL_SDK import wrap_post_context, progress

ACASL_PLUGIN = True
ACASL_ID = "sample_long"
ACASL_DESCRIPTION = "Demonstrate progress and cancel"

# Optional metadata for UI friendliness
ACASL_NAME = "SampleLong"
ACASL_VERSION = "0.1.0"
ACASL_LICENSE = "GPL-3.0-only"
ACASL_TAGS = ["post-compilation", "report"]

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    if not sctx.artifacts:
        sctx.log_warn("[sample_long] no artifacts")
        return
    with progress("Post‑build sample", "Processing artifacts…", maximum=len(sctx.artifacts), cancelable=True) as ph:
        for i, a in enumerate(sctx.artifacts):
            if ph.canceled:
                sctx.log_warn("[sample_long] canceled by user")
                return
            time.sleep(0.15)
            sctx.log_info(f"[sample_long] processed {i+1}/{len(sctx.artifacts)}: {a}")
            ph.step(1)
    sctx.msg_info("Sample", "Processing complete.")
```

## ACASL SDK facade and Context (available API) {#acasl-sdk-facade-and-context-available-api}
Always import from `API_SDK.ACASL_SDK`. Core items:
- `wrap_post_context(post_ctx) -> SDKContext` — converts host ACASLContext into SDKContext, loading workspace config and copying the artifacts list.
- SDKContext (sctx) provides:
  - Attributes: `workspace_root`, `artifacts`, `engine_id` (None in ACASL), `config_view`
  - Logging: `sctx.log_info/warn/error`
  - Messages: `sctx.msg_info/warn/error/question` (headless‑safe)
  - File utils: `sctx.path/safe_path/is_within_workspace/require_files/open_text_safe`
  - Scanning: `sctx.iter_files`, `sctx.iter_project_files(use_cache=True)`
  - Replacement: `sctx.write_text_atomic`, `sctx.replace_in_file`, `sctx.batch_replace`
  - Parallelism: `sctx.parallel_map`, Timing: `sctx.time_step`
  - Subprocess: `sctx.run_command(cmd, timeout_s=60, cwd=None, env=None, shell=False)`
- Additional helpers from the facade:
  - `progress/create_progress`, `show_msgbox`, `ConfigView/load_workspace_config/ensure_settings_file`
  - i18n: `normalize_lang_pref`, `load_plugin_translations`, `get_translations`
  - System installs: `ensure_system_pip_install` (pip global), `ensure_system_packages` (apt/dnf/pacman/zypper/winget/choco/brew)

Note: API_SDK version 3.2.3 or newer is required for ACASL facade features.

## Configuration (acasl.json) {#configuration-acasljson}
The ACASL Loader UI writes configuration to `<workspace>/acasl.json`:
```json
{
  "plugins": { "hash_report": {"enabled": true, "priority": 0} },
  "plugin_order": ["hash_report"],
  "options": { "plugin_timeout_s": 0.0, "enabled": true }
}
```
- `plugins[pid].enabled`: whether the plugin executes
- `plugins[pid].priority`: order index (0 = first)
- `plugin_order`: explicit order (top → bottom)
- `options.plugin_timeout_s`: soft timeout per plugin (<= 0 means unlimited)
- `options.enabled`: global ACASL switch (true = run, false = skip)

Behavior when disabled:
- ACASL does not run plugins and logs a notice.
- The orchestrator still tries to open the engine output directory (consistent UX).

## System installs (pip global and OS package managers) {#system-installs-pip-global-and-os-package-managers}
- Use these helpers to request user consent and install dependencies system‑wide.
- In non‑interactive mode the helpers return False and do not attempt installation.

Install Python tools globally (pip):
```python
from API_SDK.ACASL_SDK import ensure_system_pip_install, wrap_post_context

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    ok = ensure_system_pip_install(
        sctx,
        ["boto3"],
        title="Install Python tool",
        body="Install 'boto3' system-wide now?",
        python_candidates=["/usr/bin/python3", "python3", "python"],
        timeout_s=600,
    )
    if not ok:
        sctx.log_warn("boto3 not installed; skipping S3 publish")
        return
    import boto3
    sctx.log_info("boto3 available")
```

Install native packages via OS manager (Linux/Windows/macOS):
```python
from API_SDK.ACASL_SDK import ensure_system_packages, wrap_post_context

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    ok = ensure_system_packages(
        sctx,
        ["zip", "p7zip-full"],
        title="Install native tools",
        body="Install zip and 7zip with your system package manager?",
    )
    if not ok:
        sctx.log_warn("zip/7zip missing; skipping packaging")
        return
    sctx.log_info("Native tools available")
```

## UI: ACASL Loader (enable and order plugins) {#ui-acasl-loader-enable-and-order-plugins}
- Open via the sidebar button “🔌 ACASL API Loader”.
- Enable/disable plugins and reorder via drag & drop.
- Global ACASL enable/disable: toggle in the loader; saved to `options.enabled`.
- Soft timeout prompt: if `plugin_timeout_s <= 0`, a non‑blocking dialog can propose to stop ACASL after a grace delay.
- Save writes `acasl.json` in the workspace root (includes plugin order and `options.enabled`).

## Cancellation and robustness {#cancellation-and-robustness}
- If the user clicks “Cancel” during ACASL, the worker is stopped best‑effort.
- In your plugin:
  - Check cancel points (`progress` handle’s `.canceled`) or provide periodic safe prompts.
  - Always set timeouts when using `sctx.run_command`.
  - Favor atomic writes (`sctx.write_text_atomic`) and idempotent operations.

## i18n (plugin-local + core) {#i18n-plugin-local--core}
- Use `API_SDK.load_plugin_translations(Path(__file__))` to load plugin-local translations from `languages/<code>.*` (json/yaml/toml/ini/cfg); fallback to `en` then to core translations.
- Normalize the language via `normalize_lang_pref` and `resolve_system_language` (handled internally by `load_plugin_translations`).
- For strings in code, prefer a small helper resolving a key from the loaded dict, then fallback to `sctx.tr(fr, en)` for bilingual literals.

Example helper:
```python
import asyncio
from pathlib import Path
from API_SDK.ACASL_SDK import load_plugin_translations, wrap_post_context

i18n_cache = None

def _t(sctx, key, fr, en, **fmt):
    global i18n_cache
    if i18n_cache is None:
        try:
            i18n_cache = asyncio.run(load_plugin_translations(Path(__file__)))
        except RuntimeError:
            # Fallback when an event loop is already running
            import asyncio as _aio
            loop = _aio.new_event_loop()
            try:
                i18n_cache = loop.run_until_complete(load_plugin_translations(Path(__file__)))
            finally:
                loop.close()
    text = (i18n_cache or {}).get(key) if isinstance(i18n_cache, dict) else None
    base = sctx.tr(fr, en) if not isinstance(text, str) or not text.strip() else text
    try:
        return base.format(**fmt) if fmt else base
    except Exception:
        return base
```

## Best practices (security, UX, logs) {#best-practices-security-ux-logs}
- Do not open folders or file explorers; the orchestrator opens the engine output directory.
- Security: secrets only via environment or separate secure files; never commit secrets.
- UX: reduce modal prompts; prefer logs and one final summary dialog; respect non‑interactive mode.
- Logs: always log the output file paths you create.
- Idempotency: running twice should not corrupt artifacts; write side‑artifacts to distinct files.

## Troubleshooting {#troubleshooting}
- “ACASL Loader unavailable”
  - Ensure the module is importable and the UI is wired to open the loader dialog.
- Plugin not listed
  - Your plugin must be under `API/<plugin_id>/` with `__init__.py` and declare `ACASL_PLUGIN = True`.
  - Required metadata missing: define `ACASL_ID` and `ACASL_DESCRIPTION` (strings).
- ACASL disabled
  - `options.enabled=false` skips plugins; the host still attempts to open the output directory.
- No artifacts
  - Verify builds produced files and the engine output directory is resolved properly.
- System installs not happening
  - The helpers require an interactive session for consent; in non‑interactive mode they return `False`.

---

## Extended examples (rich collection) {#extended-examples-rich-collection}
(Examples retained; see stubs below. Adapt with proper validations and error handling for production.)

### 0) Zip bundle (compress main executable or app dir)
```python
# API/compress_zip/__init__.py
# ... (unchanged example from previous guide) ...
```

### 1) Hash report (SHA‑256)
```python
# API/hash_report/__init__.py
# ... (unchanged example from previous guide) ...
```

### 2) Integrity check: ldd/otool (Linux/macOS)
```python
# API/integrity_check/__init__.py
# ... (unchanged example from previous guide) ...
```

### 3) Smoke test: launch built app briefly
```python
# API/smoke_test/__init__.py
# ... (unchanged example from previous guide) ...
```

### 4) Windows code signing (signtool) — stub
```python
# API/signer_windows/__init__.py
# ... (unchanged example from previous guide) ...
```

### 5) macOS code signing + notarization — stub
```python
# API/codesign_macos/__init__.py
# ... (unchanged example from previous guide) ...
```

### 6) SBOM (CycloneDX) — stub
```python
# API/sbom_cyclonedx/__init__.py
# ... (unchanged example from previous guide) ...
```

### 7) Packaging — stubs
```python
# API/packaging/__init__.py
# ... (unchanged example from previous guide) ...
```

### 8) Publish to GitHub Releases — stub
```python
# API/publish_github/__init__.py
# ... (unchanged example from previous guide) ...
```

### 9) GPG/PGP sign a manifest — stub
```python
# API/sign_manifest/__init__.py
# ... (unchanged example from previous guide) ...
```

### 10) Publish to S3 (boto3) — with system install helper
```python
# API/publish_s3/__init__.py
# ... (unchanged example from previous guide) ...
```

### 11) Artifact pruning/renaming
```python
# API/prune_artifacts/__init__.py
# ... (unchanged example from previous guide) ...
```

### 12) Release notes (HTML) generator
```python
# API/release_notes/__init__.py
# ... (unchanged example from previous guide) ...
```

---

## Recap {#recap}
- Put your plugin in `API/<plugin_id>/__init__.py` as a Python package (folder + `__init__.py`).
- Declare `ACASL_PLUGIN = True`, provide metadata (`ACASL_ID`, `ACASL_DESCRIPTION`, optional extended fields), and define `acasl_run(ctx)`.
- Always import from `API_SDK.ACASL_SDK` and wrap the context: `sctx = wrap_post_context(ctx)`.
- Use the “🔌 ACASL API Loader” to enable and order plugins; the config is saved to `acasl.json` (with `options.plugin_timeout_s` and `options.enabled`).
- ACASL runs automatically after builds; plugins operate on `sctx.artifacts` (filtered to engine output dir).
- Do not open output folders from plugins; the orchestrator opens the engine output directory.
- Check cancellation, use timeouts, keep plugins idempotent, and leverage i18n via `load_plugin_translations` + `sctx.tr` fallback.
