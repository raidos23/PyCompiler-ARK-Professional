# PyCompiler Pro++ (ARK++)

GUI to compile Python projects across multiple engines with pre/post build automation and a unified SDK.

## Highlights (3.2.3)
- Stable SDK facades: API_SDK and engine_sdk (v3.2.3)
- Engines: PyInstaller, Nuitka, cx_Freeze
- Non‑blocking Qt UI with theme support; progress for long tasks
- Async‑only i18n with simplified APIs; app translations + plugin overlays
- BCASL (pre‑compile) loader is strict and predictable:
  - Only loads packages that declare BCASL_PLUGIN = True with BCASL_ID and BCASL_DESCRIPTION
  - Plugin order/priority managed via bcasl.json (auto‑generated if missing)
  - Non‑blocking execution with soft timeout options
- ACASL (post‑compile) loader is robust:
  - Static discovery without executing plugin code
  - Per‑plugin soft timeout; duration metrics in reports
  - Atomic writes for acasl.json and configuration normalization

## Features
- Unified, stable facades (API_SDK, engine_sdk) to build engines and plugins
- Multi‑format config (JSON/YAML/TOML/INI) with safe file operations
- Subprocess helpers and workspace utilities
- Simple extension model for engines and plugins

## Architecture Overview

- BCASL (Before Compilation Advanced System Loader)
  - Purpose: run plugins before the build (validation, preparation, code transformation, etc.)
  - Plugins: Python packages under `API/<plugin_id>/` with `__init__.py`
  - Required package signature:
    - `BCASL_PLUGIN = True`
    - `BCASL_ID = "..."`
    - `BCASL_DESCRIPTION = "..."`
  - Entry point: `bcasl_register(manager)` that registers a `PluginBase` implementing `on_pre_compile(ctx)`

- Engines layer (utils/engines_loader)
  - Encapsulates build backends (PyInstaller, Nuitka, cx_Freeze) behind a common `CompilerEngine` contract
  - Provides per‑engine tabs/options and a unified run pipeline

- ACASL (After Compilation Advanced System Loader)
  - Purpose: run plugins after the build on produced artifacts (packaging, signing, hashing, publishing, etc.)
  - Plugins: Python modules under `API/acasl/<id>.py`
  - Signature and entry point:
    - `ACASL_PLUGIN = True`, `ACASL_ID`, `ACASL_DESCRIPTION`
    - `acasl_run(ctx)`

Overall flow: select workspace → BCASL (pre‑build) → compile with selected engine → ACASL (post‑build) → open artifacts / reports.

## Quick start
1) Install dependencies (dev):
```
python -m pip install -r requirements.txt
```
2) Run the app:
```
./run.sh
```
3) Select a workspace and files. Choose an engine tab and build.

## Internationalization (i18n)
- Async helpers (async‑only):
  - `resolve_system_language()`, `available_languages()`, `get_translations(lang_pref)`
- Add more languages under `languages/*.json` (samples: `en.json`, `fr.json`, `ja.json`, `zh-CN.json`).

## Engines
- PyInstaller — main tab with core options
- Nuitka — dedicated tab with core flags
- cx_Freeze — minimal dynamic tab (output directory)

## Pre‑compile (BCASL)
- Packages under `API/<plugin_id>/` with `__init__.py`
- Required signature enforced:
  - `BCASL_PLUGIN = True`
  - `BCASL_ID = "..."`
  - `BCASL_DESCRIPTION = "..."`
- Register plugin with `bcasl_register(manager)`
- See `docs/how_to_creat_a_bcasl_API.md`

## Post‑compile (ACASL)
- Modules under `API/acasl/<id>.py` with:
  - `ACASL_PLUGIN = True`
  - `ACASL_ID`, `ACASL_DESCRIPTION`
  - function `acasl_run(ctx)`
- See `docs/how_to_creat_a_acasl_API.md`

## SDKs
- `engine_sdk`: base `CompilerEngine` and helpers
- `API_SDK`: common surfaces (progress, config, context, i18n) for BCASL and ACASL
- References: `docs/about_sdks.md`, `docs/REFERENCE.md`

## Contributing
- Open PRs with a branch; ensure basic checks pass
- Suggested toolchain: ruff, mypy, pytest, coverage, bandit
- See `pyproject.toml` for tool configuration

## License
This project is licensed under the GNU General Public License v3.0 only (GPL‑3.0‑only). See the `LICENSE` file for details.

Copyright (C) 2025 Samuel Amen Ague
