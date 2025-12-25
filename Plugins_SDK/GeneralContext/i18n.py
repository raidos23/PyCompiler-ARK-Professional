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

"""
Apply plugin-local i18n from Plugins/<plugin_name>/languages/*.json independent of app languages.

"""

from typing import Any, Union

try:
    from bcasl import BcPluginBase
except ImportError:
    BcPluginBase = type(None)  # type: ignore

try:
    from acasl import AcPluginBase
except ImportError:
    AcPluginBase = type(None)  # type: ignore



# Keep live Plugins Ac/Bc/Ce instances to support dynamic interactions (e.g., i18n refresh)
INSTANCES: dict[str, Any] = {}


def apply_translations(gui, tr: dict) -> None:
    """Propagate i18n translations to all Plugin types that expose 'apply_i18n(gui, tr)'."""
    try:
        for plugin_id, inst in list(INSTANCES.items()):
            try:
                fn = getattr(inst, "apply_i18n", None)
                if callable(fn):
                    fn(gui, tr)
            except Exception:
                continue
    except Exception:
        pass