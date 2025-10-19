# SPDX-License-Identifier: GPL-3.0-only
"""
API_SDK.ACASL_SDK — Convenience facade for ACASL plugin development

This subpackage exposes a focused set of utilities tailored for post‑compile
(ACASL) plugins so developers can import from a single, stable location.

Typical usage in Plugins/acasl/*.py:

    from API_SDK.ACASL_SDK import Ac_PluginBase, wrap_post_context

    class MyPlugin(Ac_PluginBase):
        def on_post_compile(self, ctx):
            sctx = wrap_post_context(ctx)
            # sctx.artifacts -> list of produced files
            # Use helpers: sctx.run_command(...), sctx.safe_path(...), etc.

Exports include:
- Plugin base: Ac_PluginBase
- Version & capabilities: __version__, ensure_min_sdk, sdk_info, get_capabilities
- Progress & messages: ProgressHandle, create_progress, progress, show_msgbox, sys_msgbox_for_installing
- Config: ConfigView, load_workspace_config, ensure_settings_file
- Context: SDKContext, PostCompileContext, wrap_post_context
- i18n helpers: normalize_lang_pref, available_languages, resolve_system_language, get_translations, load_plugin_translations
- Subprocess: run_command
"""
from __future__ import annotations

import platform
import shutil
from collections.abc import Sequence
from typing import Any, Optional
from acasl import PluginMeta
# Re-export from the main API_SDK to keep a single source of truth
from Plugins_SDK import (
    # Config
    ConfigView,
    PostCompileContext,
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
    resolve_system_language,
    # Subprocess
    run_command,
    sdk_info,
    show_msgbox,
    sys_msgbox_for_installing,
    wrap_post_context,
)

# --- System installation helpers for ACASL plugins ---


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
    """Ask user authorization then attempt a system-level pip install for packages (post-compile context).

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
    """Ask authorization and install OS-level packages via the native package manager (post-compile context).

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
        if pm == "apt":
            cmd_core = "apt update && apt install -y " + " ".join(pkgs)
        elif pm == "dnf":
            cmd_core = "dnf install -y " + " ".join(pkgs)
        elif pm == "pacman":
            cmd_core = "pacman -Sy --noconfirm " + " ".join(pkgs)
        else:
            cmd_core = "zypper install -y " + " ".join(pkgs)
        if _has_cmd("pkexec"):
            full = ["pkexec", "bash", "-lc", cmd_core]
            rc, _out, err = getattr(sctx, "run_command", run_command)(full, timeout_s=timeout_s)
            ok_all = rc == 0
        else:
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


# --- ACASL Plugin Base Class ---


class Ac_PluginBase:
    """Base class for ACASL (post-compile) plugins.
    
    ACASL plugins are executed after compilation to perform post-processing tasks
    such as cleanup, optimization, or artifact transformation.
    
    Subclasses should implement one of the following methods:
    - on_post_compile(ctx: PostCompileContext) -> None
    - run(ctx: PostCompileContext) -> None
    - execute(ctx: PostCompileContext) -> None
    - acasl_run(ctx: PostCompileContext) -> None
    
    Metadata can be provided via:
    - Instance attributes: id, name, version, description
    - Nested meta object: meta.id, meta.name, meta.version, meta.description
    
    Example:
        class MyPlugin(Ac_PluginBase):
            def __init__(self):
                self.id = "my_plugin"
                self.name = "My Plugin"
                self.version = "1.0.0"
                self.description = "Does something useful"
            
            def on_post_compile(self, ctx):
                sctx = wrap_post_context(ctx)
                sctx.log_info("Post-compile processing...")
    """
    
    def __init__(self) -> None:
        """Initialize the plugin. Override to set metadata."""
        pass


__all__ = [
    # Plugin base
    "Ac_PluginBase",
    "PluginMeta",
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
    "PostCompileContext",
    "wrap_post_context",
    # i18n
    "normalize_lang_pref",
    "available_languages",
    "resolve_system_language",
    "get_translations",
    "load_plugin_translations",
    # Subprocess
    "run_command",
    # System installs
    "ensure_system_pip_install",
    "ensure_system_packages",
]
