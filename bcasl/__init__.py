# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague
# Author: Samuel Amen Ague
"""
Package BCASL - Before-Compilation Actions System & Loader

Point d'entrée du package, réexporte l'API publique pour permettre des imports simples:

    from bcasl import (
        BCASL, PluginBase, PluginMeta, PreCompileContext,
        run_pre_compile_async, run_pre_compile,
        ensure_bcasl_thread_stopped, open_api_loader_dialog,
        resolve_bcasl_timeout,
    )

Le chargeur BCASL est cherché d'abord dans bcasl/bcasl_loader.py, puis en repli
vers utils/api_loader.py pour compatibilité ascendante.
"""
from __future__ import annotations

# Coeur BCASL (moteur de plugins et contexte)
from .bcasl import (
    BCASL,
    ExecutionReport,
    PluginBase,
    PluginMeta,
    PreCompileContext,
    register_plugin,
)

# Chargeur (exécution asynchrone, UI, annulation, configuration)
try:  # préférence: nouveau chemin dans le package bcasl
    from .bcasl_loader import (
        ensure_bcasl_thread_stopped,
        open_api_loader_dialog,
        resolve_bcasl_timeout,
        run_pre_compile,
        run_pre_compile_async,
    )
except Exception:
    # Repli: ancien chemin historique
    try:
        from utils.api_loader import (
            ensure_bcasl_thread_stopped,
            open_api_loader_dialog,
            resolve_bcasl_timeout,
            run_pre_compile,
            run_pre_compile_async,
        )
    except Exception:
        # Dernier recours: stubs inoffensifs
        def run_pre_compile_async(self, on_done=None):  # type: ignore
            try:
                if hasattr(self, "log") and self.log:
                    self.log.append("⚠️ BCASL loader indisponible.")
            except Exception:
                pass
            if callable(on_done):
                try:
                    on_done(None)
                except Exception:
                    pass

        def run_pre_compile(self):  # type: ignore
            try:
                if hasattr(self, "log") and self.log:
                    self.log.append("⚠️ BCASL loader indisponible.")
            except Exception:
                pass
            return None

        def ensure_bcasl_thread_stopped(self, timeout_ms: int = 5000):  # type: ignore
            return None

        def open_api_loader_dialog(self):  # type: ignore
            try:
                if hasattr(self, "log") and self.log:
                    self.log.append("ℹ️ API Loader indisponible (BCASL).")
            except Exception:
                pass

        def resolve_bcasl_timeout(self) -> float:  # type: ignore
            return 0.0


__all__ = [
    # Coeur
    "BCASL",
    "PluginBase",
    "PluginMeta",
    "PreCompileContext",
    "ExecutionReport",
    "register_plugin",
    # Loader
    "run_pre_compile_async",
    "run_pre_compile",
    "ensure_bcasl_thread_stopped",
    "open_api_loader_dialog",
    "resolve_bcasl_timeout",
]

__version__ = "1.1.0"
