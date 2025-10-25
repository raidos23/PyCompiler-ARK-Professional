# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
engine_sdk.utils — Robust helpers for engine authors

These helpers improve safety and reliability when building engine commands,
validating paths, and preparing environments.

Typical usage (inside an engine plugin):

    from engine_sdk.utils import (
        redact_secrets,
        is_within_workspace,
        safe_join,
        validate_args,
        build_env,
        clamp_text,
        normalized_program_and_args,
    )

    class MyEngine(CompilerEngine):
        id = "my_engine"; name = "My Engine"
        def program_and_args(self, gui, file: str):
            ws = gui.workspace_dir
            program = safe_join(ws, "venv", "bin", "myprog")
            args = validate_args(["--build", file])
            prog, args = normalized_program_and_args(program, args)
            return prog, args
"""

import os
import platform
import re
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional, Union

try:
    from PySide6.QtCore import QProcess  # type: ignore
except Exception:  # pragma: no cover - optional at import time
    QProcess = None  # type: ignore


Pathish = Union[str, Path]

# -------------------------------
# Secret redaction for logs
# -------------------------------
_REDACT_PATTERNS = [
    re.compile(r"(password\s*[:=]\s*)([^\s]+)", re.IGNORECASE),
    re.compile(r"(authorization\s*[:]\s*bearer\s+)([A-Za-z0-9\-_.]+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)([A-Za-z0-9\-_.]{12,})", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Return text with obvious secrets masked to avoid log leakage."""
    if not text:
        return text
    redacted = str(text)
    try:
        for pat in _REDACT_PATTERNS:
            redacted = pat.sub(lambda m: m.group(1) + "<redacted>", redacted)
    except Exception:
        pass
    return redacted


# -------------------------------
# Workspace path safety
# -------------------------------


def is_within_workspace(workspace: Pathish, p: Pathish) -> bool:
    """True if path p resolves within workspace."""
    try:
        ws = Path(workspace).resolve()
        rp = Path(p).resolve()
        _ = rp.relative_to(ws)
        return True
    except Exception:
        return False


def safe_join(workspace: Pathish, *parts: Pathish) -> Path:
    """Join parts under workspace and ensure the resolved path stays within it.
    Raises ValueError if the result escapes the workspace.
    """
    base = Path(workspace)
    p = base
    for part in parts:
        p = p / Path(part)
    rp = p.resolve()
    if not is_within_workspace(base, rp):
        raise ValueError(f"Path escapes workspace: {rp}")
    return rp


# -------------------------------
# Args and environment hardening
# -------------------------------


def validate_args(args: Sequence[Any], *, max_len: int = 4096) -> list[str]:
    """Normalize/validate CLI arguments:
    - Convert Path-like and numbers to str
    - Reject None and control characters/newlines
    - Enforce a max length per arg
    """
    out: list[str] = []
    for a in args:
        if a is None:
            raise ValueError("Argument is None")
        s = str(a)
        if any(ch in s for ch in ("\n", "\r", "\x00")):
            raise ValueError(f"Invalid control character in argument: {s!r}")
        if len(s) > max_len:
            raise ValueError(f"Argument too long (> {max_len} chars)")
        out.append(s)
    return out


_DEF_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMP", "TEMP")


def build_env(
    base: Optional[Mapping[str, str]] = None,
    *,
    whitelist: Optional[Sequence[str]] = None,
    extra: Optional[Mapping[str, str]] = None,
    minimal_path: Optional[str] = None,
) -> dict[str, str]:
    """Construct a minimal environment map for subprocess/QProcess.
    - Start from an empty map or a provided 'base'
    - Keep only whitelisted keys (defaults to a sensible minimal set)
    - Override/add with 'extra'
    - Set PATH to minimal_path if provided
    """
    env: dict[str, str] = {}
    src = dict(base or {})
    allow = set(whitelist or _DEF_ENV_KEYS)
    for k, v in src.items():
        if k in allow and isinstance(v, str):
            env[k] = v
    if minimal_path is not None:
        env["PATH"] = minimal_path
    if extra:
        for k, v in extra.items():
            if isinstance(k, str) and isinstance(v, str):
                env[k] = v
    return env


# -------------------------------
# Output/log safety
# -------------------------------


def clamp_text(text: str, *, max_len: int = 10000) -> str:
    """Clamp long text to max_len characters (suffix with …)."""
    if text is None:
        return ""
    s = str(text)
    return s if len(s) <= max_len else (s[: max_len - 1] + "…")


# -------------------------------
# Normalization helpers
# -------------------------------


def normalized_program_and_args(program: Pathish, args: Sequence[Any]) -> tuple[str, list[str]]:
    """Return (program, args) as (str, list[str]) with basic validation.
    - Ensure program is a string path
    - Validate args with validate_args
    """
    prog_str = str(program)
    return prog_str, validate_args(args)


# -------------------------------
# i18n & logging helpers
# -------------------------------


def tr(gui: Any, fr: str, en: str) -> str:
    """Robust translator wrapper using the host GUI translator when available."""
    try:
        fn = getattr(gui, "tr", None)
        if callable(fn):
            return fn(fr, en)
    except Exception:
        pass
    # Fallback: prefer English when current_language is English
    try:
        cur = getattr(gui, "current_language", None)
        if isinstance(cur, str) and cur.lower().startswith("en"):
            return en
    except Exception:
        pass
    return fr


essential_log_max_len = 10000


def safe_log(gui: Any, text: str, *, redact: bool = True, clamp: bool = True) -> None:
    """Append text to GUI log safely (or print), with optional redaction and clamping."""
    try:
        msg = str(text)
        if redact:
            msg = redact_secrets(msg)
        if clamp:
            msg = clamp_text(msg, max_len=essential_log_max_len)
        if hasattr(gui, "log") and getattr(gui, "log") is not None:
            try:
                gui.log.append(msg)
                return
            except Exception:
                pass
        print(msg)
    except Exception:
        try:
            print(text)
        except Exception:
            pass


# -------------------------------
# Executable resolution helper
# -------------------------------


def resolve_executable(program: Pathish, base_dir: Optional[Pathish] = None, *, prefer_path: bool = True) -> str:
    """Resolve an executable path according to a clear, cross-platform policy.

    - Absolute program path: returned as-is.
    - Bare command (no path separator) and prefer_path=True: use shutil.which to resolve real path if available;
      otherwise return the command name (so the OS can resolve it via PATH at runtime).
    - Otherwise: join relative to base_dir (or CWD) and return an absolute path.
    """
    prog = str(program)
    try:
        # Absolute path -> as is
        if os.path.isabs(prog):
            return prog
        bare = (os.path.sep not in prog) and (not prog.startswith("."))
        if prefer_path and bare:
            try:
                found = shutil.which(prog)
                if found:
                    return found
            except Exception:
                pass
            # Keep bare command to allow OS PATH resolution later
            return prog
        # Else, resolve relative to base_dir (or CWD)
        base = str(base_dir) if base_dir is not None else os.getcwd()
        return os.path.abspath(os.path.join(base, prog))
    except Exception:
        # Fallback: return the original string
        return prog


# Fallback: host-level resolver override if available; else use SDK's resolve_executable
try:  # pragma: no cover
    from Core.engines_loader.external import resolve_executable_path as resolve_executable_path  # type: ignore
except Exception:  # pragma: no cover

    def resolve_executable_path(
        program: Pathish, base_dir: Optional[Pathish] = None, *, prefer_path: bool = True
    ) -> str:  # type: ignore
        return resolve_executable(program, base_dir, prefer_path=prefer_path)


# -------------------------------
# OS helpers
# -------------------------------


def open_path(path: Pathish) -> bool:
    """Open a file or directory with the OS default handler. Returns True on attempt."""
    try:
        p = str(path)
        sysname = platform.system()
        if sysname == "Windows":
            os.startfile(p)  # type: ignore[attr-defined]
        elif sysname == "Linux":
            import subprocess

            subprocess.run(["xdg-open", p])
        else:
            import subprocess

            subprocess.run(["open", p])
        return True
    except Exception:
        return False


def open_dir_candidates(candidates: Sequence[Pathish]) -> Optional[str]:
    """Open the first existing directory from candidates, return the opened path or None."""
    for c in candidates:
        try:
            d = str(c)
            if d and os.path.isdir(d):
                if open_path(d):
                    return d
        except Exception:
            continue
    return None


# ---------------------------------------------
# Universal output directory discovery and open
# ---------------------------------------------
from collections.abc import Sequence as _Seq


def discover_output_candidates(
    gui: Any,
    engine_id: Optional[str] = None,
    source_file: Optional[Pathish] = None,
    artifacts: Optional[_Seq[Pathish]] = None,
) -> list[str]:
    """Discover plausible output directory candidates in a plug-and-play manner.

    Strategy (generic; no engine-specific dependencies):
      1) GUI fields likely representing output directories (heuristic: names containing 'output'/'dist' and 'dir'/'path').
      2) Directories of known artifacts (if provided).
      3) Conventional fallbacks under the workspace (dist/, build/, <base>.dist).

    Returns an ordered list of unique path strings; non-existing paths are allowed (will be filtered by opener).
    """
    cands: list[str] = []

    def _add(p: Optional[Pathish]) -> None:
        try:
            if not p:
                return
            s = str(p).strip()
            if s and s not in cands:
                cands.append(s)
        except Exception:
            pass

    try:
        ws = getattr(gui, "workspace_dir", None) or os.getcwd()
    except Exception:
        ws = os.getcwd()

    # 1) GUI fields (global common fields and heuristic scan)
    try:
        out = getattr(gui, "output_dir_input", None)
        if out and hasattr(out, "text") and callable(out.text):
            _add(out.text())
    except Exception:
        pass

    # Heuristic scan of GUI attributes for line edits that look like output fields
    try:
        for nm in dir(gui):
            try:
                w = getattr(gui, nm)
            except Exception:
                continue
            if not w or not hasattr(w, "text") or not callable(w.text):
                continue
            label_parts: list[str] = [nm]
            try:
                on = getattr(w, "objectName", None)
                if callable(on):
                    label_parts.append(str(on()))
                elif isinstance(on, str):
                    label_parts.append(on)
            except Exception:
                pass
            try:
                an = getattr(w, "accessibleName", None)
                if callable(an):
                    label_parts.append(str(an()))
                elif isinstance(an, str):
                    label_parts.append(an)
            except Exception:
                pass
            lab = " ".join([str(x) for x in label_parts if x]).lower()
            if any(tok in lab for tok in ("output", "dist")) and any(tok in lab for tok in ("dir", "path")):
                try:
                    _add(w.text())
                except Exception:
                    pass
    except Exception:
        pass

    # 2) Artifacts parents (most recent first)
    try:
        arts = artifacts
        if arts is None:
            arts = getattr(gui, "_last_artifacts", None)
        parents: list[tuple[float, str]] = []
        if arts:
            for a in arts:
                try:
                    ap = str(a)
                    d = os.path.dirname(ap)
                    mt = os.path.getmtime(ap) if os.path.exists(ap) else 0.0
                    parents.append((mt, d))
                except Exception:
                    continue
            for _mt, d in sorted(parents, key=lambda t: t[0], reverse=True):
                _add(d)
    except Exception:
        pass

    # 3) Conventional fallbacks
    try:
        _add(os.path.join(ws, "dist"))
        _add(os.path.join(ws, "build"))
        if source_file:
            try:
                base = os.path.splitext(os.path.basename(str(source_file)))[0]
                _add(os.path.join(ws, f"{base}.dist"))
            except Exception:
                pass
    except Exception:
        pass

    return cands


def open_output_directory(
    gui: Any,
    engine_id: Optional[str] = None,
    source_file: Optional[Pathish] = None,
    artifacts: Optional[_Seq[Pathish]] = None,
) -> Optional[str]:
    """Open a plausible output directory for the last successful build using generic discovery.

    Does not call engine hooks; respects plug-and-play by avoiding engine-specific code paths.
    Returns the opened directory path or None if none found.
    """
    try:
        cands = discover_output_candidates(gui, engine_id=engine_id, source_file=source_file, artifacts=artifacts)
        return open_dir_candidates(cands) if cands else None
    except Exception:
        return None


# Filesystem safety helpers


def ensure_dir(path: Pathish) -> Path:
    """Ensure directory exists and return its Path."""
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def atomic_write_text(path: Pathish, text: str, *, encoding: str = "utf-8") -> bool:
    """Write text atomically with a temp file and rename. Returns True on success."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    import tempfile

    try:
        fd, tmp = tempfile.mkstemp(prefix=".sdk_", dir=str(target.parent))
        try:
            with open(fd, "w", encoding=encoding) as f:
                f.write(text)
            os.replace(tmp, str(target))
            try:
                os.chmod(str(target), 0o644)
            except Exception:
                pass
            return True
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
    except Exception:
        return False


# Generic process runner for engines


def run_process(
    gui: Any,
    program: Pathish,
    args: Sequence[Any],
    *,
    cwd: Optional[Pathish] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout_ms: int = 300000,
    on_stdout: Optional[Any] = None,
    on_stderr: Optional[Any] = None,
) -> tuple[int, str, str]:
    """Run a process using QProcess when available, else subprocess.

    Returns (exit_code, stdout, stderr). Honors working directory and environment when provided.
    Optional callbacks on_stdout/on_stderr are invoked (with full buffers) after completion.
    """
    prog_str, arg_list = normalized_program_and_args(program, args)

    # Default working directory from GUI if not specified
    if cwd is None:
        try:
            ws = getattr(gui, "workspace_dir", None)
            if ws:
                cwd = ws
        except Exception:
            cwd = None

    t0 = time.perf_counter()

    if QProcess is not None:
        try:
            proc = QProcess(gui)
            proc.setProgram(prog_str)
            proc.setArguments(arg_list)
            try:
                if cwd:
                    proc.setWorkingDirectory(str(cwd))
            except Exception:
                pass
            try:
                if env:
                    proc.setEnvironment(
                        [f"{k}={v}" for k, v in env.items() if isinstance(k, str) and isinstance(v, str)]
                    )
            except Exception:
                pass
            proc.start()
            finished = proc.waitForFinished(timeout_ms)
            if not finished:
                try:
                    proc.terminate()
                    proc.waitForFinished(5000)
                except Exception:
                    pass
                try:
                    proc.kill()
                    proc.waitForFinished(2000)
                except Exception:
                    pass
            try:
                out_bytes = proc.readAllStandardOutput().data()
                err_bytes = proc.readAllStandardError().data()
                out = out_bytes.decode(errors="ignore") if isinstance(out_bytes, (bytes, bytearray)) else str(out_bytes)
                err = err_bytes.decode(errors="ignore") if isinstance(err_bytes, (bytes, bytearray)) else str(err_bytes)
            except Exception:
                out, err = "", ""
            code = int(proc.exitCode())
            try:
                if callable(on_stdout) and out:
                    on_stdout(out)
                if callable(on_stderr) and err:
                    on_stderr(err)
            except Exception:
                pass
            return code, out, err
        except Exception:
            # fallback to subprocess below
            pass

    # Fallback: subprocess
    try:
        completed = subprocess.run(
            [prog_str, *arg_list],
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env else None,
            timeout=max(1, int(timeout_ms / 1000)),
            capture_output=True,
            text=True,
        )
        out = completed.stdout or ""
        err = completed.stderr or ""
        try:
            if callable(on_stdout) and out:
                on_stdout(out)
            if callable(on_stderr) and err:
                on_stderr(err)
        except Exception:
            pass
        return int(completed.returncode), out, err
    except Exception as e:
        return 1, "", str(e)


# -------------------------------
# venv/pip helpers
# -------------------------------


def resolve_project_venv(gui: Any) -> Optional[str]:
    """Resolve the project venv path using VenvManager when available, else workspace/venv."""
    try:
        vm = getattr(gui, "venv_manager", None)
        if vm:
            vroot = vm.resolve_project_venv()
            if vroot and os.path.isdir(vroot):
                return vroot
    except Exception:
        pass
    try:
        ws = getattr(gui, "workspace_dir", None)
        if ws:
            v = os.path.join(ws, "venv")
            return v if os.path.isdir(v) else None
    except Exception:
        pass
    return None


def pip_executable(vroot: str) -> str:
    """Return pip executable path under a venv root (cross-platform)."""
    name = "pip.exe" if platform.system() == "Windows" else "pip"
    return os.path.join(vroot, "Scripts" if platform.system() == "Windows" else "bin", name)


def pip_show(gui: Any, pip_exe: str, package: str, *, timeout_ms: int = 180000) -> int:
    """Run 'pip show <package>' and return exit code (0 if installed).
    Falls back to 'python -m pip' if the venv pip executable is missing.
    """
    prog = pip_exe
    args = ["show", package]
    try:
        if not os.path.isfile(pip_exe):
            import sys as _sys

            prog = _sys.executable
            args = ["-m", "pip", "show", package]
    except Exception:
        try:
            import sys as _sys

            prog = _sys.executable
            args = ["-m", "pip", "show", package]
        except Exception:
            prog = pip_exe
            args = ["show", package]
    code, _out, _err = run_process(gui, prog, args, timeout_ms=timeout_ms)
    return int(code)


def pip_install(gui: Any, pip_exe: str, package: str, *, timeout_ms: int = 600000) -> int:
    """Run 'pip install <package>' and return exit code (0 if success).
    - Uses the venv pip when available, else falls back to 'python -m pip'
    - Retries once on failure after a short delay to improve robustness.
    """
    prog = pip_exe
    args = ["install", package]
    try:
        if not os.path.isfile(pip_exe):
            import sys as _sys

            prog = _sys.executable
            args = ["-m", "pip", "install", package]
    except Exception:
        try:
            import sys as _sys

            prog = _sys.executable
            args = ["-m", "pip", "install", package]
        except Exception:
            prog = pip_exe
            args = ["install", package]
    code, _out, _err = run_process(gui, prog, args, timeout_ms=timeout_ms)
    if code != 0:
        try:
            time.sleep(1.0)
        except Exception:
            pass
        code, _out, _err = run_process(gui, prog, args, timeout_ms=timeout_ms)
    return int(code)
