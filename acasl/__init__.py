# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
ACASL (After Compilation Action System Loader)

This package exposes the public ACASL API for post‑compilation steps.
Primary exports:
- run_post_compile_async(gui, artifacts, finished_cb=None)
- ensure_acasl_thread_stopped(gui=None)
- ACASLContext

Preferred loader in-package: 'acasl/acasl_loader.py'; fallback to 'utils/acasl_loader.py' for backward compatibility.
"""

__all__ = (
    # Loader API
    "run_post_compile_async",
    "ensure_acasl_thread_stopped",
    "ACASLContext",
    "open_acasl_loader_dialog",
    # Plugin system
    "Ac_PluginBase",
    "PluginMeta",
    "PostCompileContext",
    "ExecutionReport",
    "ACASL",
)

__version__ = "1.1.0"

# Preferred: loader in this package
try:  # pragma: no cover
    from .acasl_loader import (  # type: ignore
        ACASLContext,
        ensure_acasl_thread_stopped,
        open_acasl_loader_dialog,
        run_post_compile_async,
    )
    # Also import plugin system
    from .acasl import (  # type: ignore
        ACASL,
        Ac_PluginBase,
        ExecutionReport,
        PluginMeta,
        PostCompileContext,
    )
except Exception:  # pragma: no cover
    # Fallback to legacy location
    try:
        from Core.acasl_loader import (  # type: ignore
            ACASLContext,
            ensure_acasl_thread_stopped,
            open_acasl_loader_dialog,
            run_post_compile_async,
        )
    except Exception:
        # Last-resort no-op stubs to avoid crashes if loader is missing
        def run_post_compile_async(gui, artifacts, finished_cb=None):  # type: ignore
            try:
                if hasattr(gui, "log") and gui.log:
                    gui.log.append("⚠️ ACASL indisponible (aucun loader trouvé).")
            except Exception:
                pass

        def ensure_acasl_thread_stopped(gui=None):  # type: ignore
            try:
                if gui is not None:
                    setattr(gui, "_closing", True)
            except Exception:
                pass

        class ACASLContext:  # type: ignore
            pass

        def open_acasl_loader_dialog(self):  # type: ignore
            try:
                if hasattr(self, "log") and self.log:
                    self.log.append("ℹ️ ACASL Loader indisponible.")
            except Exception:
                pass
