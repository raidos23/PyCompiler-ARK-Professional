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
]

__version__ = "1.0.0"
