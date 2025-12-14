from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta
from Plugins_SDK.GeneralContext import Logging

log = Logging

META = PluginMeta(
    id="cleaner",
    name="cleaner",
    version="1.0.0",
    description="clean the workspace (.pyc and __pycache__)",
)


class Cleaner(BcPluginBase):
    def on_pre_compile(self, context):
        return super().on_pre_compile(context)

    pass

    def apply_i18n(self, gui, tr):
        return super().apply_i18n(gui, tr)


# enregistrement automatique du pllugin dans le registre de bcasl
PLUGIN = Cleaner(META)


def bcasl_register(manager):
    manager.add_plugin(PLUGIN)
