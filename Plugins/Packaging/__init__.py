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
from typing import Optional
from Plugins_SDK.AcPluginContext import AcPluginBase, PluginMeta, PostCompileContext
from Plugins_SDK.GeneralContext import Dialog

# Create instances of Dialog for logging and user interaction
log = Dialog()
dialog = Dialog()

META = PluginMeta(
    id="Packaging",
    name="Packaging",
    version="1.0.0",
    description="Package the compiled artifacts",
    author="Samuel Amen Ague",
    tags=["packaging"]
)


# classe principale du plugin
class Packaging(AcPluginBase):
    def __init__(self, meta):
        super().__init__(meta)
        self._lang_data = {}  # Translation dictionary
        self._gui = None  # GUI reference

    def install_deps(self, deps):
        return super().install_deps(deps)

    def _get_translation(self, key: str) -> Optional[str]:
        """Get translated string for the given key"""
        try:
            v = self._lang_data.get(key)
            return v if isinstance(v, str) and v.strip() else None
        except Exception:
            return None

    def on_Post_compile(
        self, ctx: PostCompileContext
    ):  # methode d'execution en post-compilation
        title = self._get_translation("packaging_title") or "Packaging"
        question = self._get_translation("packaging_question") or "Do you want to package your compiled artifacts?"
        
        response = dialog.msg_question(
            title=title,
            text=question,
            default_yes=True,
        )
        
        if response:
            try:
                # TODO: Implement actual packaging logic here
                # For now, just log success
                completed_msg = self._get_translation("packaging_completed") or "Packaging completed successfully"
                log.log_info(completed_msg)
            except Exception as e:
                error_msg = (
                    self._get_translation("packaging_error") or "Packaging failed: {error}"
                ).format(error=e)
                log.log_error(error_msg)
        else:
            cancelled_msg = self._get_translation("packaging_cancelled") or "Packaging cancelled by user"
            log.log_info(cancelled_msg)

    def apply_i18n(self, gui, tr: dict[str, str]) -> None:
        """Apply plugin-local i18n from Plugins/Packaging/languages/*.json independent of app languages."""
        try:
            self._gui = gui
            # Resolve language code preference
            code = None
            try:
                if isinstance(tr, dict):
                    meta = tr.get("_meta", {})
                    code = meta.get("code") if isinstance(meta, dict) else None
            except Exception:
                code = None
            if not code:
                try:
                    # Try GUI preferences
                    pref = getattr(gui, "language_pref", getattr(gui, "language", "System"))
                    if isinstance(pref, str) and pref != "System":
                        code = pref
                except Exception:
                    pass
            # Fallback
            if not code:
                code = "en"
            
            # Normalize codes and build robust fallback candidates
            raw = str(code)
            low = raw.lower().replace("_", "-")
            aliases = {
                "en-us": "en",
                "en_gb": "en",
                "en-uk": "en",
                "fr-fr": "fr",
                "fr_ca": "fr",
                "fr-ca": "fr",
                "pt-br": "pt-BR",
                "pt_br": "pt-BR",
                "zh": "zh-CN",
                "zh_cn": "zh-CN",
                "zh-cn": "zh-CN",
            }
            mapped = aliases.get(low, raw)
            
            # Candidate order: mapped -> base (before '-') -> exact lower -> exact raw -> 'en'
            candidates = []
            if mapped not in candidates:
                candidates.append(mapped)
            base = None
            try:
                if "-" in mapped:
                    base = mapped.split("-", 1)[0]
                elif "_" in mapped:
                    base = mapped.split("_", 1)[0]
            except Exception:
                base = None
            if base and base not in candidates:
                candidates.append(base)
            if low not in candidates:
                candidates.append(low)
            if raw not in candidates:
                candidates.append(raw)
            if "en" not in candidates:
                candidates.append("en")
            
            # Load plugin-local JSON using the first existing candidate
            import importlib.resources as ilr
            import json as _json
            
            pkg = __package__
            lang_data = {}
            
            def _load_lang(c: str) -> bool:
                nonlocal lang_data
                try:
                    with ilr.as_file(
                        ilr.files(pkg).joinpath("languages", f"{c}.json")
                    ) as p:
                        if os.path.isfile(str(p)):
                            with open(str(p), encoding="utf-8") as f:
                                lang_data = _json.load(f) or {}
                            return True
                except Exception:
                    pass
                return False
            
            for cand in candidates:
                if _load_lang(cand):
                    break
            
            self._lang_data = lang_data
        except Exception:
            self._lang_data = {}


# enregistrement automatique du plugin dans le registre de Acasl
PLUGIN = Packaging(META)


def acasl_register(manager):
    manager.add_plugin(PLUGIN)
    # Register in INSTANCES for i18n support
    try:
        from Plugins_SDK.GeneralContext.i18n import INSTANCES
        INSTANCES[META.id] = PLUGIN
    except Exception:
        pass