# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

# ceci est un exemple pourles plugin du type BC

from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta, PreCompileContext
from Plugins_SDK.GeneralContext import Dialog
from Plugins_SDK.GeneralContext.g import Logging


log = dialog = Dialog 

META = PluginMeta(
    id="cleaner",
    name="cleaner",
    version="1.0.0",
    description="clean the workspace (.pyc and __pycache__)",
    author="Samuel Amen Ague",
)


# classe principale du plugin
class Cleaner(BcPluginBase):
    def install_deps(deps):
        return super().install_deps()

    def on_pre_compile(
        self, ctx: PreCompileContext
    ):  # methode d'execution en pré_compilation
        dialog.msg_question(
            self=dialog,
            title="Cleaner",
            text="Want you clean the workspace (.pyc and __pycache__)",
            default_yes=True,
        )
        log.log_info(message="cleaner marche correctement")

    def apply_i18n(self, gui, tr):
        return super().apply_i18n(gui, tr)


# enregistrement automatique du plugin dans le registre de bcasl
PLUGIN = Cleaner(META)


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
