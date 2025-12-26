# Support Matrix

This document lists officially supported platforms and versions for PyCompiler ARK++.

## Operating Systems

| OS       | Versions                  | Arch | Status |
|----------|---------------------------|------|--------|
| Ubuntu   | 20.04, 22.04, 24.04 (LTS) | x64  | ✅ Supported |
| Windows  | 10, 11                    | x64  | ✅ Supported |
| macOS    | —                         | —    | ❌ Not officially supported |

Notes:
- macOS is not officially supported; some utilities may partially work but no active support is provided.

## Python Versions

| Python | Status         |
|--------|----------------|
| 3.10   | ✅ Minimum     |
| 3.11   | ✅ Recommended |
| 3.12   | ✅ Stable      |
| 3.13   | 🧪 Experimental|

## Compilation Engines

| Engine      | Status | Notes |
|-------------|--------|-------|
| PyInstaller | ✅     | Requires engine to resolve venv-local tool and manage options in tab |
| Nuitka      | ✅     | Requires system toolchain on Linux/Windows; engine manages venv & flags |
| cx_Freeze   | ✅     | Requires Python headers/tools per-platform; engine manages venv & flags |

## UI Libraries

| Binding  | Status | Notes                            |
|----------|--------|----------------------------------|
| PySide6  | ✅     | Actively tested                   |
| PyQt6    | ⚠️     | Partial; depends on user project  |

## General Notes
- Prefer venv-local tools for reproducibility
- Engines must keep the GUI responsive; avoid blocking calls
- Internationalization support is available via async i18n utilities

