from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta
from Plugins_SDK.GeneralContext import Logging, Dialog

log = Logging
dialog = Dialog

META = PluginMeta(
    id="cleaner",
    name="cleaner",
    version="1.0.0",
    description="clean the workspace (.pyc and __pycache__)",
)


# classe principale du plugin
class Cleaner(BcPluginBase):

    def on_pre_compile(self, ctx):  # methode d'execution en pré_compilation
        dialog.msg_question(
            self=dialog,
            title="Cleaner",
            text="Want you clean the workspace (.pyc and __pycache__)",
            default_yes=True,
        )
        log.log_info("not problem")
        return super().on_pre_compile(ctx)

    pass

    def apply_i18n(self, gui, tr):
        return super().apply_i18n(gui, tr)


# enregistrement automatique du pllugin dans le registre de bcasl
PLUGIN = Cleaner(META)


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
