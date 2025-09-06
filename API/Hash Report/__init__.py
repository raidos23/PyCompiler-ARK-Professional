# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
acasl_example — Example ACASL plugin (package form)

Conforms to the ACASL loader contract:
- Package under API/acasl_example/ with __init__.py
- Declares ACASL_PLUGIN = True
- Exposes acasl_run(ctx)
- Uses API_SDK.ACASL_SDK facade and wrap_post_context
"""

from API_SDK.ACASL_SDK import wrap_post_context
from pathlib import Path
import hashlib
import json
from typing import List

ACASL_PLUGIN = True  # required explicit signature for ACASL packages
# Metadata (required id/description; optional name/version)
ACASL_ID = "Hash Report"
ACASL_NAME = "Hash Report"
ACASL_VERSION = "1.1.0"
ACASL_DESCRIPTION = "Compute SHA-256 for post-build artifacts and write a JSON report."
ACASL_AUTHOR = "Samuel Amen Ague"
ACASL_CREATED = "2025-09-06"
ACASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
ACASL_LICENSE = "GPL-3.0-only"
ACASL_TAGS = ["post-compilation", "hash", "report", "automatisation"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def acasl_run(ctx) -> None:
    """Compute SHA‑256 for produced artifacts and write a JSON report next to them."""
    sctx = wrap_post_context(ctx)
    arts: List[str] = list(getattr(sctx, 'artifacts', []) or [])
    if not arts:
        sctx.log_warn("ACASL/hash_report: no artifacts.")
        return
    rows = []
    for a in arts:
        p = Path(a)
        if not p.exists():
            sctx.log_warn(f"ACASL/hash_report: missing: {a}")
            continue
        if sctx.is_canceled():
            sctx.log_warn("ACASL/hash_report: canceled.")
            return
        try:
            digest = _sha256(p)
            rows.append({"path": str(p), "sha256": digest})
        except Exception as e:
            sctx.log_warn(f"ACASL/hash_report: error on {a}: {e}")
    # Write report next to the first artifact
    out = Path(arts[0]).parent / "acasl_hashes.json"
    try:
        out.write_text(json.dumps({"artifacts": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
        # Bilingual info
        sctx.msg_info(
            "ACASL — Hachage | Hash",
            (
                f"Rapport de hachage écrit: {out}\n\n"
                f"Hash report written: {out}"
            )
        )
        sctx.log_info(f"ACASL/hash_report: written {out}")
    except Exception as e:
        sctx.log_error(f"ACASL/hash_report: failed writing {out}: {e}")
