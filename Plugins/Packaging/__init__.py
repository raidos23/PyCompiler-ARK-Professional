# ceci est un plugin de packaging et il est aussi un exemple pourles plugin du type AC

# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

# ceci est un exemple pourles plugin du type Ac

from Plugins_SDK.AcPluginContext import AcPluginBase, PluginMeta, PostCompileContext
from Plugins_SDK.GeneralContext import Dialog
from Plugins_SDK.GeneralContext.g import Logging

log = dialog = Dialog 

META = PluginMeta(
    id="Packaging",
    name="Packaging",
    version="1.0.0",
    description="clean the workspace (.pyc and __pycache__)",
    author="Samuel Amen Ague",
)


# classe principale du plugin
class Packaging(AcPluginBase):
    def install_deps(deps):
        return super().install_deps()

    def on_Post_compile(
        self, ctx: PostCompileContext
    ):  # methode d'execution en pré_compilation
        dialog.msg_question(
            self=dialog,
            title="Packaging",
            text="Want you Package your artifacts",
            default_yes=True,
        )
        log.log_info(message="Packaging marche correctement")

    def apply_i18n(self, gui, tr):
        return super().apply_i18n(gui, tr)


# enregistrement automatique du plugin dans le registre de Acasl
PLUGIN = Packaging(META)


def acasl_register(manager):
    manager.add_plugin(PLUGIN)
