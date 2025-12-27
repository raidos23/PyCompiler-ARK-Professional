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



"""
BCASL - Before-Compilation Actions System Loader

Point d'entrée du package: expose l'API publique minimale et stable.

    from bcasl import (
        BCASL, PluginBase, PluginMeta, PreCompileContext, ExecutionReport,
        register_plugin, BCASL_PLUGIN_REGISTER_FUNC,
        run_pre_compile_async, run_pre_compile,
        ensure_bcasl_thread_stopped, open_bc_loader_dialog,
        resolve_bcasl_timeout,
    )
"""
from __future__ import annotations

from .executor import BCASL

# Coeur BCASL (moteur de plugins et contexte)
from .Base import (
    ExecutionReport,
    BcPluginBase,
    PluginMeta,
    PreCompileContext,
    register_plugin,
    BCASL_PLUGIN_REGISTER_FUNC,
)

# Chargeur (exécution asynchrone, UI, annulation, configuration)
from .Loader import (
    ensure_bcasl_thread_stopped,
    open_bc_loader_dialog,
    resolve_bcasl_timeout,
    run_pre_compile,
    run_pre_compile_async,
)

# Validateur de compatibilité
from .validator import (
    CompatibilityCheckResult,
    check_plugin_compatibility,
    validate_plugins_compatibility,
    print_compatibility_report,
)

__version__ = "2.0.0"


def check_plugin_compatibility(plugin_class, required_bcasl_version: str = None) -> bool:
    """Check if a plugin is compatible with the current BCASL version.
    
    Args:
        plugin_class: The plugin class to check
        required_bcasl_version: Minimum required BCASL version (defaults to plugin's requirement)
    
    Returns:
        True if compatible, False otherwise
    """
    try:
        if required_bcasl_version is None:
            required_bcasl_version = getattr(plugin_class, "required_bcasl_version", "1.0.0")
        
        # Parse versions
        def parse_version(v: str) -> tuple:
            try:
                parts = v.strip().split("+")[0].split("-")[0].split(".")
                major = int(parts[0]) if len(parts) > 0 else 0
                minor = int(parts[1]) if len(parts) > 1 else 0
                patch = int(parts[2]) if len(parts) > 2 else 0
                return (major, minor, patch)
            except Exception:
                return (0, 0, 0)
        
        current = parse_version(__version__)
        required = parse_version(required_bcasl_version)
        return current >= required
    except Exception:
        return False


__all__ = [
    # Coeur
    "executor",
    "BcPluginBase",
    "PluginMeta",
    "PreCompileContext",
    "ExecutionReport",
    "register_plugin",
    "BCASL_PLUGIN_REGISTER_FUNC",
    # Loader
    "run_pre_compile_async",
    "run_pre_compile",
    "ensure_bcasl_thread_stopped",
    "open_bc_loader_dialog",
    "resolve_bcasl_timeout",
    # Compatibility & Validation
    "check_plugin_compatibility",
    "CompatibilityCheckResult",
    "validate_plugins_compatibility",
    "print_compatibility_report",
]
