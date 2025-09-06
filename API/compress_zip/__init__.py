# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
ACASL plugin: compress_zip — Create a ZIP bundle from the built executable or its app folder.

Heuristics (cross-platform, plug-and-play):
- Windows: prefer .exe artifacts
- macOS: prefer .app bundles (zip the bundle directory)
- Linux/other: prefer executable files (mode & 0o111)
- Fallback: most recent non-empty artifact file

ZIP naming:
- <target_basename>.zip in the parent directory of the target (dist/ or similar)
- If already exists, append _1, _2, ...

Notes:
- No UI popups except informational logs; respects ACASL-only policy (no folder opening).
- Idempotent: does not overwrite unless explicitly allowed (we don't overwrite by default).
"""

import stat
import sys
import zipfile
from pathlib import Path
from typing import Optional

from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "compress_zip"
ACASL_NAME = "ACASL: ZIP Bundle"
ACASL_VERSION = "1.0.1"
ACASL_DESCRIPTION = "Create a ZIP archive of the generated executable (or app folder)."
ACASL_AUTHOR = "Samuel Amen Ague"
ACASL_CREATED = "2025-09-06"
ACASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
ACASL_LICENSE = "GPL-3.0-only"
ACASL_TAGS = ["post-compilation", "archivage", "zip", "automatisation"]


def _is_executable_file(p: Path) -> bool:
    try:
        if not p.is_file():
            return False
        mode = p.stat().st_mode
        return bool(mode & stat.S_IXUSR or mode & stat.S_IXGRP or mode & stat.S_IXOTH)
    except Exception:
        return False


def _pick_target(artifacts: list[Path]) -> Optional[Path]:
    """Pick the most plausible main target among artifacts.

    Priority:
    - macOS: .app directories (newest)
    - Windows: .exe files (newest)
    - Executable files (mode executable) (newest)
    - Fallback: newest non-empty file
    """
    try:
        arts = [p for p in artifacts if p.exists()]
        if not arts:
            return None
        # macOS bundles first
        if sys.platform == "darwin":
            apps = [p for p in arts if p.is_dir() and p.suffix.lower() == ".app"]
            if apps:
                return max(apps, key=lambda p: p.stat().st_mtime)
        # Windows .exe
        exes = [p for p in arts if p.is_file() and p.suffix.lower() == ".exe"]
        if exes:
            return max(exes, key=lambda p: p.stat().st_mtime)
        # Generic executable files
        execs = [p for p in arts if _is_executable_file(p)]
        if execs:
            return max(execs, key=lambda p: p.stat().st_mtime)
        # Fallback: newest non-empty file
        files = [p for p in arts if p.is_file() and p.stat().st_size > 0]
        if files:
            return max(files, key=lambda p: p.stat().st_mtime)
        # Fallback: newest directory (rare)
        dirs = [p for p in arts if p.is_dir()]
        if dirs:
            return max(dirs, key=lambda p: p.stat().st_mtime)
        return None
    except Exception:
        return None


def _next_available(path: Path) -> Path:
    """Return a non-existing path by appending _1, _2, ... if needed."""
    if not path.exists():
        return path
    stem, suf = path.stem, path.suffix
    i = 1
    while True:
        candidate = path.with_name(f"{stem}_{i}{suf}")
        if not candidate.exists():
            return candidate
        i += 1


def _zip_dir(zip_path: Path, root_dir: Path) -> bool:
    try:
        with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in root_dir.rglob("*"):
                if p.is_file():
                    try:
                        arcname = p.relative_to(root_dir)
                        zf.write(str(p), arcname=str(arcname))
                    except Exception:
                        continue
        return True
    except Exception:
        return False


def _zip_file(zip_path: Path, file_path: Path) -> bool:
    try:
        with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(str(file_path), arcname=file_path.name)
        return True
    except Exception:
        return False


def acasl_run(ctx) -> None:
    sctx = wrap_post_context(ctx)
    arts = [Path(a) for a in getattr(sctx, "artifacts", []) or []]
    if not arts:
        sctx.log_warn("[zip] no artifacts; skipping")
        return

    target = _pick_target(arts)
    if not target:
        sctx.log_warn("[zip] could not determine a target to zip")
        return

    # Decide whether to zip a directory or a single file
    to_zip: tuple[str, str]  # (kind, path)
    kind = "dir" if target.is_dir() else "file"

    # For PyInstaller-like one-folder layouts: if the target is an executable file and its parent
    # looks like an app directory (many files), zip the entire folder instead for better UX.
    if kind == "file":
        try:
            parent = target.parent
            entries = list(parent.iterdir())
            many_support_files = len(entries) >= 5
            if many_support_files:
                # Also ensure we are not at workspace root
                ws = Path(getattr(sctx, "workspace_root", "."))
                if parent != ws:
                    kind = "dir"
                    target = parent
        except Exception:
            pass

    out_dir = target.parent
    base_name = target.stem if target.is_file() else target.name.rstrip("/")
    zip_name = f"{base_name}.zip"
    zip_path = _next_available(out_dir / zip_name)

    sctx.log_info(f"[zip] target: {target} ({kind}); output: {zip_path.name}")

    ok = _zip_dir(zip_path, target) if kind == "dir" else _zip_file(zip_path, target)
    if ok:
        sctx.log_info(f"[zip] written: {zip_path}")
    else:
        sctx.log_error(f"[zip] failed creating: {zip_path}")
