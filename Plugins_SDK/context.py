# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
API_SDK.context — Execution context and file utilities for API plugins

This module provides the SDKContext class used by API plugins during the
pre-compilation phase (BCASL). It also includes common file operations and
helpers designed for safety and performance in large workspaces.
"""
import fnmatch
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union
import os

# Reuse i18n facade from host
# Local utility imports (UI helpers and message boxes)
from .progress import show_msgbox

Pathish = Union[str, Path]
LogFn = Callable[[str], None]

@dataclass
class SDKContext:
    """Execution context passed to API plugins (BCASL/ACASL).

    Attributes:
        workspace_root: Path to the user's workspace root
        config_view: Dict-backed configuration view (ConfigView-like)
        log_fn: Optional logging callback (GUI if available; stdout fallback)
        engine_id: Active engine identifier
        plugin_id: Current plugin id (set by PluginBase during execution)
        redact_logs: Whether to redact obvious secrets in logs
        debug_enabled: Emit debug logs when True
    """

    workspace_root: Path
    config_view: Any
    log_fn: Optional[LogFn] = None
    engine_id: Optional[str] = None
    plugin_id: Optional[str] = None
    artifacts: list[str] = field(default_factory=list)
    # ACASL-only scope: when set, all file operations are restricted to this directory
    allowed_dir: Optional[Path] = None
    redact_logs: bool = True
    debug_enabled: bool = False
    _iter_cache: dict[tuple[tuple[str, ...], tuple[str, ...]], list[Path]] = field(
        default_factory=dict, repr=False, compare=False
    )

    # ---------- Logging ----------
    def log(self, message: str) -> None:
        try:
            msg = str(message)
        except Exception:
            msg = message
        if self.log_fn:
            try:
                self.log_fn(msg)
                return
            except Exception:
                pass
        print(msg)

    def log_info(self, message: str) -> None:
        self.log(f"[INFO] {message}")

    def log_warn(self, message: str) -> None:
        self.log(f"[WARN] {message}")

    def log_error(self, message: str) -> None:
        self.log(f"[ERROR] {message}")
    # ---------- Message boxes ----------
    def show_msgbox(
        self, kind: str, title: str, text: str, *, default: Optional[str] = None
    ) -> Optional[bool]:
        return show_msgbox(kind, title, text, default=default)

    def msg_info(self, title: str, text: str) -> None:
        show_msgbox("info", title, text)

    def msg_warn(self, title: str, text: str) -> None:
        show_msgbox("warning", title, text)

    def msg_error(self, title: str, text: str) -> None:
        show_msgbox("error", title, text)

    def msg_question(self, title: str, text: str, default_yes: bool = True) -> bool:
        return bool(
            show_msgbox("question", title, text, default="Yes" if default_yes else "No")
        )
    # ---------- Environment/policy ----------
    @property
    def noninteractive(self) -> bool:
        try:
            import os as _os

            v = _os.environ.get("PYCOMPILER_NONINTERACTIVE")
            if v is None:
                return False
            return str(v).strip().lower() not in ("", "0", "false", "no")
        except Exception:
            return False

    def ui_available(self) -> bool:
        try:
            if self.noninteractive:
                return False
            from PySide6 import QtWidgets as _QtW2  # type: ignore

            return _QtW2.QApplication.instance() is not None
        except Exception:
            return False
    # ---------- Cancelation (ACASL-safe default) ----------
    def is_canceled(self) -> bool:
        """Return True if the current operation should be canceled.
        Default implementation for ACASL plugins; always False unless overridden
        by the host or extended context.
        """
        return False
    # ---------- Subprocess convenience ----------
    def run_command(
        self,
        cmd: list[str] | str,
        *,
        timeout_s: int = 60,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        shell: bool = False,
    ) -> tuple[int, str, str]:
        """Proxy to API_SDK.run_command to avoid direct imports here and keep modularity."""
        try:
            from Plugins_SDK import run_command as _run
        except Exception:
            # Minimal fallback if API_SDK.run_command is not accessible
            import os as _os
            import subprocess

            base_env = {
                k: v
                for k, v in _os.environ.items()
                if k in ("PATH", "LANG", "HOME", "LC_ALL", "LC_CTYPE")
            }
            if isinstance(env, dict):
                base_env.update({str(k): str(v) for k, v in env.items()})
            try:
                cp = subprocess.run(
                    cmd,
                    cwd=cwd,
                    env=base_env,
                    shell=bool(shell),
                    capture_output=True,
                    text=True,
                    timeout=int(timeout_s) if timeout_s else None,
                )
                return int(cp.returncode), cp.stdout or "", cp.stderr or ""
            except subprocess.TimeoutExpired as te:
                out = (
                    te.stdout.decode()
                    if isinstance(te.stdout, (bytes, bytearray))
                    else (te.stdout or "")
                )
                err = (
                    te.stderr.decode()
                    if isinstance(te.stderr, (bytes, bytearray))
                    else (te.stderr or "")
                )
                return -999, out, err
        rc, out, err = _run(cmd, timeout_s=timeout_s, cwd=cwd, env=env, shell=shell)
        try:

            def _clamp(s: str, n: int = 4000) -> str:
                return s if len(s) <= n else (s[:n] + "\n<...truncated...>")
            if rc == -999:
                self.log_warn(f"run_command timeout ({timeout_s}s): {cmd}")
            self.log_info(f"$ {cmd}\n[stdout]\n{_clamp(out)}\n[stderr]\n{_clamp(err)}")
        except Exception:
            pass
        return rc, out, err
    # ---------- File helpers ----------
    def path(self, *parts: Pathish) -> Path:
        p = self.workspace_root
        for part in parts:
            p = p / Path(part)
        return p

    def is_within_workspace(self, p: Path) -> bool:
        try:
            _ = p.resolve().relative_to(self.workspace_root.resolve())
            return True
        except Exception:
            return False

    def is_within_allowed(self, p: Path) -> bool:
        """Return True if path is within the allowed_dir (ACASL scope) when set; otherwise True."""
        try:
            if self.allowed_dir is None:
                return True
            _ = p.resolve().relative_to(self.allowed_dir.resolve())
            return True
        except Exception:
            return False

    def is_within_scope(self, p: Path) -> bool:
        """Scope check used by file helpers: within workspace and, when set, within allowed_dir."""
        try:
            return self.is_within_workspace(p) and self.is_within_allowed(p)
        except Exception:
            return False

    def safe_path(self, *parts: Pathish) -> Path:
        p = self.path(*parts).resolve()
        if not self.is_within_scope(p):
            raise ValueError(f"Path not allowed (outside output_dir/workspace): {p}")
        return p

    def require_files(self, paths: Sequence[Pathish]) -> list[Path]:
        missing: list[Path] = []
        for rel in paths:
            try:
                p = self.safe_path(rel)
            except Exception:
                missing.append(self.path(rel))
                continue
            if not p.exists():
                missing.append(p)
        return missing

    def open_text_safe(self, *parts: Pathish, max_size_mb: int = 5) -> Optional[str]:
        try:
            p = self.safe_path(*parts)
            if not p.is_file():
                return None
            size = p.stat().st_size
            if max_size_mb and size > max_size_mb * 1024 * 1024:
                return None
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    # ---------- Workspace scanning ----------
    def iter_files(
        self,
        patterns: Sequence[str],
        exclude: Sequence[str] = (),
        *,
        enforce_workspace: bool = True,
        max_files: Optional[int] = None,
    ) -> Iterable[Path]:
        root = self.allowed_dir or self.workspace_root
        ex_patterns = list(exclude or [])
        count = 0
        for p in root.rglob("*"):
            try:
                if not p.is_file():
                    continue
                if enforce_workspace and not self.is_within_scope(p):
                    continue
                rel = p.relative_to(root).as_posix()
                if ex_patterns and any(fnmatch.fnmatch(rel, ex) for ex in ex_patterns):
                    continue
                if not patterns or any(fnmatch.fnmatch(rel, pat) for pat in patterns):
                    yield p
                    count += 1
                    if (
                        isinstance(max_files, int)
                        and max_files > 0
                        and count >= max_files
                    ):
                        return
            except Exception:
                continue

    def iter_project_files(
        self,
        patterns: Optional[Sequence[str]] = None,
        exclude: Optional[Sequence[str]] = None,
        *,
        use_cache: bool = True,
        max_files: Optional[int] = None,
    ) -> Iterable[Path]:
        pats = (
            list(patterns)
            if patterns
            else (self.config_view.file_patterns or ["**/*.py"])
        )  # default to python files
        exc = list(exclude) if exclude else (self.config_view.exclude_patterns or [])
        key = None
        if use_cache:
            try:
                key = (tuple(sorted(pats)), tuple(sorted(exc)))
                cached = self._iter_cache.get(key)
                if cached is not None:
                    for cp in (
                        cached[:max_files]
                        if isinstance(max_files, int) and max_files > 0
                        else cached
                    ):
                        yield cp
                    return
            except Exception:
                key = None
        root = self.allowed_dir or self.workspace_root
        matches: list[Path] = []
        count = 0
        for p in root.rglob("*"):
            try:
                if not p.is_file():
                    continue
                if not self.is_within_scope(p):
                    continue
                rel = p.relative_to(root).as_posix()
                if exc and any(fnmatch.fnmatch(rel, ex) for ex in exc):
                    continue
                if pats and not any(fnmatch.fnmatch(rel, pat) for pat in pats):
                    continue
                matches.append(p)
                yield p
                count += 1
                if isinstance(max_files, int) and max_files > 0 and count >= max_files:
                    break
            except Exception:
                continue
        if use_cache and key is not None:
            try:
                self._iter_cache[key] = matches
            except Exception:
                pass
    # ---------- Replace helpers ----------
    def write_text_atomic(
        self,
        *parts: Pathish,
        text: str,
        create_dirs: bool = True,
        backup: bool = True,
        encoding: str = "utf-8",
    ) -> Path:
        import os as _os
        import tempfile

        tgt = self.safe_path(*parts)
        if create_dirs:
            try:
                tgt.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=".sdk_tmp_", dir=str(tgt.parent))
        try:
            with open(tmp_fd, "w", encoding=encoding) as f:
                f.write(text)
            if backup and tgt.exists():
                try:
                    bkp = tgt.with_suffix(tgt.suffix + ".bak")
                    try:
                        if bkp.exists():
                            bkp.unlink()
                    except Exception:
                        pass
                    tgt.replace(bkp)
                except Exception:
                    pass
            _os.replace(tmp_path, str(tgt))
            return tgt
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def replace_in_file(
        self,
        *parts: Pathish,
        pattern: str,
        repl: str,
        regex: bool = False,
        flags: int = 0,
        count: int = 0,
        encoding: str = "utf-8",
    ) -> int:
        p = self.safe_path(*parts)
        try:
            data = p.read_text(encoding=encoding)
        except Exception:
            return 0
        new = data
        n = 0
        if regex:
            import re as _re

            new, n = _re.subn(
                pattern,
                repl,
                data,
                count=0 if count is None or count <= 0 else count,
                flags=flags,
            )
        else:
            if pattern in data:
                n = (
                    data.count(pattern)
                    if (count is None or count <= 0)
                    else min(count, data.count(pattern))
                )
                if n > 0:
                    new = data.replace(pattern, repl, n)
        if n > 0 and new != data:
            self.write_text_atomic(
                p, text=new, create_dirs=False, backup=True, encoding=encoding
            )
        return n

    def batch_replace(
        self,
        replacements: list[tuple[str, str]],
        patterns: Optional[Sequence[str]] = None,
        exclude: Optional[Sequence[str]] = None,
        *,
        regex: bool = False,
        flags: int = 0,
        max_files: Optional[int] = None,
    ) -> dict[str, int]:
        stats: dict[str, int] = {}
        for fp in self.iter_project_files(
            patterns=patterns, exclude=exclude, use_cache=True, max_files=max_files
        ):
            total = 0
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            new = content
            if regex:
                import re as _re

                for pat, rep in replacements:
                    new, n = _re.subn(pat, rep, new, flags=flags)
                    total += n
            else:
                for pat, rep in replacements:
                    if pat in new:
                        c = new.count(pat)
                        new = new.replace(pat, rep)
                        total += c
            if total > 0 and new != content:
                try:
                    self.write_text_atomic(
                        fp, text=new, create_dirs=False, backup=True, encoding="utf-8"
                    )
                    stats[str(fp)] = total
                except Exception:
                    pass
        return stats
    # ---------- Timing ----------
    def time_step(self, label: str):
        import contextlib
        import time as _t

        @contextlib.contextmanager
        def _ctx():
            t0 = _t.perf_counter()
            self.debug(f"Start: {label}")
            try:
                yield
            finally:
                dt = (_t.perf_counter() - t0) * 1000.0
                self.log_info(f"{label} done in {dt:.1f} ms")
        return _ctx()
    # ---------- Parallel map ----------
    def parallel_map(
        self,
        func: Callable[[Any], Any],
        items: Sequence[Any],
        max_workers: Optional[int] = None,
    ) -> list[Any]:
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
        except Exception:
            out: list[Any] = []
            for it in items:
                try:
                    out.append(func(it))
                except Exception as e:
                    self.log_error(f"parallel_map error: {e}")
            return out
        maxw = max_workers or min(32, max(1, (len(items) or 1)))
        results: list[Any] = [None] * len(items)  # type: ignore
        with ThreadPoolExecutor(max_workers=maxw) as ex:
            futures = {ex.submit(func, items[i]): i for i in range(len(items))}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    self.log_error(f"parallel_map item {idx} failed: {e}")
        return results

__all__ = [
    "SDKContext",
]
