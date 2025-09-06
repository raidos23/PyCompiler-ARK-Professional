# About the PyCompiler SDKs (Capabilities Reference)

Author: Samuel Amen Ague
License: GPL-3.0-only

Quick Navigation
- [Engine SDK — Capabilities](#1-engine-sdk--capabilities)
- [API_SDK — Capabilities](#2-api_sdk--capabilities)
- [Appendix](#appendix-capability-matrix-quick-glance)

This page is the authoritative capabilities reference for the two public SDKs exposed by PyCompiler Pro++: the Engine SDK and the API_SDK. It lists each capability, function signature, behavior, and platform considerations, with examples and best‑practices.

Table of Contents
- 1) Engine SDK — Capabilities
  - 1.1 Overview and Versioning
  - 1.2 Base Class: CompilerEngine
  - 1.3 Process & Execution Capabilities
  - 1.4 Executable Resolution Capabilities
  - 1.5 Environment & Filesystem Capabilities
  - 1.6 venv/Pip Capabilities
  - 1.7 Auto‑plugins Mapping Capabilities
  - 1.8 Examples
  - 1.9 Limitations, Platform Notes & Env Vars
- 2) API_SDK — Capabilities
  - 2.1 Overview, Versioning & get_capabilities
  - 2.2 Namespaced Facades: BCASL_SDK and ACASL_SDK
  - 2.3 Key Differences: Engine SDK vs API_SDK
  - 2.4 Key Differences: BCASL vs ACASL
  - 2.5 Progress & Messaging Capabilities
  - 2.6 Configuration Capabilities
  - 2.7 Context Capabilities (Scanning, Replace, Parallelism, Subprocess)
  - 2.8 Facades & Bridges (decorators, wrappers, workspace bridge)
  - 2.9 Examples (BCASL/ACASL)
  - 2.10 Limitations, Platform Notes & Env Vars

---

1) Engine SDK — Capabilities

1.1 Overview and Versioning
- Purpose: stable façade for third‑party build engines to integrate with the GUI.
- Current version: 3.2.3
- Compatibility: semantic, additive changes preferred. Breaking changes announced in release notes.

1.2 Base Class: CompilerEngine
- Contract surface (selected):
  - id: str — stable engine identifier
  - name: str — display name
  - create_tab(self, gui) -> (QWidget, str) | None — optional UI tab
  - preflight(self, gui, file) -> bool — quick validation before running
  - program_and_args(self, gui, file) -> (program: str, args: list[str]) — main command
  - environment(self, gui, file) -> dict[str, str] | None — additional env vars
  - get_timeout_seconds(self, gui) -> int — external process timeout
  - on_success(self, gui, file) -> None — post‑success hook

1.3 Process & Execution Capabilities
- run_process(gui, program, args, *, cwd=None, env=None, timeout_ms=300000, on_stdout=None, on_stderr=None) -> (code, out, err)
  - Uses Qt QProcess when available (non‑blocking UI), else subprocess.run.
  - Captures stdout/stderr. Calls optional on_stdout/on_stderr callbacks with full buffers after completion.
  - Applies working directory and environment if provided.
  - Timeout handling: terminates, then kills if needed; returns exit code and collected outputs.
  - Error handling: returns (1, "", str(error)) on unexpected exceptions.

1.4 Executable Resolution Capabilities
- resolve_executable(program, base_dir=None, *, prefer_path=True) -> str
  - Absolute path: returned as‑is.
  - Bare command + prefer_path=True: resolved via shutil.which; if not found, keep bare to allow OS PATH resolution at runtime.
  - Relative path or prefer_path=False: joined to base_dir (or CWD), normalized absolute path returned.
- resolve_executable_path(program, base_dir=None, prefer_path=True) -> str
  - Same API; acts as an alias to host resolver when available.

1.5 Environment & Filesystem Capabilities
- validate_args(args: Sequence[Any], *, max_len=4096) -> list[str]
  - Converts to strings; rejects None and control chars/newlines; enforces max length.
- build_env(base: Mapping[str,str]|None, *, whitelist=None, extra=None, minimal_path=None) -> dict[str,str]
  - Returns a reduced environment map for safe subprocess use (PATH/LANG/LC_*/TMP by default).
- ensure_dir(path) -> Path
  - Creates directories recursively; returns Path.
- atomic_write_text(path, text, encoding='utf-8') -> bool
  - Writes through a temporary file and os.replace; returns True on success.

1.6 venv/Pip Capabilities
- resolve_project_venv(gui) -> Optional[str]
  - Uses host VenvManager when available, else <workspace>/venv if exists.
- pip_executable(vroot: str) -> str
  - Returns pip path under venv root (Scripts/pip on Windows; bin/pip otherwise).
- pip_show(gui, pip_exe, package, *, timeout_ms=180000) -> int
  - Returns 0 if package installed; non‑zero otherwise.
- pip_install(gui, pip_exe, package, *, timeout_ms=600000) -> int
  - Performs pip install. Built‑in single retry after 1s on failure.

1.7 Auto‑plugins Mapping Capabilities
- compute_auto_for_engine, compute_for_all
  - Infer engine CLI arguments from detected imports/dependencies based on mapping.json rules.
  - Mapping load precedence: engine package’s mapping.json > ENGINES/<id>/mapping.json > PYCOMPILER_MAPPING file.
  - Builders: <engine_id>.auto_plugins module entry points are supported (AUTO_BUILDER/get_auto_builder/register_auto_builder).

1.8 Examples
- Non‑blocking run with callbacks
```python
from engine_sdk.utils import run_process

code, out, err = run_process(gui, "pyinstaller", ["--version"], timeout_ms=60000,
                             on_stdout=lambda s: gui.log.append("OUT:"+s),
                             on_stderr=lambda s: gui.log.append("ERR:"+s))
```
- Executable resolution with fallback to PATH
```python
from engine_sdk.utils import resolve_executable
exe = resolve_executable("python")
```
- venv pip install with retry
```python
from engine_sdk.utils import resolve_project_venv, pip_executable, pip_install
vroot = resolve_project_venv(gui)
if vroot:
    rc = pip_install(gui, pip_executable(vroot), "pyinstaller")
```

1.9 Limitations, Platform Notes & Env Vars
- QProcess requires a running Qt application; the SDK falls back to subprocess when absent.
- Windows vs POSIX: venv layouts differ (Scripts vs bin).
- Environment variables (see REFERENCE.md for details):
  - PYCOMPILER_PROCESS_TIMEOUT (default engine timeout), PYCOMPILER_REQ_FILES, PYCOMPILER_MAPPING (mapping.json path).

---

2) API_SDK — Capabilities

2.1 Overview, Versioning & get_capabilities
- Purpose: modular kit for API plugins. Supports both BCASL (pre‑compile) and ACASL (post‑compile).
- Current version: 3.2.3
- ensure_min_sdk(required: str) -> bool: semver guard.
- get_capabilities() -> dict: runtime feature detection.
  - Example return structure (selected keys):
```json
{
  "version": "3.2.3",
  "progress": { "context_manager": true, "qt": true },
  "config": { "multi_format": true, "ensure_settings_file": true },
  "context": { "iter_cache": true, "batch_replace": true, "parallel_map": true },
  "i18n": true,
  "subprocess": true,
  "workspace_bridge": true,
  "acasl": { "post_context_wrapper": true, "artifacts_in_context": true }
}
```
- sdk_info() -> { version, exports, capabilities }

2.2 Namespaced Facades: BCASL_SDK and ACASL_SDK
- BCASL_SDK: convenience imports for pre‑compile plugins
  - from API_SDK.BCASL_SDK import plugin, PluginBase, PreCompileContext, wrap_context
  - Also re‑exports progress/config/context/i18n/run_command/scaffold_plugin
  - i18n helpers are async‑only with simplified names: available_languages, resolve_system_language, get_translations, load_plugin_translations, and normalize_lang_pref (async)
- ACASL_SDK: convenience imports for post‑compile plugins
  - from API_SDK.ACASL_SDK import wrap_post_context
  - Also re‑exports progress/config/context/i18n/run_command
- Both facades are thin re‑exports of API_SDK to keep a single source of truth.

2.3 Key Differences: Engine SDK vs API_SDK
- Purpose
  - Engine SDK: integrate build engines into the GUI (tabs, command lines, processes).
  - API_SDK: implement optional automation before/after compilation (plugins).
- Entry points
  - Engine SDK: implements a class deriving from CompilerEngine (engine package).
  - API_SDK: BCASL uses class‑based plugins (PluginBase + @plugin), ACASL uses a function `acasl_run(ctx)`.
- Execution time
  - Engine SDK: during compilation of each file.
  - API_SDK: BCASL before any compilation; ACASL after all compilations.
- Processes
  - Engine SDK: owns long‑running external processes; QProcess integration built‑in.
  - API_SDK: provides run_command helper for short tasks inside plugins.

2.4 Key Differences: BCASL vs ACASL
- When they run
  - BCASL: before compilation; can mutate sources/config, prepare environment.
  - ACASL: after all builds; operates on produced artifacts (dist/build).
- Plugin discovery & layout
  - BCASL: package plugins under API/<plugin_id>/ with __init__.py; entry point is class PluginBase.on_pre_compile.
    - Mandatory package signature in __init__.py:
      - BCASL_PLUGIN = True
      - BCASL_ID = "your_id"
      - BCASL_DESCRIPTION = "short description"
  - ACASL: single Python modules under API/acasl/*.py; entry point is a function acasl_run(ctx) with ACASL_PLUGIN=True, ACASL_ID, ACASL_DESCRIPTION.
- Configuration
  - BCASL: bcasl.* (JSON/YAML/TOML/INI; hidden variants supported).
  - ACASL: acasl.json (JSON; simple enable/order map).
- Loader UI
  - BCASL: “🔌 BCASL API Loader” (pre‑compilation; package selection & order).
  - ACASL: “🔌 ACASL API Loader” (post‑compilation; module selection & order).
- Context object
  - BCASL: PreCompileContext from bcasl passed by the host; wrap with API_SDK.wrap_context to get SDKContext.
  - ACASL: ACASLContext from acasl passed by the host; wrap with API_SDK.wrap_post_context to get SDKContext (includes sctx.artifacts).
- UX conventions
  - BCASL: avoid heavy UI; use progress/messages sparingly; safe edits with write_text_atomic.
  - ACASL: treat artifacts as read‑only unless creating side‑artifacts (signatures, zips, reports).

2.5 Progress & Messaging Capabilities
- ProgressHandle(title, text="", maximum=0, cancelable=False)
  - Qt first, fallback to console; context‑manager friendly via create_progress/progress.
- show_msgbox(kind, title, text, *, default=None) -> Optional[bool]
  - kind: info | warning | error | question (question returns bool); headless‑safe with PYCOMPILER_NONINTERACTIVE.
- sys_msgbox_for_installing(subject, explanation=None, title="Installation required")
  - OS‑aware helper for privileged install prompts.

2.6 Configuration Capabilities
- ConfigView(data=None)
  - get/set, for_plugin(plugin_id) -> ConfigView (scoped), properties: required_files, file_patterns, exclude_patterns, engine_id.
- load_workspace_config(workspace_root: Path) -> dict
  - Multi‑format parser; looks for bcasl.* and hidden variants; distinct from acasl.json.
- ensure_settings_file(sctx, subdir="config", basename="settings", fmt="yaml", defaults=None, overwrite=False) -> Path
  - Writes serialized defaults in requested format; creates directories if needed.

2.7 Context Capabilities (Scanning, Replace, Parallelism, Subprocess)
- SDKContext(workspace_root: Path, config_view: ConfigView, ...)
  - Logging: log/log_info/log_warn/log_error
  - Messages: msg_info/msg_warn/msg_error/msg_question
  - noninteractive property; ui_available()
  - File utilities: path/safe_path/is_within_workspace/require_files/open_text_safe
  - Scanning: iter_files(...), iter_project_files(..., use_cache=True)
  - Replace: write_text_atomic(...), replace_in_file(...), batch_replace(...)
  - Parallelism: parallel_map(func, items, max_workers=None)
  - Timing: time_step(label)
  - Subprocess: run_command(cmd, timeout_s=60, cwd=None, env=None, shell=False) -> (rc, out, err)
  - ACASL only: artifacts list available at sctx.artifacts (via wrap_post_context)

2.8 Facades & Bridges (decorators, wrappers, workspace bridge)
- Decorators (BCASL only)
  - plugin(id=None, version="", description=""): class decorator to attach metadata to PluginBase subclasses.
- Wrappers
  - wrap_context(pre_ctx, log_fn=None, engine_id=None) -> SDKContext (BCASL)
  - wrap_post_context(post_ctx, log_fn=None) -> SDKContext (ACASL; includes artifacts)
- Workspace bridge (both)
  - set_selected_workspace(path) -> bool: ask the UI to switch workspace (may refuse if busy/invalid).

2.9 Examples (BCASL/ACASL)
- BCASL minimal package
```python
# API/my_plugin/__init__.py
from API_SDK.BCASL_SDK import plugin, PluginBase, PreCompileContext, wrap_context

# Required signature
BCASL_PLUGIN = True
BCASL_ID = "my_plugin"
BCASL_DESCRIPTION = "Demo"

@plugin(id=BCASL_ID, version="0.1.0", description=BCASL_DESCRIPTION)
class MyPlugin(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        sctx = wrap_context(ctx)
        sctx.log_info("Hello from BCASL")
        missing = sctx.require_files(["main.py"]) 
        if missing:
            raise FileNotFoundError("Missing main.py")
```

- ACASL minimal module
```python
# API/acasl/hello.py
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "hello"
ACASL_DESCRIPTION = "Post‑build demo"

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    for a in sctx.artifacts:
        sctx.log_info(f"artifact: {a}")
```

2.10 Limitations, Platform Notes & Env Vars
- Headless non‑interactive mode: set PYCOMPILER_NONINTERACTIVE=1. Message boxes become console logs; user prompts must have safe defaults.
- Performance: prefer iter_project_files(use_cache=True); narrow patterns/excludes; batch writes.
- Environment variables (selected; see REFERENCE.md for the full list):
  - Common: PYCOMPILER_NONINTERACTIVE
  - BCASL: PYCOMPILER_BCASL_PLUGIN_TIMEOUT, PYCOMPILER_BCASL_SOFT_TIMEOUT, PYCOMPILER_BCASL_PARALLELISM
  - ACASL: inherits app‑level timeout/cancel policies; plugins should use run_command timeouts

---

Appendix: Capability Matrix (Quick Glance)

Engine SDK
- Process: QProcess/subprocess, callbacks, timeouts
- Exec resolution: absolute/which/base_dir
- Args/env: validate_args, build_env
- FS: ensure_dir, atomic_write_text
- Venv/pip: resolve_project_venv, pip_* helpers
- Auto‑plugins: mapping discovery + builders

API_SDK (BCASL + ACASL)
- Progress/Msg: ProgressHandle, show_msgbox, sys_msgbox_for_installing
- Config: ConfigView, multi‑format config, ensure_settings_file
- Context: safe_path, cached scanning, replace/batch_replace, parallel_map, time_step, run_command
- i18n: async‑only helpers (normalize_lang_pref, resolve_system_language, available_languages, get_translations, load_plugin_translations)
- Bridges & Facades: plugin decorator (BCASL), wrap_context (BCASL), wrap_post_context (ACASL), set_selected_workspace; namespaced facades BCASL_SDK and ACASL_SDK

For more context and step‑by‑step tutorials, see:
- Engines how‑to: docs/how_to_creat_a_building_engine.md
- BCASL plugins how‑to: docs/how_to_creat_a_bcasl_API.md
- ACASL plugins how‑to: docs/how_to_creat_a_acasl_API.md
- Framework Reference: docs/REFERENCE.md
