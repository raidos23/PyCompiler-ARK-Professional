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

from __future__ import annotations

from pathlib import Path
from typing import Any, Union


# -----------------------------
# Plugin base (ACASL) and decorator
# -----------------------------
# Reuse ACASL types to guarantee compatibility with the host
try:  # noqa: E402
    from acasl import (
        ACASL as ACASL,
        ExecutionReport as ExecutionReport,
        AcPluginBase as AcPluginBase,
        PluginMeta as PluginMeta,
        PostCompileContext as PostCompileContext,
    )

    try:
        from acasl import (
            ACASL_PLUGIN_REGISTER_FUNC as ACASL_PLUGIN_REGISTER_FUNC,
            register_acasl_plugin as register_plugin,
        )
    except Exception:  # pragma: no cover

        def register_plugin(cls: Any) -> Any:  # type: ignore
            setattr(cls, "__acasl_plugin__", True)
            return cls

        ACASL_PLUGIN_REGISTER_FUNC = "acasl_register"
except Exception:  # pragma: no cover — dev fallback when ACASL is not importable

    class AcPluginBase:  # type: ignore
        pass

    class PluginMeta:  # type: ignore
        pass

    class PostCompileContext:  # type: ignore
        pass

    def register_plugin(cls: Any) -> Any:  # type: ignore
        setattr(cls, "__acasl_plugin__", True)
        return cls

    ACASL_PLUGIN_REGISTER_FUNC = "acasl_register"


# -----------------------------
# Public bridge to set selected workspace from plugins
# -----------------------------

Pathish = Union[str, Path]


def set_selected_workspace(path: Pathish) -> bool:
    """Always accept workspace change requests (SDK-level contract).

    - Auto-creates the target directory if missing
    - Invokes the GUI-side bridge when available (non-blocking acceptance)
    - Returns True in all cases (including headless/no-GUI environments)
    """
    # Best-effort ensure the path exists
    try:
        p = Path(path)
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
    except Exception:
        pass
    # Try to inform the GUI when running with UI; ignore result and accept by contract
    try:
        from Core.MainWindow import request_workspace_change_from_AcPlugin  # type: ignore

        try:
            request_workspace_change_from_AcPlugin(str(path))
        except Exception:
            pass
    except Exception:
        # No GUI or bridge available — still accept
        pass
    return True


def Generate_Ac_Plugin_Template() -> str:
    """Retourne un modèle de plugin AC prêt à l'emploi.

    Le modèle est compatible avec le chargeur ACASL:
    - expose une classe de plugin décorée avec register_plugin
    - fournit la variable globale PLUGIN pour l'exécution sandbox
    - fournit la fonction acasl_register(manager) pour l'enregistrement direct
    """
    return r'''

from __future__ import annotations

# Importer les types depuis le SDK pour rester compatible avec l'hôte
from Plugins_SDK.AcPluginContext import (
    AcPluginBase, PluginMeta, PostCompileContext,
    register_plugin, ACASL_PLUGIN_REGISTER_FUNC,
)


@register_plugin
class MyAcPlugin(AcPluginBase):
    """Exemple minimal de plugin AC.

    - Utilisez le champ 'tags' pour aider l'ordonnancement (voir acasl.tagging):
      ex: ('clean',), ('check',), ('optimize',), ('sign',), ('package',), ('report',)
    - Déclarez les dépendances dans 'requires' via les identifiants de plugins.
    """
    def __init__(self) -> None:
        super().__init__(
            meta=PluginMeta(
                id="my.ac.plugin",
                name="My AC Plugin",
                version="0.1.0",
                description="Describe what this plugin does after compilation.",
                author="Your Name",
                tags=("package",),  # ajustez selon la phase ciblée
            ),
            requires=(),  # ex: ("other.plugin.id",)
            priority=100,  # priorité numérique (plus petit = plus tôt)
        )

    def on_post_compile(self, ctx: PostCompileContext) -> None:
        """Point d'entrée du plugin (post-compilation).

        Utilisez ctx.iter_artifacts(include, exclude) pour parcourir les artefacts compilés.
        Utilisez ctx.iter_files(include, exclude) pour parcourir les fichiers du workspace.
        Le code doit être idempotent et robuste.
        """
        # Exemple: itérer sur les artefacts compilés
        for artifact in ctx.iter_artifacts(["*.exe", "*.app", "*.so"], []):
            # TODO: effectuer une action (signature, packaging, etc.)
            _ = artifact
        # Aucun retour attendu; lever une exception pour signaler un échec

    def apply_i18n(self, gui, tr: dict[str, str]) -> None:
        """Appliquer les traductions à l'interface si le plugin expose une UI.

        - gui: objet graphique hôte (peut être None en mode headless)
        - tr: dictionnaire de chaînes localisées
        """
        # Optionnel: implémenter si nécessaire
        return None


# Instance globale (facilitée pour l'exécution en sandbox)
PLUGIN = MyAcPlugin()


def acasl_register(manager) -> None:
    """Point d'extension appelé par le chargeur pour enregistrer le plugin.

    L'hôte invoquera manager.add_plugin(PLUGIN).
    """
    manager.add_plugin(PLUGIN)
'''


__all__ = [
    "AcPluginBase",
    "PostCompileContext",
    "PluginMeta",
    "ACASL",
    "ExecutionReport",
    "register_plugin",
    "ACASL_PLUGIN_REGISTER_FUNC",
    "set_selected_workspace",
    "Generate_Ac_Plugin_Template",
]