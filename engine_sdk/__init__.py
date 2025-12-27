# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

# Re-export auto_plugins helpers for convenience
from .auto_build_command import (
    compute_auto_for_engine,
    compute_for_all,
    register_auto_builder,
)

# Re-export the base interface used by the host
from .base import CompilerEngine
from .utils import (
    atomic_write_text,
    build_env,
    clamp_text,
    ensure_dir,
    is_within_workspace,
    normalized_program_and_args,
    open_dir_candidates,
    open_path,
    pip_executable,
    pip_install,
    pip_show,
    redact_secrets,
    resolve_executable,  # executable resolution helper (SDK)
    resolve_executable_path,
    resolve_project_venv,
    run_process,
    safe_join,
    safe_log,
    tr,
    validate_args,
)

try:
    # Optional alias to host-level executable resolver for advanced cases
    from .utils import resolve_executable_path as host_resolve_executable_path  # type: ignore
except Exception:  # pragma: no cover
    host_resolve_executable_path = None  # type: ignore

# Simple wrapper to persist engine UI state via host registry
def save_engine_ui(gui, engine_id: str, updates: dict) -> bool:
    try:
        if registry is None:
            return False
        return registry.save_engine_ui(gui, engine_id, updates)  # type: ignore[attr-defined]
    except Exception:
        return False

# Re-export system dependency helpers
# Re-export i18n helpers
from .i18n import (
    available_languages,
    get_translations,
    normalize_lang_pref,
    resolve_system_language,
)
from .Sys_Deps import SysDependencyManager  # type: ignore

# Re-export engines registry for self-registration from engine packages
try:
    from Core.engines_loader import registry as registry  # type: ignore
except Exception:  # pragma: no cover
    registry = None  # type: ignore

__version__ = "3.2.3"


# Lazy attribute resolver to reduce import overhead in plugin environments
def __getattr__(name: str):
    if name == "SysDependencyManager":
        import importlib

        mod = importlib.import_module(f"{__name__}.sysdep")
        attr = getattr(mod, "SysDependencyManager")
        globals()["SysDependencyManager"] = attr
        return attr
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    try:
        base = set(globals().keys()) | set(__all__)
        return sorted(base)
    except Exception:
        return sorted(globals().keys())


# Version helpers and capability report


def _parse_version(v: str) -> tuple:
    try:
        parts = v.strip().split("+")[0].split("-")[0].split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except Exception:
        return (0, 0, 0)


def ensure_min_sdk(required: str) -> bool:
    """Return True if the current SDK version satisfies the minimal required semver (major.minor.patch).
    Example: ensure_min_sdk("3.2.2") -> True/False
    """
    try:
        cur = _parse_version(__version__)
        need = _parse_version(str(required))
        return cur >= need
    except Exception:
        return False


def get_capabilities() -> dict:
    """Return a dictionary of SDK runtime capabilities for feature detection."""
    caps = {
        "version": __version__,
        "process": {
            "on_stdout": True,
            "on_stderr": True,
        },
        "fs": {
            "atomic_write_text": True,
            "ensure_dir": True,
        },
        "exec_resolution": {
            "host_resolve_executable_path": bool(host_resolve_executable_path),
        },
        "config": {
            "save_engine_ui": True,
        },
    }
    return caps


def sdk_info() -> dict:
    """Return SDK metadata, exported symbols and capabilities."""
    return {
        "version": __version__,
        "exports": sorted(list(__all__)),
        "capabilities": get_capabilities(),
    }


__all__ = [
    "CompilerEngine",
    "compute_auto_for_engine",
    "compute_for_all",
    "register_auto_builder",
    "registry",
    # Utilities for engine authors
    "redact_secrets",
    "is_within_workspace",
    "safe_join",
    "validate_args",
    "build_env",
    "clamp_text",
    "normalized_program_and_args",
    "tr",
    "safe_log",
    "open_path",
    "open_dir_candidates",
    "resolve_project_venv",
    "pip_executable",
    "pip_show",
    "pip_install",
    "resolve_executable",
    "ensure_dir",
    "atomic_write_text",
    "run_process",
    "resolve_executable_path",
    "host_resolve_executable_path",
    "SysDependencyManager",
    "normalize_lang_pref",
    "available_languages",
    "resolve_system_language",
    "get_translations",
    "ensure_min_sdk",
    "get_capabilities",
    "sdk_info",
    "__version__",
    # Config helpers
    "save_engine_ui",
]
