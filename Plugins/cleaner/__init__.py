# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague
# Author: Samuel Amen Ague
import fnmatch
import os
import shutil

import Plugins_SDK
from Plugins_SDK import Bc_PluginBase, PluginMeta, PreCompileContext, wrap_context
from Plugins_SDK.BCASL_SDK import apply_plugin_i18n

# Métadonnées et instance du plugin pour BCASL
META = PluginMeta(
    id="cleaner",
    name="Nettoyeur",
    version="1.0.0",
    description="clean the workspace (.pyc and __pycache__)",
)

class Cleaner(Bc_PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][cleaner] {exc}")
            return
        root = sctx.workspace_root

        # Charger les traductions locales du plugin
        tr = apply_plugin_i18n(self, __file__, getattr(sctx, '_tr', {}))

        # Préparer exclusions (globales + spécifiques au plugin)
        cfg = sctx.config_view
        subcfg = cfg.for_plugin(getattr(self, "id", "cleaner"))
        exclude = list(cfg.exclude_patterns) + list(subcfg.get("exclude_patterns", []))
        include_venv = bool(subcfg.get("include_venv", False))
        if not include_venv:
            # Exclure venv/** par défaut
            if "venv/**" not in exclude:
                exclude.append("venv/**")

        def _is_excluded(path_str: str) -> bool:
            try:
                rel = os.path.relpath(path_str, str(root))
            except Exception:
                rel = path_str
            rel_posix = rel.replace(os.sep, "/")
            for pat in exclude:
                try:
                    if fnmatch.fnmatch(rel_posix, pat):
                        return True
                except Exception:
                    continue
            return False

        # Demande de confirmation avant une opération potentiellement destructive
        if not sctx.msg_question(
            tr.get("title", "Nettoyeur"),
            tr.get("confirm_delete", "Supprimer tous les fichiers .pyc et les dossiers __pycache__ du workspace ?"),
            default_yes=False,
        ):
            sctx.log_warn("Nettoyage annulé par l'utilisateur")
            return

        # 1) Analyse (comptage des éléments à supprimer) avec progression indéterminée
        ph = Plugins_SDK.progress(
            tr.get("progress_title", "Nettoyage du workspace"),
            tr.get("analysis_text", "Analyse des éléments à supprimer..."),
            maximum=0,
            cancelable=True,
        )
        try:
            total = 0
            for r, dirs, files in os.walk(root, topdown=False):
                for file in files:
                    if file.endswith(".pyc"):
                        fpath = os.path.join(r, file)
                        if not _is_excluded(fpath):
                            total += 1
                for d in dirs:
                    if d == "__pycache__":
                        dpath = os.path.join(r, d)
                        if not _is_excluded(dpath):
                            total += 1

            if total == 0:
                ph.update(text="Rien à supprimer")
                sctx.log_info("Aucun fichier .pyc ou dossier __pycache__ à supprimer.")
                return

            # 2) Suppression avec progression déterminée
            pyc_count = 0
            pycache_count = 0
            current = 0
            ph.set_maximum(total if total > 0 else 1)

            for r, dirs, files in os.walk(root, topdown=False):
                # Supprimer les fichiers .pyc
                for file in files:
                    if file.endswith(".pyc"):
                        path = os.path.join(r, file)
                        if _is_excluded(path):
                            continue
                        if ph.canceled:
                            sctx.log_warn("Nettoyage annulé par l'utilisateur")
                            return
                        try:
                            os.remove(path)
                            pyc_count += 1
                        except Exception as e:
                            sctx.log_warn(f"Erreur suppression {file}: {e}")
                        finally:
                            current += 1
                            ph.update(current, f"Suppression .pyc ({current}/{total})")

                # Supprimer les dossiers __pycache__
                for d in dirs:
                    if d == "__pycache__":
                        path = os.path.join(r, d)
                        if _is_excluded(path):
                            continue
                        if ph.canceled:
                            sctx.log_warn("Nettoyage annulé par l'utilisateur")
                            return
                        try:
                            shutil.rmtree(path)
                            pycache_count += 1
                        except Exception as e:
                            sctx.log_warn(f"Erreur suppression {d}: {e}")
                        finally:
                            current += 1
                            ph.update(current, f"Suppression __pycache__ ({current}/{total})")

            # 3) Logs UI
            sctx.log_info(
                f"🗑️ Nettoyage terminé : {pyc_count} fichier(s) .pyc et {pycache_count} dossier(s) __pycache__ supprimés."
            )
        finally:
            ph.close()



PLUGIN = Cleaner(META)

# Fonction requise par le chargeur BCASL


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
