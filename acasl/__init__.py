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

from .executor import ACASL


__all__ = (
    # Loader API
    "run_post_compile_async",
    "ensure_acasl_thread_stopped",
    "ACASLContext",
    "open_ac_loader_dialog",
    # Plugin system
    "AcPluginBase",
    "PluginMeta",
    "PostCompileContext",
    "ExecutionReport",
    "executor",
)

__version__ = "1.0.0"

# Preferred: loader in this package
try:  # pragma: no cover
    from .Loader import (  # type: ignore
        ACASLContext,
        ensure_acasl_thread_stopped,
        open_ac_loader_dialog,
        run_post_compile_async,
    )

    # Also import plugin system
    from .Base import (  # type: ignore
        AcPluginBase,
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
            open_ac_loader_dialog,
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

        def open_ac_loader_dialog(self):  # type: ignore
            try:
                if hasattr(self, "log") and self.log:
                    self.log.append("ℹ️ ACASL Loader indisponible.")
            except Exception:
                pass
