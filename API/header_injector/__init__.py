# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague
# Author: Samuel Amen Ague
from __future__ import annotations

from API_SDK import PluginBase, PluginMeta, PreCompileContext, plugin, wrap_context

# BCASL package signature (required)
BCASL_PLUGIN = True
BCASL_ID = "license_injector"
BCASL_DESCRIPTION = "Injecte une ligne de licence (SPDX) en tête des fichiers ciblés"
BCASL_NAME = "License Injector"
BCASL_VERSION = "1.1.0"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
BCASL_LICENSE = "GPL-3.0-only"
BCASL_TAGS = ["pre-compilation", "license", "SPDX"]

import re
from pathlib import Path
from typing import Optional

import API_SDK

# Détection et normalisation de la licence du workspace
try:
    import tomllib as _tomllib  # Python 3.11+
except Exception:
    try:
        import tomli as _tomllib  # backport
    except Exception:
        _tomllib = None


def _normalize_spdx(lic: str) -> tuple[str, str]:
    s = (lic or "").strip()
    if not s:
        return "", ""
    s_up = s.upper()
    # Normalisations directes
    mapping = {
        "MIT": "MIT",
        "APACHE-2.0": "Apache-2.0",
        "APACHE LICENSE 2.0": "Apache-2.0",
        "GPL-3.0": "GPL-3.0-only",
        "GPL-3.0-ONLY": "GPL-3.0-only",
        "GPL-3.0-OR-LATER": "GPL-3.0-or-later",
        "LGPL-3.0": "LGPL-3.0-only",
        "LGPL-3.0-ONLY": "LGPL-3.0-only",
        "LGPL-3.0-OR-LATER": "LGPL-3.0-or-later",
        "AGPL-3.0": "AGPL-3.0-only",
        "AGPL-3.0-ONLY": "AGPL-3.0-only",
        "AGPL-3.0-OR-LATER": "AGPL-3.0-or-later",
        "BSD-3-CLAUSE": "BSD-3-Clause",
        "BSD-2-CLAUSE": "BSD-2-Clause",
        "MPL-2.0": "MPL-2.0",
        "MOZILLA PUBLIC LICENSE 2.0": "MPL-2.0",
        "THE UNLICENSE": "Unlicense",
        "UNLICENSE": "Unlicense",
    }
    for k, v in mapping.items():
        if k in s_up:
            return v, v
    # Heuristiques
    if "GNU GENERAL PUBLIC LICENSE" in s_up:
        if "AFFERO" in s_up:
            return "AGPL-3.0-only", "AGPL-3.0-only"
        if "LESSER" in s_up:
            return "LGPL-3.0-only", "LGPL-3.0-only"
        return "GPL-3.0-only", "GPL-3.0-only"
    if "APACHE LICENSE" in s_up:
        return "Apache-2.0", "Apache-2.0"
    if "MIT LICENSE" in s_up:
        return "MIT", "MIT"
    if "MOZILLA PUBLIC LICENSE" in s_up:
        return "MPL-2.0", "MPL-2.0"
    if "BSD" in s_up:
        return "BSD-3-Clause", "BSD-3-Clause"
    return s, s


def _detect_license_from_pyproject(root: Path) -> Optional[str]:
    try:
        if _tomllib is None:
            return None
        pp = root / "pyproject.toml"
        if not pp.is_file():
            return None
        with open(pp, "rb") as f:
            data = _tomllib.load(f)
        # PEP 621
        proj = data.get("project") or {}
        lic = proj.get("license")
        if isinstance(lic, str):
            return lic
        if isinstance(lic, dict):
            if isinstance(lic.get("text"), str):
                return lic.get("text")
            if isinstance(lic.get("file"), str):
                try:
                    return (root / lic["file"]).read_text(encoding="utf-8", errors="ignore")[:4096]
                except Exception:
                    pass
        # Poetry
        tool = data.get("tool") or {}
        poetry = tool.get("poetry") or {}
        lic2 = poetry.get("license")
        if isinstance(lic2, str):
            return lic2
    except Exception:
        return None
    return None


def _detect_license_from_files(root: Path) -> Optional[str]:
    try:
        candidates = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
            "LICENCE",
            "LICENCE.txt",
            "COPYING",
            "COPYING.txt",
        ]
        for name in candidates:
            p = root / name
            if p.is_file():
                try:
                    return p.read_text(encoding="utf-8", errors="ignore")[:8192]
                except Exception:
                    continue
    except Exception:
        return None
    return None


def _detect_workspace_license(root: Path) -> tuple[str, str]:
    lic = _detect_license_from_pyproject(root) or _detect_license_from_files(root)
    if not lic:
        return "", ""
    spdx, name = _normalize_spdx(lic)
    return spdx, name


# Détection SPDX déjà présente


def _has_spdx(text: str) -> bool:
    return "SPDX-License-Identifier:" in text


# Injection d'une ligne SPDX minimale selon le type de fichier


def _inject_license_for_file(path: Path, text: str, spdx_id: str) -> str:
    """Injecte une ligne SPDX minimale selon le type de fichier, sans en-tête additionnel.
    - .py: insère '# SPDX-License-Identifier: <ID>' après shebang/encodage
    - .md/.markdown: insère 'SPDX-License-Identifier: <ID>' en première ligne
    - .html/.htm: insère '<!-- SPDX-License-Identifier: <ID> -->' en tête (après DOCTYPE)
    - autres: insère 'SPDX-License-Identifier: <ID>' en première ligne
    """
    try:
        if not spdx_id:
            return text
        if _has_spdx(text):
            return text
        suffix = path.suffix.lower()
        if suffix == ".py":
            lines = text.splitlines(keepends=True)
            idx = 0
            if idx < len(lines) and lines[idx].startswith("#!"):
                idx += 1
            coding_re = re.compile(r"^#.*coding[:=]\\s*([-\\w.]+)")
            if idx < len(lines) and coding_re.match(lines[idx]):
                idx += 1
            lic_line = f"# SPDX-License-Identifier: {spdx_id}\n"
            return "".join(lines[:idx]) + lic_line + "".join(lines[idx:])
        elif suffix in (".md", ".markdown"):
            return f"SPDX-License-Identifier: {spdx_id}\n\n{text}"
        elif suffix in (".html", ".htm"):
            lines = text.splitlines(keepends=True)
            if lines and lines[0].lstrip().upper().startswith("<!DOCTYPE"):
                return lines[0] + f"<!-- SPDX-License-Identifier: {spdx_id} -->\n" + "".join(lines[1:])
            return f"<!-- SPDX-License-Identifier: {spdx_id} -->\n{text}"
        else:
            return f"SPDX-License-Identifier: {spdx_id}\n{text}"
    except Exception:
        return text


@plugin(
    id="license_injector",
    version="1.1.0",
    description="Injecte une ligne de licence (SPDX) en tête des fichiers ciblés",
)
class LicenseInjector(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][license_injector] {exc}")
            return

        cfg = sctx.config_view
        subcfg = cfg.for_plugin(getattr(self, "id", "license_injector"))

        # Déterminer la licence du workspace
        spdx_id, lic_name = _detect_workspace_license(sctx.workspace_root)
        if not spdx_id:
            sctx.log_info(
                "license_injector: aucune licence détectée dans le workspace (pyproject/LICEN[SC]E/COPYING). Aucune injection."
            )
            return

        # Cibles et exclusions
        patterns: list[str] = subcfg.get("file_patterns", []) or cfg.file_patterns or ["**/*.py", "**/*.md"]
        exclude: list[str] = list(cfg.exclude_patterns) + list(subcfg.get("exclude_patterns", []))
        # Exclusions communes
        for pat in ("venv/**", ".git/**", "main.build/**"):
            if pat not in exclude:
                exclude.append(pat)

        # Demande confirmation
        if not sctx.msg_question(
            "License Injector",
            f"Injecter la licence (SPDX: {spdx_id}) dans les fichiers correspondant aux motifs: {patterns}?",
            default_yes=False,
        ):
            sctx.log_warn("license_injector: opération annulée par l'utilisateur")
            return

        # Phase 1: analyse des cibles
        ph = API_SDK.progress("Injection de licence", "Analyse des fichiers cibles...", maximum=0, cancelable=True)
        try:
            to_modify: list[Path] = []
            found = 0
            skipped_dup = 0
            for p in sctx.iter_files(patterns, exclude=exclude, enforce_workspace=True):
                if ph.canceled:
                    sctx.log_warn("license_injector: opération annulée par l'utilisateur")
                    return
                found += 1
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    sctx.log_warn(
                        f"Lecture échouée pour {p.relative_to(sctx.workspace_root) if p.exists() else p}: {e}"
                    )
                    continue
                if _has_spdx(text):
                    skipped_dup += 1
                else:
                    to_modify.append(p)
                if found <= 5 or (found % 50 == 0):
                    try:
                        rel = p.relative_to(sctx.workspace_root)
                        ph.update(text=f"Fichiers détectés: {found} (dernier: {rel})")
                    except Exception:
                        ph.update(text=f"Fichiers détectés: {found}")

            if not to_modify:
                if found == 0:
                    sctx.log_info("license_injector: aucun fichier cible")
                else:
                    sctx.log_info(
                        f"license_injector: aucun fichier à modifier (déj�� avec SPDX={skipped_dup}, total scannés={found})"
                    )
                return

            # Phase 2: injection
            ph.set_maximum(len(to_modify))
            changed = 0
            for i, p in enumerate(to_modify, start=1):
                if ph.canceled:
                    sctx.log_warn("license_injector: opération annulée par l'utilisateur")
                    return
                rel = p.relative_to(sctx.workspace_root)
                ph.update(i, f"{i}/{len(to_modify)}: {rel}")
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    sctx.log_warn(f"Lecture échouée pour {rel}: {e}")
                    continue

                new_text = _inject_license_for_file(p, text, spdx_id)
                try:
                    p.write_text(new_text, encoding="utf-8")
                    changed += 1
                except Exception as e:
                    sctx.log_warn(f"Écriture échouée pour {rel}: {e}")

            sctx.log_info(
                f"license_injector: terminé. Modifiés={changed}, déjà avec SPDX={skipped_dup}, total scannés={found}"
            )
        finally:
            ph.close()


# Métadonnées et instance du plugin pour BCASL
META = PluginMeta(
    id=BCASL_ID,
    name="LicenseInjector",
    version="1.1.0",
    description="Injecte une ligne de licence (SPDX) en tête des fichiers ciblés",
)
PLUGIN = LicenseInjector(META)


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
