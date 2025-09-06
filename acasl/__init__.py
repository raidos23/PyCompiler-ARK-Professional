# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations
"""
ACASL (After Compilation Advanced System Loader)

This package exposes the public ACASL API for post‑compilation steps.
Primary exports:
- run_post_compile_async(gui, artifacts, finished_cb=None)
- ensure_acasl_thread_stopped(gui=None)
- ACASLContext

Preferred loader in-package: 'acasl/acasl_loader.py'; fallback to 'utils/acasl_loader.py' for backward compatibility.
"""

__all__ = (
    "run_post_compile_async",
    "ensure_acasl_thread_stopped",
    "ACASLContext",
    "open_acasl_loader_dialog",
)

__version__ = "1.1.0"

# Preferred: loader in this package
try:  # pragma: no cover
    from .acasl_loader import run_post_compile_async, ensure_acasl_thread_stopped, ACASLContext, open_acasl_loader_dialog  # type: ignore
except Exception:  # pragma: no cover
    # Fallback to legacy location
    try:
        from utils.acasl_loader import run_post_compile_async, ensure_acasl_thread_stopped, ACASLContext, open_acasl_loader_dialog  # type: ignore
    except Exception:
        # Last-resort no-op stubs to avoid crashes if loader is missing
        def run_post_compile_async(gui, artifacts, finished_cb=None):  # type: ignore
            try:
                if hasattr(gui, 'log') and gui.log:
                    gui.log.append("⚠️ ACASL indisponible (aucun loader trouvé).")
            except Exception:
                pass
        def ensure_acasl_thread_stopped(gui=None):  # type: ignore
            try:
                if gui is not None:
                    setattr(gui, '_closing', True)
            except Exception:
                pass
        class ACASLContext:  # type: ignore
            pass
        def open_acasl_loader_dialog(self):  # type: ignore
            try:
                if hasattr(self, 'log') and self.log:
                    self.log.append("ℹ️ ACASL Loader indisponible.")
            except Exception:
                pass
