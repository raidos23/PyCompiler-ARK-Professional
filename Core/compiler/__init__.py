"""
Logique de compilation pour PyCompiler Pro++.
Inclut la construction des commandes PyInstaller/Nuitka et la gestion des processus de compilation.
"""

from .compiler import (
    _kill_process_tree,
    _continue_compile_all,
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
    compile_all,
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
    "compile_all",
    "compute_for_all",
    "engines_loader",
]
