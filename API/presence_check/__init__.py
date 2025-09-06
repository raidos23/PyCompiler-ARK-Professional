# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague
# Author: Samuel Amen Ague
from __future__ import annotations

from API_SDK import PluginBase, PreCompileContext, wrap_context, plugin, PluginMeta

# BCASL package signature (required)
BCASL_PLUGIN = True
BCASL_ID = "presence_check"
BCASL_DESCRIPTION = "Garde-fou: vérifie la présence et la conformité des éléments requis"
BCASL_NAME = "Presence Check"
BCASL_VERSION = "1.0.0"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_COMPATIBILITY = ['PyCompiler ARK++ v3.2+', 'Python 3.10+']
BCASL_LICENSE = "GPL-3.0-only"
BCASL_TAGS = ['pre-compilation', 'validation', 'requirements']

import API_SDK
import os
import re
from pathlib import Path
from typing import Iterable, List, Tuple


@plugin(id="presence_check", version="1.0.0", description="Garde-fou: vérifie la présence et la conformité des éléments requis")
class PresenceCheck(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][presence_check] {exc}")
            return

        cfg = sctx.config_view
        subcfg = cfg.for_plugin(getattr(self, 'id', 'presence_check'))

        # Exigences: motifs glob et/ou chemins explicites (relatifs au workspace)
        requires = subcfg.get("require", None)
        if not requires:
            requires = cfg.required_files or []
        if not isinstance(requires, (list, tuple)):
            requires = [str(requires)]
        requires = [str(x).strip() for x in requires if str(x).strip()]

        # Exclusions (glob) à respecter lors du développement des motifs
        exclude: List[str] = list(cfg.exclude_patterns) + list(subcfg.get("exclude_patterns", []))

        # Contraintes optionnelles
        must_be_file = bool(subcfg.get("must_be_file", True))
        must_be_readable = bool(subcfg.get("must_be_readable", True))
        must_be_non_empty = bool(subcfg.get("must_be_non_empty", False))
        require_at_least_one_match_for_glob = bool(subcfg.get("require_at_least_one_match_for_glob", True))

        if not requires:
            sctx.log_info("presence_check: aucune exigence fournie (require/required_files). Rien à valider.")
            return

        # Demande de confirmation avant vérification
        if not sctx.msg_question("Presence Check", f"Vérifier la présence et la conformité des éléments requis ({len(requires)} entrée(s)) ?", default_yes=False):
            sctx.log_warn("presence_check: opération annulée par l'utilisateur")
            return

        problems: List[str] = []

        def _wildcard(s: str) -> bool:
            return bool(re.search(r"[\*\?\[]", s))

        def _validate_path(p: Path, origin: str) -> None:
            try:
                # Enforce confinement to workspace
                if not sctx.is_within_workspace(p):
                    problems.append(f"{origin}: hors du workspace -> {p}")
                    return
            except Exception:
                problems.append(f"{origin}: chemin invalide -> {p}")
                return

            if must_be_file and not p.is_file():
                problems.append(f"{origin}: n'est pas un fichier -> {p.relative_to(sctx.workspace_root) if p.exists() else p}")
                return

            if must_be_readable:
                try:
                    if not os.access(p, os.R_OK):
                        problems.append(f"{origin}: non lisible -> {p.relative_to(sctx.workspace_root)}")
                        return
                except Exception:
                    problems.append(f"{origin}: non lisible (os.access échec) -> {p}")
                    return

            if must_be_non_empty:
                try:
                    if p.stat().st_size <= 0:
                        problems.append(f"{origin}: fichier vide -> {p.relative_to(sctx.workspace_root)}")
                        return
                except Exception:
                    problems.append(f"{origin}: impossible de déterminer la taille -> {p}")
                    return

        # Progression: phase 1 (analyse)
        ph = API_SDK.progress("Presence Check", "Analyse des éléments à vérifier...", maximum=0, cancelable=True)
        try:
            to_check: List[Tuple[Path, str]] = []
            total_checked = 0
            found = 0

            for req in requires:
                if ph.canceled:
                    sctx.log_warn("presence_check: opération annulée par l'utilisateur")
                    return
                req = req.replace("\\", "/")  # uniformiser
                if _wildcard(req):
                    matches = list(sctx.iter_files([req], exclude=exclude, enforce_workspace=True))
                    if not matches and require_at_least_one_match_for_glob:
                        problems.append(f"pattern '{req}': aucun fichier trouvé")
                        continue
                    for m in matches:
                        to_check.append((m, f"pattern '{req}'"))
                        found += 1
                        if found <= 5 or (found % 50 == 0):
                            try:
                                relm = m.relative_to(sctx.workspace_root)
                                ph.update(text=f"Collecte: {found} (dernier: {relm})")
                            except Exception:
                                ph.update(text=f"Collecte: {found}")
                else:
                    # Chemin explicite relatif au workspace
                    try:
                        p = sctx.safe_path(req)
                    except Exception:
                        problems.append(f"path '{req}': hors du workspace ou invalide")
                        continue
                    if not p.exists():
                        problems.append(f"path '{req}': introuvable -> {req}")
                        continue
                    to_check.append((p, f"path '{req}'"))
                    found += 1
                    if found <= 5 or (found % 50 == 0):
                        try:
                            relp = p.relative_to(sctx.workspace_root)
                            ph.update(text=f"Collecte: {found} (dernier: {relp})")
                        except Exception:
                            ph.update(text=f"Collecte: {found}")

            # Phase 2: validation déterminée
            n = len(to_check)
            if n == 0:
                if problems:
                    detail = "\n - " + "\n - ".join(problems)
                    sctx.log_error("presence_check: des exigences ne sont pas satisfaites:")
                    sctx.log_error(detail)
                    raise RuntimeError("presence_check: échec des validations. Voir détails dans les logs.")
                else:
                    sctx.log_info("presence_check: rien à vérifier.")
                    return

            ph.set_maximum(n)
            for i, (p, origin) in enumerate(to_check, start=1):
                if ph.canceled:
                    sctx.log_warn("presence_check: opération annulée par l'utilisateur")
                    return
                try:
                    rel = p.relative_to(sctx.workspace_root)
                    ph.update(i, f"Vérification {i}/{n}: {rel}")
                except Exception:
                    ph.update(i, f"Vérification {i}/{n}: {p}")
                _validate_path(p, origin)
                total_checked += 1

            if problems:
                # Échec: lister toutes les non-conformités
                detail = "\n - " + "\n - ".join(problems)
                sctx.log_error("presence_check: des exigences ne sont pas satisfaites:")
                sctx.log_error(detail)
                raise RuntimeError("presence_check: échec des validations. Voir détails dans les logs.")

            sctx.log_info(f"presence_check: OK ({total_checked} élément(s) vérifié(s)).")
        finally:
            ph.close()


# Métadonnées et instance du plugin pour BCASL
META = PluginMeta(
    id=BCASL_ID,
    name="PresenceCheck",
    version="1.0.0",
    description="Garde-fou: vérifie la présence et la conformité des éléments requis",
)
PLUGIN = PresenceCheck(META)


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
