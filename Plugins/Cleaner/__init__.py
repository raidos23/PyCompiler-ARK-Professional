# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

# Plugin de nettoyage du workspace (suppression des fichiers .pyc et dossiers __pycache__)

from pathlib import Path
import shutil
from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta, PreCompileContext
from Plugins_SDK.GeneralContext import Dialog


log = Dialog
dialog = Dialog

META = PluginMeta(
    id="cleaner",
    name="Cleaner",
    version="1.0.0",
    description="Clean the workspace (.pyc and __pycache__)",
    author="Samuel Amen Ague",
    tags=["clean"]
)


# classe principale du plugin
class Cleaner(BcPluginBase):
    def __init__(self):
        super().__init__(META)
        self.cleaned_files = 0
        self.cleaned_dirs = 0

    def install_deps(self, deps):
        return super().install_deps(deps)

    def on_pre_compile(self, ctx: PreCompileContext):
        """Nettoie le workspace avant la compilation"""
        # Demander confirmation à l'utilisateur
        response = dialog.msg_question(
            self=dialog,
            title="Cleaner",
            text="Do you want to clean the workspace (.pyc and __pycache__)?",
            default_yes=True,
        )
        
        if response:
            self.cleaned_files = 0
            self.cleaned_dirs = 0
            
            # Parcourir tous les fichiers du workspace
            for file_path in ctx.iter_files(["**/*.pyc"], []):
                try:
                    Path(file_path).unlink()
                    self.cleaned_files += 1
                except Exception as e:
                    log.log_warning(message=f"Failed to remove {file_path}: {e}")
            
            # Parcourir et supprimer les dossiers __pycache__
            workspace_path = Path(ctx.workspace) if hasattr(ctx, 'workspace') else Path.cwd()
            for pycache_dir in workspace_path.rglob("__pycache__"):
                try:
                    shutil.rmtree(pycache_dir)
                    self.cleaned_dirs += 1
                except Exception as e:
                    log.log_warning(message=f"Failed to remove {pycache_dir}: {e}")
            
            log.log_info(
                message=f"Cleaner completed: {self.cleaned_files} .pyc files and {self.cleaned_dirs} __pycache__ directories removed"
            )
        else:
            log.log_info(message="Cleaner cancelled by user")

    def apply_i18n(self, gui, tr):
        return super().apply_i18n(gui, tr)


# enregistrement automatique du plugin dans le registre de bcasl
PLUGIN = Cleaner()


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
