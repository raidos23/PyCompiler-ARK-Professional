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
Logique de compilation pour PyCompiler ARK++.
Inclut la construction des commandes PyInstaller/Nuitka et la gestion des processus de compilation.
"""

from .compiler import _continue_compile_all, compile_all
from .mainprocess import (
    _kill_process_tree,
    _kill_all_descendants,
    try_install_missing_modules,
    try_start_processes,
    show_error_dialog,
    build_nuitka_command,
    build_pyinstaller_command,
    clamp_text,
    start_compilation_process,
    cancel_all_compilations,
    handle_finished,
    handle_stderr,
    handle_stdout,
    redact_secrets,
    compute_for_all,
    engines_loader,
)


__all__ = [
    "_kill_process_tree",
    "_continue_compile_all",
    "_kill_all_descendants",
    "try_install_missing_modules",
    "try_start_processes",
    "show_error_dialog",
    "build_nuitka_command",
    "build_pyinstaller_command",
    "clamp_text",
    "start_compilation_process",
    "cancel_all_compilations",
    "handle_finished",
    "handle_stderr",
    "handle_stdout",
    "redact_secrets",
    "compiler",
    "compute_for_all",
    "engines_loader",
    "compile_all",
]
