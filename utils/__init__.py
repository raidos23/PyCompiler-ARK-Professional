# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

# Author: Samuel Amen Ague
"""
PyCompiler Pro++ - Package Public API (lazy-loaded)

This module exposes the high-level API of the utils package while avoiding
heavy imports at module import-time. Public attributes are resolved lazily
via __getattr__ (PEP 562), which speeds up startup and reduces side effects
until a symbol is actually used.

Exports (stable):
- Preferences: MAX_PARALLEL, PREFS_FILE, load_preferences, save_preferences, update_ui_state
- Compiler:   compile_all, try_start_processes, start_compilation_process,
              handle_stdout, handle_stderr, handle_finished,
              try_install_missing_modules, show_error_dialog, cancel_all_compilations,
              build_pyinstaller_command, build_nuitka_command
- Dependency analysis: suggest_missing_dependencies,
                       _install_next_dependency, _on_dep_pip_output, _on_dep_pip_finished
- Dialogs:    ProgressDialog
- UI:         PyInstallerWorkspaceGUI
- BCASL/api_loader: run_pre_compile (exécute les plugins API avant compilation)
- api:        structured dictionary view of the API (constructed on first access)

Notes
- Private helpers beginning with '_' are intentionally exposed for internal wiring
  consistency across modules; avoid relying on them from external code.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from os.path import dirname as _dirname
from threading import RLock
from types import ModuleType
from typing import Any

__version__ = "3.2.3"

# Cache of resolved attributes to avoid repeated imports
_RESOLVED: dict[str, Any] = {}
# Bind common names once to avoid repeated global lookups
_PKG: str = __package__ or __name__
_NAME: str = __name__
_ROOT_ADDED: bool = False
# Precomputed paths for sys.path fallback
_PKG_DIR: str = _dirname(__file__)
_ROOT_DIR: str = _dirname(_PKG_DIR)
# Cache des modules et chemin préféré pour accélérer les résolutions ultérieures
_MODULES: dict[str, ModuleType] = {}
_MODULE_TARGET: dict[str, str] = {}
_LOCK = RLock()

# Cache per-module candidate targets to avoid rebuilding lists on each access
_CANDIDATES_CACHE: dict[str, list[tuple[str, str | None]]] = {}


def _get_candidates(mod_name: str) -> list[tuple[str, str | None]]:
    """Build and cache a prioritized list of import targets for a module name.

    The resolver will try candidates in order, covering relative and absolute
    forms. Results are cached per module name to avoid repeated string building.
    Returns a list of (target, package) pairs suitable for importlib.import_module.
    """
    cached = _CANDIDATES_CACHE.get(mod_name)
    if cached is not None:
        return cached
    tail = mod_name.lstrip(".")
    lst: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()

    def add(t: str, p: str | None) -> None:
        key = (t, p)
        if key not in seen:
            seen.add(key)
            lst.append((t, p))

    # 1) As declared
    if mod_name.startswith("."):
        add(mod_name, _PKG)
    else:
        add(mod_name, None)
    # 2) Absolute using the full current package path
    add(f"{_PKG}.{tail}", None)
    # 3) If running under a different top-level name, also try using __name__ base
    if _NAME != _PKG:
        add(f"{_NAME}.{tail}", None)
    _CANDIDATES_CACHE[mod_name] = lst
    return lst


# Map public names to (module, attribute) pairs for lazy resolution
_EXPORTS: dict[str, tuple[str, str]] = {
    # Preferences
    "MAX_PARALLEL": (".preferences", "MAX_PARALLEL"),
    "PREFS_FILE": (".preferences", "PREFS_FILE"),
    "load_preferences": (".preferences", "load_preferences"),
    "save_preferences": (".preferences", "save_preferences"),
    "update_ui_state": (".preferences", "update_ui_state"),
    "preferences_system_info": (".preferences", "preferences_system_info"),
    "export_system_preferences_json": (".preferences", "export_system_preferences_json"),
    # Compiler
    "compile_all": (".compiler", "compile_all"),
    "try_start_processes": (".compiler", "try_start_processes"),
    "start_compilation_process": (".compiler", "start_compilation_process"),
    "handle_stdout": (".compiler", "handle_stdout"),
    "handle_stderr": (".compiler", "handle_stderr"),
    "handle_finished": (".compiler", "handle_finished"),
    "try_install_missing_modules": (".compiler", "try_install_missing_modules"),
    "show_error_dialog": (".compiler", "show_error_dialog"),
    "cancel_all_compilations": (".compiler", "cancel_all_compilations"),
    "build_pyinstaller_command": (".compiler", "build_pyinstaller_command"),
    "build_nuitka_command": (".compiler", "build_nuitka_command"),
    # Dependency analysis (some internal helpers intentionally exported)
    "suggest_missing_dependencies": (".dependency_analysis", "suggest_missing_dependencies"),
    "_install_next_dependency": (".dependency_analysis", "_install_next_dependency"),
    "_on_dep_pip_output": (".dependency_analysis", "_on_dep_pip_output"),
    "_on_dep_pip_finished": (".dependency_analysis", "_on_dep_pip_finished"),
    # Dialogs
    "ProgressDialog": (".dialogs", "ProgressDialog"),
    # UI main entry point
    "PyInstallerWorkspaceGUI": (".worker", "PyInstallerWorkspaceGUI"),
    # BCASL integration
    "run_pre_compile": (".bcasl_loader", "run_pre_compile"),
    # Engines (external)
    "resolve_executable_path": (".engines.external", "resolve_executable_path"),
    # System dependency manager
    "SysDependencyManager": (".sys_dependency", "SysDependencyManager"),
}


# Static import hints for bundlers (ensures collection without hidden imports)
# These are not executed at runtime because the condition is constant False.
if False:  # pragma: no cover
    pass


def _load_export(name: str) -> Any:
    """Resolve and cache a public symbol lazily.

    Resolution strategy (in order):
      1) In-memory cache hit (_RESOLVED)
      2) Previously hinted absolute target (_MODULE_TARGET)
      3) Prioritized candidates from _get_candidates
      4) Last resort: insert project root into sys.path and import absolute package path

    Thread-safety: cache writes guarded by _LOCK. Errors are re-raised with
    augmented diagnostics to ease troubleshooting.
    """
    # Fast-path: return from cache if already resolved
    if name in _RESOLVED:
        return _RESOLVED[name]
    mod_name, attr = _EXPORTS[name]
    pkg = _PKG
    tail = mod_name.lstrip(".")
    last_err: Exception | None = None

    # Use cached module if available
    with _LOCK:
        mod_cached = _MODULES.get(mod_name)
    if mod_cached is not None:
        try:
            value = getattr(mod_cached, attr)
            with _LOCK:
                _RESOLVED[name] = value
                globals()[name] = value
            return value
        except AttributeError as e:
            last_err = e  # proceed to import attempts

    # Try hinted absolute target first if known
    with _LOCK:
        hinted = _MODULE_TARGET.get(mod_name)
    if hinted:
        try:
            mod = _import_module(hinted) if not hinted.startswith(".") else _import_module(hinted, pkg)
            value = getattr(mod, attr)
            with _LOCK:
                _RESOLVED[name] = value
                globals()[name] = value
                _MODULES[mod_name] = mod
            return value
        except (ModuleNotFoundError, ImportError, AttributeError) as e:
            last_err = e

    # Build a robust list of candidates to try in order (cached per module)
    candidates = _get_candidates(mod_name)

    for target, package in candidates:
        try:
            if package:
                mod = _import_module(target, package)
            else:
                mod = _import_module(target)
            value = getattr(mod, attr)
            with _LOCK:
                _RESOLVED[name] = value
                globals()[name] = value
                _MODULES.setdefault(mod_name, mod)
                _MODULE_TARGET.setdefault(mod_name, target)
            return value
        except (ModuleNotFoundError, ImportError, AttributeError) as e:
            last_err = e
            continue

    # 5) Last resort: ensure project root is on sys.path then retry absolute import
    try:
        global _ROOT_ADDED
        if not _ROOT_ADDED and _ROOT_DIR not in _sys.path:
            _sys.path.insert(0, _ROOT_DIR)
            _ROOT_ADDED = True
        mod = _import_module(f"{pkg}.{tail}")
        value = getattr(mod, attr)
        with _LOCK:
            _RESOLVED[name] = value
            globals()[name] = value
            _MODULES.setdefault(mod_name, mod)
            _MODULE_TARGET.setdefault(mod_name, f"{pkg}.{tail}")
        return value
    except Exception as e:
        last_err = e

    # Propagate the most recent error with clearer diagnostics
    if isinstance(last_err, (ModuleNotFoundError, ImportError)):
        raise last_err
    if isinstance(last_err, AttributeError):
        raise AttributeError(f"Export '{name}' not found: module '{tail}' has no attribute '{attr}'") from last_err
    raise RuntimeError(f"Failed to load export '{name}' ({pkg}.{tail}.{attr}): {last_err}") from last_err


def __getattr__(name: str) -> Any:
    """Lazy attribute resolver for the public utils API (PEP 562).

    - If 'name' is declared in _EXPORTS, resolve it lazily and cache it.
    - If 'name' == 'api', compute and cache a structured snapshot of the
      high-level public surface for discoverability and IDE help.
    """
    # Lazy resolution for declared exports
    if name in _EXPORTS:
        return _load_export(name)
    # Build a structured API snapshot lazily on first access
    if name == "api":
        api = {
            "preferences": {
                "MAX_PARALLEL": _load_export("MAX_PARALLEL"),
                "PREFS_FILE": _load_export("PREFS_FILE"),
                "load_preferences": _load_export("load_preferences"),
                "save_preferences": _load_export("save_preferences"),
                "update_ui_state": _load_export("update_ui_state"),
                "preferences_system_info": _load_export("preferences_system_info"),
                "export_system_preferences_json": _load_export("export_system_preferences_json"),
            },
            "compiler": {
                "compile_all": _load_export("compile_all"),
                "try_start_processes": _load_export("try_start_processes"),
                "start_compilation_process": _load_export("start_compilation_process"),
                "handle_stdout": _load_export("handle_stdout"),
                "handle_stderr": _load_export("handle_stderr"),
                "handle_finished": _load_export("handle_finished"),
                "try_install_missing_modules": _load_export("try_install_missing_modules"),
                "show_error_dialog": _load_export("show_error_dialog"),
                "cancel_all_compilations": _load_export("cancel_all_compilations"),
                "build_pyinstaller_command": _load_export("build_pyinstaller_command"),
                "build_nuitka_command": _load_export("build_nuitka_command"),
            },
            "dependency_analysis": {
                "suggest_missing_dependencies": _load_export("suggest_missing_dependencies"),
                "_install_next_dependency": _load_export("_install_next_dependency"),
                "_on_dep_pip_output": _load_export("_on_dep_pip_output"),
                "_on_dep_pip_finished": _load_export("_on_dep_pip_finished"),
            },
            "dialogs": {
                "ProgressDialog": _load_export("ProgressDialog"),
            },
            "ui": {
                "PyInstallerWorkspaceGUI": _load_export("PyInstallerWorkspaceGUI"),
            },
            "bcasl_loader": {
                "run_pre_compile": _load_export("run_pre_compile"),
            },
            "engines": {
                "resolve_executable_path": _load_export("resolve_executable_path"),
            },
            "sys_dependency": {
                "SysDependencyManager": _load_export("SysDependencyManager"),
            },
        }
        globals()["api"] = api  # cache snapshot
        return api
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Internal maintenance helper (not exported): clear lazy-load caches


def _clear_lazy_caches() -> None:
    """Clear all lazy-load caches (for tests/debugging)."""
    with _LOCK:
        _RESOLVED.clear()
        _MODULES.clear()
        _MODULE_TARGET.clear()
        _CANDIDATES_CACHE.clear()
    try:
        globals().pop("api", None)
    except Exception:
        pass


# Precompute directory listing and __all__ for faster introspection
_DIR: list[str] = sorted(list(_EXPORTS.keys()) + ["api", "__version__"])


def __dir__() -> list[str]:  # aid IDEs and dir(utils)
    return _DIR


__all__ = tuple(_DIR)
