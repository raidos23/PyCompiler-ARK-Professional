# About SDKs

This document provides an overview of the development SDKs available in PyCompiler ARK++ and how they fit together.

- Audience: plugin and engine developers
- Scope: high-level concepts and links to the concrete guides

## Overview

PyCompiler ARK++ exposes two main SDKs:

1) Plugins_SDK (BCASL only)
- Purpose: create pre-compilation (Before Compilation) plugins executed before a build starts
- Typical responsibilities:
  - Validate project structure and dependencies
  - Prepare artifacts (generate files, clean up, configure pathing)
  - Perform pre-flight checks and block the build when necessary
- Key characteristics:
  - Runs in a sandboxed and isolated environment (when applicable)
  - Declarative metadata (id, name, tags, dependencies)
  - i18n support independent of the application language
- Start here: docs/how_to_create_a_BC_plugin.md

2) Engine SDK
- Purpose: implement compilation engines (e.g., PyInstaller, Nuitka, cx_Freeze) with pluggable UI and behavior
- Typical responsibilities:
  - Build command composition (program and arguments)
  - Engine-owned venv/tooling checks and non-blocking installation flows
  - Tab UI creation and translation
  - Post-success hook for user feedback (logs, opening directories, etc.)
- Start here: docs/how_to_create_an_engine.md

## Lifecycle

The typical lifecycle when compiling a project is:

1. User selects workspace and files in the GUI
2. BCASL plugins run (Plugins_SDK)
   - Validate and prepare the workspace
   - Can fail fast to abort the build if required preconditions are not met
3. Engine runs (Engine SDK)
   - Resolves tools in the workspace venv
   - Executes the build process using a QProcess
   - Streams progress and logs to the GUI
4. Post-success hook
   - Engines may open or highlight the output directory
   - Engines may log additional details about the produced artifacts

## Design Principles

- Non-blocking UI: all long operations should be asynchronous or off the GUI thread
- Least privileges: engines/tools should run with minimal environment variables
- Reproducibility: prefer venv-local tools and deterministic command lines
- Internationalization: all user-facing text should be translatable

## Directory Structure Summary

- Engines live under ENGINES/<engine_id>/ with __init__.py and optional languages/
- BCASL plugins live under Plugins/<plugin_id>/ with __init__.py and optional languages/
- The GUI binds engine tabs dynamically and runs BCASL prior to compilation

