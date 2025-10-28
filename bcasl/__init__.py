# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague
# Author: Samuel Amen Ague
"""
BCASL - Before-Compilation Actions System Loader

Point d'entrée du package: expose l'API publique minimale et stable.

    from bcasl import (
        BCASL, PluginBase, PluginMeta, PreCompileContext, ExecutionReport,
        register_plugin, BCASL_PLUGIN_REGISTER_FUNC,
        run_pre_compile_async, run_pre_compile,
        ensure_bcasl_thread_stopped, open_api_loader_dialog,
        resolve_bcasl_timeout,
    )
"""
from __future__ import annotations

# Coeur BCASL (moteur de plugins et contexte)
from .bcasl import (
    BCASL,
    ExecutionReport,
    Bc_PluginBase,
    PluginMeta,
    PreCompileContext,
    register_plugin,
    BCASL_PLUGIN_REGISTER_FUNC,
)

# Chargeur (exécution asynchrone, UI, annulation, configuration)
from .bcasl_loader import (
    ensure_bcasl_thread_stopped,
    open_api_loader_dialog,
    resolve_bcasl_timeout,
    run_pre_compile,
    run_pre_compile_async,
)

__all__ = [
    # Coeur
    "BCASL",
    "Bc_PluginBase",
    "PluginMeta",
    "PreCompileContext",
    "ExecutionReport",
    "register_plugin",
    "BCASL_PLUGIN_REGISTER_FUNC",
    # Loader
    "run_pre_compile_async",
    "run_pre_compile",
    "ensure_bcasl_thread_stopped",
    "open_api_loader_dialog",
    "resolve_bcasl_timeout",
]

__version__ = "1.1.0"
