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
    tags=["clean"]
)

# Default English translations (fallback)
DEFAULT_TRANSLATIONS = {
    "cleaner_title": "Cleaner",
    "cleaner_question": "Do you want to clean the workspace (.pyc and __pycache__)?",
    "cleaner_cancelled": "Cleaner cancelled by user",
    "cleaner_completed": "Cleaner completed: {files} .pyc files and {dirs} __pycache__ directories removed",
    "cleaner_error_file": "Failed to remove {path}: {error}",
    "cleaner_error_dir": "Failed to remove {path}: {error}",
}


class Cleaner(BcPluginBase):
    """Plugin de nettoyage du workspace avant compilation.
    
    Supprime les fichiers .pyc et les dossiers __pycache__ pour réduire la taille
    et éviter les problèmes de cache lors de la compilation.
    """
    
    def __init__(self):
        super().__init__(META)
        self.cleaned_files = 0
        self.cleaned_dirs = 0
        self._lang_data = {}  # Translation dictionary
        self._gui = None  # GUI reference

    def _get_translation(self, key: str, default: Optional[str] = None) -> str:
        """Get translated string for the given key with fallback.
        
        Args:
            key: Translation key
            default: Default value if key not found
            
        Returns:
            Translated string or default value
        """
        try:
            # Try to get from loaded translations
            if isinstance(self._lang_data, dict):
                v = self._lang_data.get(key)
                if isinstance(v, str) and v.strip():
                    return v
            
            # Fallback to default translations
            v = DEFAULT_TRANSLATIONS.get(key)
            if isinstance(v, str) and v.strip():
                return v
            
            # Last resort: use provided default
            return default or key
        except Exception:
            return default or key

    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        """Nettoie le workspace avant la compilation.
        
        Args:
            ctx: PreCompileContext avec les informations du workspace
        """
        try:
            # Demander confirmation à l'utilisateur
            title = self._get_translation("cleaner_title")
            question = self._get_translation("cleaner_question")
            
            response = dialog.msg_question(
                title=title,
                text=question,
                default_yes=True,
            )
            
            if not response:
                cancelled_msg = self._get_translation("cleaner_cancelled")
                log.log_info(cancelled_msg)
                return
            
            # Réinitialiser les compteurs
            self.cleaned_files = 0
            self.cleaned_dirs = 0
            
            # Déterminer le chemin du workspace
            try:
                workspace_path = Path(ctx.workspace) if hasattr(ctx, 'workspace') else Path.cwd()
            except Exception:
                workspace_path = Path.cwd()
            
            # Parcourir et supprimer les fichiers .pyc
            try:
                for file_path in ctx.iter_files(["**/*.pyc"], []):
                    try:
                        Path(file_path).unlink()
                        self.cleaned_files += 1
                    except Exception as e:
                        error_msg = self._get_translation(
                            "cleaner_error_file",
                            "Failed to remove {path}: {error}"
                        ).format(path=file_path, error=e)
                        log.log_warn(error_msg)
            except Exception as e:
                log.log_warn(f"Error iterating .pyc files: {e}")
            
            # Parcourir et supprimer les dossiers __pycache__
            try:
                for pycache_dir in workspace_path.rglob("__pycache__"):
                    try:
                        shutil.rmtree(pycache_dir)
                        self.cleaned_dirs += 1
                    except Exception as e:
                        error_msg = self._get_translation(
                            "cleaner_error_dir",
                            "Failed to remove {path}: {error}"
                        ).format(path=pycache_dir, error=e)
                        log.log_warn(error_msg)
            except Exception as e:
                log.log_warn(f"Error iterating __pycache__ directories: {e}")
            
            # Afficher le résumé
            completed_msg = self._get_translation(
                "cleaner_completed",
                "Cleaner completed: {files} .pyc files and {dirs} __pycache__ directories removed"
            ).format(files=self.cleaned_files, dirs=self.cleaned_dirs)
            log.log_info(completed_msg)
            
        except Exception as e:
            log.log_warn(f"Error during cleaning: {e}")

    def apply_i18n(self, gui, tr: dict) -> None:
        """Apply i18n translations from the application.
        
        Supports both namespaced and flat translation structures:
        - Namespaced: tr["plugins"]["cleaner"] = {...}
        - Flat: tr["cleaner_*"] = {...}
        
        Falls back to plugin-local languages/*.json if not provided by app.
        
        Args:
            gui: GUI reference for error logging
            tr: Translation dictionary from the application
        """
        try:
            self._gui = gui
            
            # 1) Try to extract plugin translations from app's dict (preferred)
            plugin_tr: dict = {}
            try:
                if isinstance(tr, dict):
                    # Try namespaced structure: tr["plugins"]["cleaner"]
                    plugs = tr.get("plugins", {})
                    if isinstance(plugs, dict):
                        maybe = plugs.get("cleaner", {})
                        if isinstance(maybe, dict) and maybe:
                            plugin_tr = maybe
                    
                    # Try flat structure: collect keys starting with "cleaner_"
                    if not plugin_tr:
                        collected = {
                            k: v for k, v in tr.items()
                            if isinstance(k, str) and k.startswith("cleaner_") and isinstance(v, str)
                        }
                        if collected:
                            plugin_tr = collected
            except Exception:
                plugin_tr = {}
            
            # If app provided translations, use them directly
            if isinstance(plugin_tr, dict) and plugin_tr:
                self._lang_data = plugin_tr
                return
            
            # 2) Fallback: load plugin-local JSON based on language code
            try:
                # Extract language code from translation metadata
                code = None
                try:
                    if isinstance(tr, dict):
                        meta = tr.get("_meta", {})
                        if isinstance(meta, dict):
                            code = meta.get("code")
                except Exception:
                    pass
                
                # Fallback to GUI language preference
                if not code:
                    try:
                        code = getattr(gui, "current_language", None)
                        if not code:
                            code = getattr(gui, "language_pref", None)
                        if not code:
                            code = getattr(gui, "language", None)
                    except Exception:
                        pass
                
                # Default to English
                if not code or code == "System":
                    code = "en"
                
                # Load language file
                lang_data = self._load_language_file(str(code))
                if lang_data:
                    self._lang_data = lang_data
                else:
                    # Fallback to default translations
                    self._lang_data = DEFAULT_TRANSLATIONS.copy()
                    
            except Exception:
                self._lang_data = DEFAULT_TRANSLATIONS.copy()
                
        except Exception as e:
            # Ensure we always have fallback translations
            self._lang_data = DEFAULT_TRANSLATIONS.copy()
            try:
                if hasattr(gui, "log") and gui.log:
                    gui.log.append(f"⚠️ Error applying i18n to Cleaner plugin: {e}\n")
            except Exception:
                pass

    def _load_language_file(self, code: str) -> Optional[dict]:
        """Load language file for the given language code.
        
        Tries multiple candidates with fallbacks:
        - Exact match (e.g., "fr-FR")
        - Base language (e.g., "fr")
        - English as last resort
        
        Args:
            code: Language code (e.g., "en", "fr", "fr-FR")
            
        Returns:
            Language dictionary or None if not found
        """
        try:
            import json
            import importlib.resources as ilr
            
            # Normalize code
            raw = str(code).strip()
            low = raw.lower().replace("_", "-")
            
            # Language aliases for normalization
            aliases = {
                "en-us": "en",
                "en-gb": "en",
                "en-uk": "en",
                "fr-fr": "fr",
                "fr-ca": "fr",
                "pt-br": "pt-BR",
                "zh-cn": "zh-CN",
                "zh-tw": "zh-CN",
            }
            mapped = aliases.get(low, raw)
            
            # Build candidates list
            candidates = []
            if mapped not in candidates:
                candidates.append(mapped)
            
            # Add base language (e.g., "fr" from "fr-FR")
            base = None
            try:
                if "-" in mapped:
                    base = mapped.split("-", 1)[0]
                elif "_" in mapped:
                    base = mapped.split("_", 1)[0]
            except Exception:
                pass
            if base and base not in candidates:
                candidates.append(base)
            
            # Add normalized variants
            if low not in candidates:
                candidates.append(low)
            if raw not in candidates:
                candidates.append(raw)
            
            # Always try English as fallback
            if "en" not in candidates:
                candidates.append("en")
            
            # Try to load each candidate
            pkg = __package__
            for cand in candidates:
                try:
                    with ilr.as_file(
                        ilr.files(pkg).joinpath("languages", f"{cand}.json")
                    ) as p:
                        if os.path.isfile(str(p)):
                            with open(str(p), encoding="utf-8") as f:
                                data = json.load(f)
                                if isinstance(data, dict):
                                    return data
                except Exception:
                    continue
            
            return None
            
        except Exception:
            return None


# Auto-register plugin in BCASL
PLUGIN = Cleaner()


def bcasl_register(manager):
    """Register the Cleaner plugin with the BCASL manager.
    
    Args:
        manager: BCASL manager instance
    """
    manager.add_plugin(PLUGIN)

