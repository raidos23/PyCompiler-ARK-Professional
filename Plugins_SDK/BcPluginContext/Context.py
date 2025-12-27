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

from pathlib import Path
from typing import Any, Union


# -----------------------------
# Plugin base (BCASL) and decorator
# -----------------------------
# Reuse BCASL types to guarantee compatibility with the host
try:  # noqa: E402
    from bcasl import (
        BCASL as BCASL,
        ExecutionReport as ExecutionReport,
        BcPluginBase as BcPluginBase,
        PluginMeta as PluginMeta,
        PreCompileContext as PreCompileContext,
    )

    try:
        from bcasl import (
            BCASL_PLUGIN_REGISTER_FUNC as BCASL_PLUGIN_REGISTER_FUNC,
            register_plugin as register_plugin,
        )
    except Exception:  # pragma: no cover

        def register_plugin(cls: Any) -> Any:  # type: ignore
            setattr(cls, "__bcasl_plugin__", True)
            return cls

        BCASL_PLUGIN_REGISTER_FUNC = "bcasl_register"
except Exception:  # pragma: no cover — dev fallback when BCASL is not importable

    class BcPluginBase:  # type: ignore
        pass

    class PluginMeta:  # type: ignore
        pass

    class PreCompileContext:
        pass

    def register_plugin(cls: Any) -> Any:  # type: ignore
        setattr(cls, "__bcasl_plugin__", True)
        return cls

    BCASL_PLUGIN_REGISTER_FUNC = "bcasl_register"


# -----------------------------
# Public bridge to set selected workspace from plugins
# -----------------------------

Pathish = Union[str, Path]


def set_selected_workspace(path: Pathish) -> bool:
    """Always accept workspace change requests (SDK-level contract).

    - Auto-creates the target directory if missing
    - Invokes the GUI-side bridge when available (non-blocking acceptance)
    - Returns True in all cases (including headless/no-GUI environments)
    """
    # Best-effort ensure the path exists
    try:
        p = Path(path)
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
    except Exception:
        pass
    # Try to inform the GUI when running with UI; ignore result and accept by contract
    try:
        from Core.MainWindow import request_workspace_change_from_BcPlugin  # type: ignore

        try:
            request_workspace_change_from_BcPlugin(str(path))
        except Exception:
            pass
    except Exception:
        # No GUI or bridge available — still accept
        pass
    return True


def Generate_Bc_Plugin_Template() -> str:
    """Retourne un modèle de plugin BC prêt à l'emploi.

    Le modèle est compatible avec le chargeur BCASL:
    - expose une classe de plugin décorée avec register_plugin
    - fournit la variable globale PLUGIN pour l'exécution sandbox
    - fournit la fonction bcasl_register(manager) pour l'enregistrement direct
    """
    return