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
Plugins_SDK
===========

Kit de développement pour plugins ARK++ couvrant:
- Contexte BC (Before Compilation)
- Contexte AC (After Compilation)
- Contexte CE (Core Extension)
- Contexte UI (boîtes de dialogue, i18n)

Ce package expose une API stable pour les plugins tiers.
"""

# Expose uniquement les sous-packages pour éviter les imports précoces
# Les Context concrets (Ac/Bc) sont disponibles dans leurs sous-modules respectifs.

# from . import AcPluginContext as AcPluginContext  # noqa: F401  # ACASL removed
from . import BcPluginContext as BcPluginContext  # noqa: F401
from . import GeneralContext as GeneralContext  # noqa: F401


__version__ = "1.0.0"

__all__ = [
    # "AcPluginContext",  # ACASL removed
    "BcPluginContext",
    "GeneralContext",
    "__version__",
]
