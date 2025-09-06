# SPDX-License-Identifier: GPL-3.0-only
"""
API_SDK.BCASL_SDK — Convenience facade for BCASL (pre‑compile) plugin development

This subpackage exposes a focused set of utilities tailored for BCASL plugins,
so developers can import from a single, stable location.

Typical usage in API/<plugin_pkg>/__init__.py:

    from API_SDK.BCASL_SDK import plugin, PluginBase, PreCompileContext, wrap_context

    @plugin(id="your_id", version="0.1.0", description="...")
    class MyPlugin(PluginBase):
        def on_pre_compile(self, ctx: PreCompileContext) -> None:
            sctx = wrap_context(ctx)
            # use sctx helpers: files, subprocess, i18n, messages, etc.

Exports include:
- Version & capabilities: __version__, ensure_min_sdk, sdk_info, get_capabilities
- Progress & messages: ProgressHandle, create_progress, progress, show_msgbox, sys_msgbox_for_installing
- Config: ConfigView, load_workspace_config, ensure_settings_file
- Context: SDKContext, PreCompileContext, wrap_context
- BCASL types: PluginBase, PluginMeta, ExecutionReport, BCASL, register_plugin, BCASL_PLUGIN_REGISTER_FUNC
- i18n helpers: normalize_lang_pref, available_languages, resolve_system_language, get_translations, load_plugin_translations
- Subprocess: run_command
- Scaffolding: scaffold_plugin
"""
from __future__ import annotations

import platform
import shutil
from collections.abc import Sequence
from typing import Optional

# Re-export from the main API_SDK
from API_SDK import (
    BCASL,
    BCASL_PLUGIN_REGISTER_FUNC,
    # Config
    ConfigView,
    ExecutionReport,
    # BCASL types
    PluginBase,
    PluginMeta,
    PreCompileContext,
    # Progress
    ProgressHandle,
    # Context
    SDKContext,
    __version__,
    available_languages,
    create_progress,
    ensure_min_sdk,
    ensure_settings_file,
    get_capabilities,
    get_translations,
    load_plugin_translations,
    load_workspace_config,
    # i18n
    normalize_lang_pref,
    progress,
    register_plugin,
    resolve_system_language,
    # Subprocess
    run_command,
    # Scaffolding
    scaffold_plugin,
    sdk_info,
    show_msgbox,
    sys_msgbox_for_installing,
    wrap_context,
)

# --- System installation helper for BCASL plugins ---


def _is_noninteractive(sctx) -> bool:
    try:
        return bool(getattr(sctx, "noninteractive", False) or getattr(sctx, "is_noninteractive", False))
    except Exception:
        return False


def ensure_system_pip_install(
    sctx,
    packages: Sequence[str],
    *,
    title: str = "Installer dépendances système",
    body: Optional[str] = None,
    python_candidates: Optional[Sequence[str]] = None,
    timeout_s: int = 900,
) -> bool:
    """Ask user authorization then attempt a system-level pip install for packages.

    - Asks consent via sctx.sys_msgbox_for_installing(name, message) when available,
      else falls back to sctx.msg_question(title, body, default_yes=False).
    - Tries multiple Python interpreters (default: /usr/bin/python3, python3, python)
    - Retries with '--break-system-packages' on Debian/Ubuntu when standard pip blocks system writes.
    - Returns True if installation succeeds, False otherwise.
    """
    pkgs = [str(p).strip() for p in (packages or []) if str(p).strip()]
    if not pkgs:
        return True
    if _is_noninteractive(sctx):
        try:
            if hasattr(sctx, "log_warn"):
                sctx.log_warn("System installation skipped (non-interactive mode)")
        except Exception:
            pass
        return False
    consent = False
    msg = body or f"Install system-wide: {', '.join(pkgs)} ?"
    try:
        fn = getattr(sctx, "sys_msgbox_for_installing", None)
        if callable(fn):
            consent = bool(fn(", ".join(pkgs), msg))
        else:
            consent = bool(getattr(sctx, "msg_question", lambda *_args, **_kw: False)(title, msg, default_yes=False))
    except Exception:
        consent = False
    if not consent:
        try:
            if hasattr(sctx, "log_warn"):
                sctx.log_warn("System installation canceled by user")
        except Exception:
            pass
        return False
    candidates = list(python_candidates or ["/usr/bin/python3", "python3", "python"])
    last_err = ""
    for py in candidates:
        try:
            rc, _out, err = getattr(sctx, "run_command", run_command)(
                [py, "-m", "pip", "install", *pkgs], timeout_s=timeout_s
            )
            if rc == 0:
                return True
            last_err = err or last_err
            # Debian/Ubuntu fallback when system pip refuses to write
            rc2, _out2, err2 = getattr(sctx, "run_command", run_command)(
                [py, "-m", "pip", "install", "--break-system-packages", *pkgs], timeout_s=timeout_s
            )
            if rc2 == 0:
                return True
            last_err = err2 or err or last_err
        except Exception as e:
            last_err = str(e) or last_err
            continue
    try:
        if hasattr(sctx, "log_error"):
            sctx.log_error(f"System pip install failed: {last_err}")
    except Exception:
        pass
    return False


# --- Native system package installation (apt/dnf/pacman/zypper/brew/winget/choco) ---


def _has_cmd(cmd: str) -> bool:
    try:
        return shutil.which(cmd) is not None
    except Exception:
        return False


def ensure_system_packages(
    sctx,
    packages: Sequence[str],
    *,
    title: str = "Installer des paquets système",
    body: Optional[str] = None,
    timeout_s: int = 3600,
) -> bool:
    """Ask authorization and install OS-level packages via the native package manager.

    Supports:
    - Linux: apt, dnf, pacman, zypper (wrapped with pkexec if available)
    - Windows: winget (preferred), fallback to choco if present
    - macOS: brew

    Returns True if all packages were installed successfully, False otherwise.
    """
    pkgs = [str(p).strip() for p in (packages or []) if str(p).strip()]
    if not pkgs:
        return True
    # Consent (skip if non-interactive)
    if _is_noninteractive(sctx):
        try:
            if hasattr(sctx, "log_warn"):
                sctx.log_warn("System packages install skipped (non-interactive mode)")
        except Exception:
            pass
        return False
    consent = False
    msg = body or ("Install system packages: " + ", ".join(pkgs) + " ?")
    try:
        fn = getattr(sctx, "sys_msgbox_for_installing", None)
        if callable(fn):
            consent = bool(fn(", ".join(pkgs), msg))
        else:
            consent = bool(getattr(sctx, "msg_question", lambda *_args, **_kw: False)(title, msg, default_yes=False))
    except Exception:
        consent = False
    if not consent:
        try:
            if hasattr(sctx, "log_warn"):
                sctx.log_warn("System packages install canceled by user")
        except Exception:
            pass
        return False
    sysname = platform.system()
    ok_all = True
    if sysname == "Linux":
        # Detect manager
        pm = None
        for cand in ("apt", "dnf", "pacman", "zypper"):
            if _has_cmd(cand):
                pm = cand
                break
        if not pm:
            try:
                if hasattr(sctx, "log_error"):
                    sctx.log_error("No supported package manager detected (apt/dnf/pacman/zypper)")
            except Exception:
                pass
            return False
        # Build command string
        if pm == "apt":
            cmd_core = "apt update && apt install -y " + " ".join(pkgs)
        elif pm == "dnf":
            cmd_core = "dnf install -y " + " ".join(pkgs)
        elif pm == "pacman":
            cmd_core = "pacman -Sy --noconfirm " + " ".join(pkgs)
        else:  # zypper
            cmd_core = "zypper install -y " + " ".join(pkgs)
        # Wrap with pkexec if available (GUI auth), else plain sudo
        if _has_cmd("pkexec"):
            full = ["pkexec", "bash", "-lc", cmd_core]
            rc, _out, err = getattr(sctx, "run_command", run_command)(full, timeout_s=timeout_s)
            ok_all = rc == 0
        else:
            # Best-effort without prompting for password (may fail)
            full = ["bash", "-lc", f"sudo -S {cmd_core}"]
            rc, _out, err = getattr(sctx, "run_command", run_command)(full, timeout_s=timeout_s)
            ok_all = rc == 0
        if not ok_all:
            try:
                if hasattr(sctx, "log_error"):
                    sctx.log_error(f"System packages install failed: {err}")
            except Exception:
                pass
    elif sysname == "Windows":
        # Prefer winget
        if _has_cmd("winget"):
            for pkg in pkgs:
                args = [
                    "winget",
                    "install",
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    pkg,
                ]
                rc, _out, err = getattr(sctx, "run_command", run_command)(args, timeout_s=timeout_s)
                if rc != 0:
                    ok_all = False
                    try:
                        if hasattr(sctx, "log_error"):
                            sctx.log_error(f"winget failed for {pkg}: {err}")
                    except Exception:
                        pass
        elif _has_cmd("choco"):
            for pkg in pkgs:
                args = ["choco", "install", "-y", pkg]
                rc, _out, err = getattr(sctx, "run_command", run_command)(args, timeout_s=timeout_s)
                if rc != 0:
                    ok_all = False
                    try:
                        if hasattr(sctx, "log_error"):
                            sctx.log_error(f"choco failed for {pkg}: {err}")
                    except Exception:
                        pass
        else:
            ok_all = False
            try:
                if hasattr(sctx, "log_error"):
                    sctx.log_error("No supported Windows package manager detected (winget/choco)")
            except Exception:
                pass
    elif sysname == "Darwin":
        if not _has_cmd("brew"):
            try:
                if hasattr(sctx, "log_error"):
                    sctx.log_error("Homebrew not detected; install from https://brew.sh/")
            except Exception:
                pass
            return False
        for pkg in pkgs:
            args = ["brew", "install", pkg]
            rc, _out, err = getattr(sctx, "run_command", run_command)(args, timeout_s=timeout_s)
            if rc != 0:
                ok_all = False
                try:
                    if hasattr(sctx, "log_error"):
                        sctx.log_error(f"brew failed for {pkg}: {err}")
                except Exception:
                    pass
    else:
        ok_all = False
        try:
            if hasattr(sctx, "log_error"):
                sctx.log_error(f"Unsupported OS for system packages: {sysname}")
        except Exception:
            pass
    return bool(ok_all)


__all__ = [
    # Version & caps
    "__version__",
    "ensure_min_sdk",
    "sdk_info",
    "get_capabilities",
    # Progress
    "ProgressHandle",
    "create_progress",
    "progress",
    "show_msgbox",
    "sys_msgbox_for_installing",
    # Config
    "ConfigView",
    "load_workspace_config",
    "ensure_settings_file",
    # Context
    "SDKContext",
    "PreCompileContext",
    "wrap_context",
    # BCASL types
    "PluginBase",
    "PluginMeta",
    "ExecutionReport",
    "BCASL",
    "register_plugin",
    "BCASL_PLUGIN_REGISTER_FUNC",
    # i18n
    "normalize_lang_pref",
    "available_languages",
    "resolve_system_language",
    "get_translations",
    "load_plugin_translations",
    # Subprocess
    "run_command",
    # Scaffolding
    "scaffold_plugin",
    "ensure_system_pip_install",
    "ensure_system_packages",
]
