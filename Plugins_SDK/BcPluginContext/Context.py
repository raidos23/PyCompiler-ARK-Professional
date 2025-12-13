# extension de capacité pour les plugins AC pour une meilleur affinité avec le logiciel et ainsi avoir plus de possibilité

# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Optional, Union


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

    def register_plugin(cls: Any) -> Any:  # type: ignore
        setattr(cls, "__bcasl_plugin__", True)
        return cls

    BCASL_PLUGIN_REGISTER_FUNC = "bcasl_register"


# -----------------------------
# Scaffolding utilities
# -----------------------------

BCPLUGIN_TEMPLATE = "\n".join([])


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


def Generate_Bc_Plugin_Template():
    # Cette methode doit pouvoir créer une base de plugin de type Bc avec le contenu de la variable BCPLUGIN_TEMPLATE
    pass
