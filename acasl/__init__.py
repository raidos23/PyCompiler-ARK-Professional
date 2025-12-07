# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from .executor import ACASL


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
    "executor",
)

__version__ = "1.1.0"

# Preferred: loader in this package
try:  # pragma: no cover
    from .Loader import (  # type: ignore
        ACASLContext,
        ensure_acasl_thread_stopped,
        open_acasl_loader_dialog,
        run_post_compile_async,
    )

    # Also import plugin system
    from .Base import (  # type: ignore
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
