"""
Apply plugin-local i18n from Plugins/<plugin_name>/languages/*.json independent of app languages.

"""

from bcasl import BcPluginBase
from acasl import AcPluginBase


# Keep live PLugins Ac/Bc instances to support dynamic interactions (e.g., i18n refresh)
INSTANCES: dict[str, BcPluginBase, AcPluginBase] = {}


# methode pour traduire les dialogues des PLugins Ac/Bc
def apply_translations(gui, tr: dict) -> None:
    """Propagate i18n translations to all Plugin types that expose 'apply_i18n(gui, tr)'."""
    try:
        for eid, inst in list(INSTANCES.items()):
            try:
                fn = getattr(inst, "apply_i18n", None)
                if callable(fn):
                    fn(gui, tr)
            except Exception:
                continue
    except Exception:
        pass
