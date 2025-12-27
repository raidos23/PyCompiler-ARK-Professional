# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from pathlib import Path
import shutil
from typing import Optional
from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta, PreCompileContext
from Plugins_SDK.GeneralContext import Dialog


# Create instances of Dialog for logging and user interaction
# These now automatically execute in the main Qt thread, ensuring theme inheritance
# and proper UI integration with the main application
log = Dialog()
dialog = Dialog()

META = PluginMeta(
    id="cleaner",
    name="Cleaner",
    version="1.0.0",
    description="Clean the workspace (.pyc and __pycache__)",
    author="Samuel Amen Ague",
    tags=["clean"],
    required_bcasl_version="2.0.0",
    required_core_version="1.0.0",
    required_plugins_sdk_version="1.0.0",
    required_bc_plugin_context_version="1.0.0",
    required_general_context_version="1.0.0",
)

# Plugin no longer uses i18n; static messages are used directly.


class Cleaner(BcPluginBase):
    """Plugin de nettoyage du workspace avant compilation.
    
    Supprime les fichiers .pyc et les dossiers __pycache__ pour réduire la taille
    et éviter les problèmes de cache lors de la compilation.
    """
    
    def __init__(self):
        super().__init__(META)
        self.cleaned_files = 0
        self.cleaned_dirs = 0

    
    
    
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        """Nettoie le workspace avant la compilation.
        
        Args:
            ctx: PreCompileContext avec les informations du workspace
        """
        try:
            # Demander confirmation à l'utilisateur
            response = dialog.msg_question(
                title="Cleaner",
                text="Do you want to clean the workspace (.pyc and __pycache__)?",
                default_yes=True,
            )
            
            if not response:
                log.log_info("Cleaner cancelled by user")
                return
            
            # Réinitialiser les compteurs
            self.cleaned_files = 0
            self.cleaned_dirs = 0
            
            # Déterminer le chemin du workspace
            try:
                workspace_path = Path(ctx.workspace) if hasattr(ctx, 'workspace') else Path.cwd()
            except Exception:
                workspace_path = Path.cwd()
            
            # Créer le dialog de progression
            progress = dialog.progress(title="Cleaning workspace...", cancelable=True)
            progress.show()
            
            try:
                # Étape 1: Parcourir et supprimer les fichiers .pyc
                progress.set_message("Scanning for .pyc files and __pycache__ directories...")
                
                pyc_files = []
                try:
                    for file_path in ctx.iter_files(["**/*.pyc"], []):
                        pyc_files.append(file_path)
                except Exception as e:
                    log.log_warn(f"Error iterating .pyc files: {e}")
                
                # Étape 2: Supprimer les fichiers .pyc
                progress.set_message("Removing .pyc files...")
                progress.set_progress(0, len(pyc_files))
                
                for idx, file_path in enumerate(pyc_files):
                    if progress.is_canceled():
                        break
                    try:
                        Path(file_path).unlink()
                        self.cleaned_files += 1
                    except Exception as e:
                        log.log_warn(f"Failed to remove {file_path}: {e}")
                    progress.set_progress(idx + 1, len(pyc_files))
                
                # Étape 3: Parcourir et supprimer les dossiers __pycache__
                progress.set_message("Removing __pycache__ directories...")
                
                pycache_dirs = []
                try:
                    for pycache_dir in workspace_path.rglob("__pycache__"):
                        pycache_dirs.append(pycache_dir)
                except Exception as e:
                    log.log_warn(f"Error iterating __pycache__ directories: {e}")
                
                progress.set_progress(0, len(pycache_dirs))
                
                for idx, pycache_dir in enumerate(pycache_dirs):
                    if progress.is_canceled():
                        break
                    try:
                        shutil.rmtree(pycache_dir)
                        self.cleaned_dirs += 1
                    except Exception as e:
                        log.log_warn(f"Failed to remove {pycache_dir}: {e}")
                    progress.set_progress(idx + 1, len(pycache_dirs))
                
            finally:
                progress.close()
            
            # Afficher le résumé
            log.log_info(
                f"Cleaner completed: {self.cleaned_files} .pyc files and {self.cleaned_dirs} __pycache__ directories removed"
            )
            
        except Exception as e:
            log.log_warn(f"Error during cleaning: {e}")

    

# Auto-register plugin in BCASL
PLUGIN = Cleaner()


def bcasl_register(manager):
    """Register the Cleaner plugin with the BCASL manager."""
    manager.add_plugin(PLUGIN)

