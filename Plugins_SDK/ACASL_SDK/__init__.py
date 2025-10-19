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
from acasl import Ac_PluginBase, PluginMeta
# Re-export from the main Plugins_SDK to keep a single source of truth
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
    # Dialog creator
    ask_yes_no,
    request_permissions,
    request_text_input,
    Permission,
)

# --- Unified i18n helper for BCASL/ACASL plugins ---


def apply_plugin_i18n(plugin_instance, plugin_file_or_dir, tr_dict: dict, *, fallback_to_core: bool = True) -> dict:
    """Load and apply plugin-local i18n translations (async internally, sync interface).

    This helper provides a unified i18n system for BCASL/ACASL plugins, matching the engine pattern.
    Internally asynchronous for I/O efficiency, but wrapped for synchronous use.

    Args:
        plugin_instance: The plugin instance (self)
        plugin_file_or_dir: __file__ or plugin directory path
        tr_dict: Current app translations dict (from gui._tr or similar)
        fallback_to_core: If True, merge with core translations

    Returns:
        Loaded translation dict for the plugin

    Usage in plugin:
        from Plugins_SDK.ACASL_SDK import apply_plugin_i18n

        class MyPlugin(Ac_PluginBase):
            def on_post_compile(self, ctx):
                sctx = wrap_post_context(ctx)
                tr = apply_plugin_i18n(self, __file__, getattr(sctx, '_tr', {}))
                msg = tr.get('my_key', 'fallback text')
    """
    import asyncio
    
    async def _load_async() -> dict:
        """Asynchronous i18n loading implementation."""
        import json
        import os
        from pathlib import Path

        try:
            import importlib.resources as ilr
        except ImportError:
            ilr = None  # type: ignore

        # Resolve plugin directory
        try:
            p = Path(plugin_file_or_dir)
            plugin_dir = p if p.is_dir() else p.parent
        except Exception:
            plugin_dir = Path(".")

        # Get language code from app translations
        code = "en"
        try:
            if isinstance(tr_dict, dict):
                meta = tr_dict.get("_meta", {})
                if isinstance(meta, dict) and "code" in meta:
                    code = meta["code"]
        except Exception:
            pass

        # Build candidate list
        candidates = [code]
        if "-" in code:
            base = code.split("-")[0]
            if base not in candidates:
                candidates.append(base)
        if code.lower() != code:
            candidates.append(code.lower())
        if "en" not in candidates:
            candidates.append("en")

        # Load plugin translations asynchronously
        data = {}
        lang_dir = plugin_dir / "languages"

        async def _load_json_async(path: Path) -> dict:
            """Load JSON file asynchronously."""
            try:
                # Run file I/O in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                def _read():
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            return json.load(f) or {}
                    except Exception:
                        return {}
                return await loop.run_in_executor(None, _read)
            except Exception:
                return {}

        # Try each candidate
        for cand in candidates:
            try:
                # Direct file path
                json_file = lang_dir / f"{cand}.json"
                if json_file.exists():
                    data = await _load_json_async(json_file)
                    if data:
                        break
            except Exception:
                pass

            # Try importlib.resources if available
            if ilr and hasattr(plugin_instance, "__module__"):
                try:
                    pkg = plugin_instance.__module__.rsplit(".", 1)[0]
                    with ilr.as_file(ilr.files(pkg).joinpath("languages", f"{cand}.json")) as p:
                        if os.path.isfile(str(p)):
                            data = await _load_json_async(Path(str(p)))
                            if data:
                                break
                except Exception:
                    pass

        # Merge with core translations if requested
        if fallback_to_core and isinstance(tr_dict, dict):
            merged = dict(tr_dict)
            try:
                merged.update(data)
            except Exception:
                pass
            return merged
        return data

    # Run async function synchronously
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _load_async())
                return future.result()
        else:
            return asyncio.run(_load_async())
    except Exception:
        # Fallback: return empty dict on error
        return tr_dict if isinstance(tr_dict, dict) else {}


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


# Ac_PluginBase is imported from acasl module above


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
    # Dialog creator
    "ask_yes_no",
    "request_permissions",
    "request_text_input",
    "Permission",
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
    "apply_plugin_i18n",
    # Subprocess
    "run_command",
    # System installs
    "ensure_system_pip_install",
    "ensure_system_packages",
]
