# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague
# Author: Samuel Amen Ague
import asyncio
import fnmatch
import os
import shutil

import API_SDK
from API_SDK import PluginBase, PluginMeta, PreCompileContext, load_plugin_translations, plugin, wrap_context

# BCASL package signature (required)
BCASL_PLUGIN = True
BCASL_ID = "cleaner"
BCASL_DESCRIPTION = "Nettoie le workspace (.pyc et __pycache__)"
BCASL_NAME = "Cleaner"
BCASL_VERSION = "1.0.0"
BCASL_AUTHOR = "Samuel Amen Ague"
BCASL_CREATED = "2025-09-06"
BCASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
BCASL_LICENSE = "GPL-3.0-only"
BCASL_TAGS = ["pre-compilation", "clean", "cache", "pyc"]


@plugin(id="cleaner", version="1.0.0", description="Nettoie le workspace (.pyc et __pycache__)")
class Cleaner(PluginBase):
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        try:
            sctx = wrap_context(ctx)
        except RuntimeError as exc:
            print(f"[ERROR][cleaner] {exc}")
            return
        root = sctx.workspace_root

        # Préparer exclusions (globales + spécifiques au plugin)
        cfg = sctx.config_view
        subcfg = cfg.for_plugin(getattr(self, "id", "cleaner"))
        lang_code = subcfg.get("language", "System")
        tr = asyncio.run(load_plugin_translations(__file__, lang_code))
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
            tr.get("title", "Cleaner"),
            tr.get("confirm_delete", "Delete all .pyc files and __pycache__ folders from the workspace?"),
            default_yes=False,
        ):
            sctx.log_warn(tr.get("cleanup_cancelled", "Cleanup cancelled by user"))
            return

        # 1) Analyse (comptage des éléments à supprimer) avec progression indéterminée
        ph = API_SDK.progress(
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
                ph.update(text=tr.get("nothing_to_delete", "Nothing to delete"))
                sctx.log_info(tr.get("no_files_to_delete", "No .pyc files or __pycache__ folders to delete."))
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
                            sctx.log_warn(tr.get("cleanup_cancelled", "Cleanup cancelled by user"))
                            return
                        try:
                            os.remove(path)
                            pyc_count += 1
                        except Exception as e:
                            sctx.log_warn(
                                tr.get("delete_error", "Error deleting {file}: {error}").format(file=file, error=e)
                            )
                        finally:
                            current += 1
                            ph.update(
                                current,
                                tr.get("deleting_pyc", "Deleting .pyc ({current}/{total})").format(
                                    current=current, total=total
                                ),
                            )

                # Supprimer les dossiers __pycache__
                for d in dirs:
                    if d == "__pycache__":
                        path = os.path.join(r, d)
                        if _is_excluded(path):
                            continue
                        if ph.canceled:
                            sctx.log_warn(tr.get("cleanup_cancelled", "Cleanup cancelled by user"))
                            return
                        try:
                            shutil.rmtree(path)
                            pycache_count += 1
                        except Exception as e:
                            sctx.log_warn(
                                tr.get("delete_error", "Error deleting {file}: {error}").format(file=d, error=e)
                            )
                        finally:
                            current += 1
                            ph.update(
                                current,
                                tr.get("deleting_pycache", "Deleting __pycache__ ({current}/{total})").format(
                                    current=current, total=total
                                ),
                            )

            # 3) Logs UI
            sctx.log_info(
                tr.get(
                    "cleanup_completed",
                    "🗑️ Cleanup completed: {pyc_count} .pyc file(s) and {pycache_count} __pycache__ folder(s) deleted.",
                ).format(pyc_count=pyc_count, pycache_count=pycache_count)
            )
        finally:
            ph.close()


# Métadonnées et instance du plugin pour BCASL
META = PluginMeta(
    id=BCASL_ID,
    name="Nettoyeur",
    version="1.0.0",
    description="Nettoie le workspace (.pyc et __pycache__)",
)
PLUGIN = Cleaner(META)

# Fonction requise par le chargeur BCASL


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
