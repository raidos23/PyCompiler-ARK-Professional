# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
API Plugin: PyArmor Obfuscation (self-contained, no utils dependency)

This BCASL plugin obfuscates selected Python sources using PyArmor.
- Reads configuration from bcasl.* (plugins.pyarmor) and a per‑plugin settings file.
- Checks PyArmor availability and proposes installation when missing.
- Uses API_SDK facilities (progress, run_command, safe paths) and writes a report.
"""
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

from API_SDK.BCASL_SDK import (
    PluginBase,
    PluginMeta,
    PreCompileContext,
    ensure_min_sdk,
    ensure_settings_file,
    ensure_system_pip_install,
    progress,
    wrap_context,
)

try:
    from API_SDK.BCASL_SDK import plugin  # preferred
except Exception:  # pragma: no cover
    from API_SDK import plugin
from API_SDK import set_selected_workspace

BCASL_PLUGIN = True
BCASL_ID = "pyarmor"
BCASL_DESCRIPTION = "Obfuscate Python sources with PyArmor"
BCASL_NAME = "PyArmor"
BCASL_VERSION = "0.1.2"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
BCASL_LICENSE = "GPL-3.0-only"
BCASL_TAGS = ["obfuscation", "protect"]


DEFAULT_SETTINGS = {
    # Inputs can be explicit paths OR discovered via globbing when glob_mode=True
    "inputs": ["main.py"],
    "inputs_glob": ["**/*.py"],  # evaluated within the workspace when glob_mode=True
    "glob_mode": False,

    # Output directory (relative to workspace by default)
    "out_dir": "obfuscated",

    # Recursion and symlink handling
    "recursive": True,
    "follow_symlinks": False,

    # Exclusions (broad by default; keep overkill to avoid polluting the output)
    "exclude_patterns": [
        "venv/**",
        "build/**",
        "dist/**",
        "tests/**",
        "__pycache__/**",
        ".git/**",
        ".hg/**",
        ".svn/**",
        ".idea/**",
        ".vscode/**",
        "node_modules/**",
        "*.egg-info/**",
    ],

    # Manifest file path; when manifest_auto=True a manifest may be generated from inputs/excludes
    "manifest": "",
    "manifest_auto": False,

    # Advanced options forwarded to `pyarmor gen` (None values are ignored)
    # Keep keys here for convenience; they are not applied unless set by the user.
    "advanced": {
        "platform": None,            # e.g., "linux.x86_64", "windows.x86_64" or comma-separated
        "obf-code": None,            # 0|1|2
        "obf-module": None,          # 0|1
        "restrict-mode": None,       # 0|1|2
        "mix-str": None,             # True to enable string mixing
        "keep-runtime": None,        # True to keep runtime package alongside outputs
        "no-cross-protection": None, # True to disable cross protection
        "bootstrap-code": None,      # Python statements injected at startup
        "enable-suffix": None,       # True to append obfuscated suffix
        "enable-assert-hook": None,  # True to protect assert
        "plugin": None,              # Optional PyArmor plugin name
    },

    # Dry run will only log the command and not execute
    "dry_run": False,

    # Execution controls
    "timeout_s": 1800,               # Max seconds for obfuscation command

    # Workspace controls
    "workspace": "",                # Optional: override selected workspace (absolute or relative)
    "post_switch_workspace": True,   # Switch to out_dir on success
}

# -----------------------------
# Local helpers (self-contained)
# -----------------------------


def _pyarmor_available(sctx) -> bool:
    """Detect PyArmor via 'pyarmor --version' or 'python -m pyarmor --version'."""
    rc, out, err = sctx.run_command(["pyarmor", "--version"], timeout_s=10)
    if rc == 0:
        return True
    rc, out, err = sctx.run_command(["python", "-m", "pyarmor", "--version"], timeout_s=10)
    return rc == 0


def _pyarmor_version(sctx) -> tuple[int, int, int]:
    """Return detected PyArmor version tuple or (0,0,0)."""
    for cmd in (["pyarmor", "--version"], ["python", "-m", "pyarmor", "--version"]):
        rc, out, err = sctx.run_command(cmd, timeout_s=10)
        if rc == 0:
            text = (out or err or "").strip()
            m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
            if m:
                return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return (0, 0, 0)


def _pyarmor_version_detail(sctx) -> str:
    """Return raw PyArmor version/license line (e.g., 'Pyarmor 9.1.8 (trial), 000000, non-profits')."""
    for cmd in (["pyarmor", "--version"], ["python", "-m", "pyarmor", "--version"]):
        rc, out, err = sctx.run_command(cmd, timeout_s=10)
        if rc == 0:
            return (out or err or "").strip()
    return ""


def _build_gen_args(
    inputs: Sequence[str],
    out_dir: str,
    *,
    recursive: bool = False,
    exclude: Optional[Sequence[str]] = None,
    manifest: Optional[str] = None,
    advanced: Optional[dict[str, Any]] = None,
) -> list[str]:
    """Build 'pyarmor gen' arguments for PyArmor 8+."""
    args: list[str] = ["gen", "-O", out_dir]
    if recursive:
        args.append("-r")
    if exclude:
        pattxt = ",".join(str(p) for p in exclude)
        if pattxt:
            args.extend(["--exclude", pattxt])
    if manifest:
        args.extend(["--manifest", str(manifest)])
    if advanced and isinstance(advanced, dict):
        for k, v in advanced.items():
            if v is None:
                continue
            if len(str(k)) == 1:
                args.extend([f"-{k}", str(v)])
            else:
                if isinstance(v, bool):
                    if v:
                        args.append(f"--{k}")
                else:
                    args.extend([f"--{k}", str(v)])
    for it in inputs:
        args.append(str(it))
    return args


def _run_pyarmor(
    sctx, args: Sequence[str], *, cwd: Optional[str] = None, timeout_s: int = 1800
) -> tuple[int, str, str, list[str]]:
    """Run PyArmor with given args using either 'pyarmor' or 'python -m pyarmor'."""
    runner: list[str]
    rc, _out, _err = sctx.run_command(["pyarmor", "--version"], timeout_s=5)
    if rc == 0:
        runner = ["pyarmor"]
    else:
        runner = ["python", "-m", "pyarmor"]
    cmd = [*runner, *args]
    rc, out, err = sctx.run_command(cmd, cwd=str(cwd) if cwd else None, timeout_s=timeout_s)
    return int(rc), out, err, cmd


def _obfuscate(
    sctx,
    inputs: Sequence[str],
    out_dir: str,
    *,
    recursive: bool = False,
    exclude: Optional[Sequence[str]] = None,
    manifest: Optional[str] = None,
    advanced: Optional[dict[str, Any]] = None,
    cwd: Optional[str] = None,
    timeout_s: int = 1800,
) -> tuple[bool, dict[str, Any]]:
    args = _build_gen_args(inputs, out_dir, recursive=recursive, exclude=exclude, manifest=manifest, advanced=advanced)
    rc, out, err, cmd = _run_pyarmor(sctx, args, cwd=cwd, timeout_s=timeout_s)
    ok = rc == 0
    report = {
        "cmd": cmd[0],
        "args": args,
        "code": rc,
        "stdout": out,
        "stderr": err,
        "ok": ok,
    }
    return ok, report


@plugin(id=BCASL_ID, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
class PyArmorPlugin(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        if not ensure_min_sdk("3.2.3"):
            raise RuntimeError("API_SDK >= 3.2.3 required for PyArmor plugin")

        sctx = wrap_context(ctx)
        subcfg = sctx.config_view.for_plugin(self.id)
        # Non-interactive/headless mode guard (best effort)
        try:
            noninteractive = bool(getattr(sctx, "noninteractive", False) or getattr(sctx, "is_noninteractive", False))
        except Exception:
            noninteractive = False

        # Optional: change selected workspace via API_SDK bridge if requested
        req_ws_val = subcfg.get("workspace", None)
        req_ws = req_ws_val.strip() if isinstance(req_ws_val, str) else None
        if req_ws:
            try:
                p = Path(req_ws)
                if not p.is_absolute():
                    # Resolve relative to current workspace
                    p = (sctx.workspace_root / p).resolve()
                ok = set_selected_workspace(str(p))
                if ok:
                    sctx.log_info(f"[pyarmor] Workspace changed to: {p}")
                    # Refresh context to reflect new selection
                    sctx = wrap_context(ctx)
                    subcfg = sctx.config_view.for_plugin(self.id)
                else:
                    sctx.log_warn(f"[pyarmor] Workspace change refused: {p}")
            except Exception as e:
                sctx.log_warn(f"[pyarmor] Invalid workspace path '{req_ws}': {e}")

        # Ensure a per-plugin settings file exists (editable by users)
        settings_path = ensure_settings_file(
            sctx, subdir="config", basename="pyarmor", fmt="yaml", defaults=DEFAULT_SETTINGS, overwrite=False
        )
        sctx.log_info(f"[pyarmor] Settings file: {settings_path}")

        # Resolve runtime configuration
        inputs: list[str] = subcfg.get("inputs", DEFAULT_SETTINGS["inputs"]) or DEFAULT_SETTINGS["inputs"]
        out_dir: str = subcfg.get("out_dir", DEFAULT_SETTINGS["out_dir"]) or DEFAULT_SETTINGS["out_dir"]
        recursive: bool = bool(subcfg.get("recursive", DEFAULT_SETTINGS["recursive"]))
        exclude_patterns: list[str] = (
            subcfg.get("exclude_patterns", DEFAULT_SETTINGS["exclude_patterns"]) or DEFAULT_SETTINGS["exclude_patterns"]
        )
        manifest: str = subcfg.get("manifest", DEFAULT_SETTINGS["manifest"]) or ""
        advanced: dict[str, Any] = subcfg.get("advanced", DEFAULT_SETTINGS["advanced"]) or {}
        dry_run: bool = bool(subcfg.get("dry_run", DEFAULT_SETTINGS["dry_run"]))
        # Overkill/versatile options
        glob_mode: bool = bool(subcfg.get("glob_mode", DEFAULT_SETTINGS.get("glob_mode", False)))
        inputs_glob: list[str] = subcfg.get("inputs_glob", DEFAULT_SETTINGS.get("inputs_glob", ["**/*.py"])) or DEFAULT_SETTINGS.get("inputs_glob", ["**/*.py"]) 
        follow_symlinks: bool = bool(subcfg.get("follow_symlinks", DEFAULT_SETTINGS.get("follow_symlinks", False)))
        timeout_s: int = int(subcfg.get("timeout_s", DEFAULT_SETTINGS.get("timeout_s", 1800)))
        post_switch_workspace: bool = bool(subcfg.get("post_switch_workspace", DEFAULT_SETTINGS.get("post_switch_workspace", True)))

        # Sanitize and resolve paths relative to workspace
        ws = sctx.workspace_root
        abs_inputs: list[str] = []
        for it in inputs:
            try:
                p = sctx.safe_path(it)
                if p.exists():
                    abs_inputs.append(str(p))
                else:
                    sctx.log_warn(f"[pyarmor] Input does not exist: {it}")
            except Exception:
                sctx.log_warn(f"[pyarmor] Invalid input: {it}")
        # Optional: discover inputs by globbing inside the workspace
        if glob_mode:
            discovered: list[str] = []
            try:
                # Prefer SDK iter_files when available
                try:
                    it = sctx.iter_files(patterns=list(inputs_glob or ["**/*.py"]), exclude=list(exclude_patterns or []), enforce_workspace=True)
                    for p in it:
                        try:
                            if p and getattr(p, "is_file", lambda: False)():
                                discovered.append(str(p))
                        except Exception:
                            pass
                except Exception:
                    # Fallback to pathlib globbing
                    for pat in list(inputs_glob or ["**/*.py"]):
                        try:
                            for p in ws.glob(pat):
                                try:
                                    if p.is_file():
                                        rp = str(p)
                                        # Exclude patterns match on full path
                                        if not any(p.match(ex) for ex in (exclude_patterns or [])):
                                            discovered.append(rp)
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
            if discovered:
                # Deduplicate while keeping order
                seen = set()
                for x in discovered:
                    if x not in seen:
                        seen.add(x)
                        abs_inputs.append(x)
        if not abs_inputs:
            sctx.log_warn("[pyarmor] No valid inputs to obfuscate; skipping")
            return
        out_path = sctx.safe_path(out_dir)
        try:
            out_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"[pyarmor] Unable to create output directory: {out_path}") from e

        # Ensure PyArmor available: ask authorization and use system helper when missing
        if not _pyarmor_available(sctx):
            sctx.log_warn("[pyarmor] PyArmor CLI not found.")
            ok = ensure_system_pip_install(
                sctx,
                ["pyarmor"],
                title="Install Python tool",
                body="Install 'pyarmor' system-wide now?",
                python_candidates=["/usr/bin/python3", "python3", "python"],
                timeout_s=900,
            )
            if not ok or not _pyarmor_available(sctx):
                sctx.log_warn("[pyarmor] PyArmor not installed; skipping obfuscation")
                return

        ver = _pyarmor_version(sctx)
        sctx.log_info(f"[pyarmor] Detected PyArmor version: {ver[0]}.{ver[1]}.{ver[2]}")
        # Bilingual message about detected version/license
        try:
            import platform as _platform

            detail = _pyarmor_version_detail(sctx)
            plat = f"{_platform.system()} {_platform.machine()}"
            title = "PyArmor — Version | Version"
            msg = (
                f"Version détectée : {detail}\nPlateforme : {plat}\n\n" f"Detected version: {detail}\nPlatform: {plat}"
            )
            if not noninteractive:
                sctx.msg_info(title, msg)
            low = (detail or "").lower()
            is_trial = any(k in low for k in ("trial", "non-profit", "nonprofits", "non-profits", "000000"))
            if is_trial and not noninteractive:
                warn = (
                    "Licence d'essai / non-profit détectée.\n"
                    "L'obfuscation peut échouer (ex: 'out of license').\n\n"
                    "Trial / non-profit license detected.\n"
                    "Obfuscation may fail (e.g., 'out of license')."
                )
                sctx.msg_warn("PyArmor — Licence | License", warn)
                q = "Continuer l'obfuscation ?\n\n" "Proceed with obfuscation?"
                if not sctx.msg_question("PyArmor — Continuer ? | Continue?", q, default_yes=True):
                    sctx.log_warn("[pyarmor] User canceled obfuscation due to trial license")
                    return
        except Exception:
            pass

        # Build args (supports PyArmor 8+ gen command)
        if dry_run:
            sctx.log_info("[pyarmor] Dry run enabled; generating command only")
            args = _build_gen_args(
                abs_inputs,
                str(out_path),
                recursive=recursive,
                exclude=exclude_patterns,
                manifest=(str(sctx.safe_path(manifest)) if manifest else None),
                advanced=advanced,
            )
            sctx.log_info("[pyarmor] Command: pyarmor " + " ".join(args))
            return

        # Run obfuscation with progress
        with progress("PyArmor", "Obfuscating...", maximum=1) as ph:
            ok, report = _obfuscate(
                sctx,
                abs_inputs,
                str(out_path),
                recursive=recursive,
                exclude=exclude_patterns,
                manifest=(str(sctx.safe_path(manifest)) if manifest else None) if manifest else None,
                advanced=advanced,
                cwd=str(ws),
                timeout_s=timeout_s,
            )
            try:
                ph.update(1, "Done")
            except Exception:
                pass
        # Save a report under the output directory
        try:
            import json

            rpt = out_path / "pyarmor_report.json"
            payload = json.dumps(report, indent=2, ensure_ascii=False)
            try:
                # Prefer atomic write when available in SDK context
                sctx.write_text_atomic(rpt, payload)
            except Exception:
                rpt.write_text(payload, encoding="utf-8")
            sctx.log_info(f"[pyarmor] Report saved: {rpt}")
        except Exception:
            pass
        # On success, optionally switch the selected workspace to the obfuscated output directory
        if ok and post_switch_workspace:
            try:
                switched = set_selected_workspace(str(out_path))
                if switched:
                    sctx.log_info(f"[pyarmor] Workspace switched to obfuscated output: {out_path}")
                else:
                    sctx.log_warn(f"[pyarmor] Workspace switch refused: {out_path}")
            except Exception as e:
                sctx.log_warn(f"[pyarmor] Failed to switch workspace: {e}")
        elif ok:
            sctx.log_info("[pyarmor] post_switch_workspace=False; keeping current workspace")
        if not ok:
            try:
                out = (report.get("stdout") or "") + "\n" + (report.get("stderr") or "")
                if "out of license" in out.lower():
                    sctx.msg_warn(
                        "PyArmor — Erreur licence | License error",
                        "Obfuscation échouée: licence PyArmor insuffisante ou trial.\n\n"
                        "Obfuscation failed: insufficient or trial PyArmor license.",
                    )
            except Exception:
                pass
            raise RuntimeError("[pyarmor] Obfuscation reported an error; see logs")


META = PluginMeta(id=BCASL_ID, name=BCASL_NAME, version=BCASL_VERSION, description=BCASL_DESCRIPTION)
PLUGIN = PyArmorPlugin(META)


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
