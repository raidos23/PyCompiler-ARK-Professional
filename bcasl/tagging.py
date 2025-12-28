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

from typing import Any


# Hiérarchie de priorité basée sur les tags (ordre d'exécution)
TAG_PRIORITY_MAP = {
    # Phase 0: Nettoyage et hygiène du workspace
    "clean": 0,
    "cleanup": 0,
    "sanitize": 0,
    "prune": 0,
    "tidy": 0,
    # Phase 1: Validation et vérification des prérequis
    "validation": 10,
    "presence": 10,
    "check": 10,
    "requirements": 10,
    "verify": 10,
    # Phase 2: Préparation et génération des ressources
    "prepare": 20,
    "codegen": 20,
    "generate": 20,
    "fetch": 20,
    "resources": 20,
    "download": 20,
    "install": 20,
    "bootstrap": 20,
    "configure": 20,
    "setup": 20,
    # Phase 3: Conformité et injection de headers
    "license": 30,
    "header": 30,
    "normalize": 30,
    "inject": 30,
    "spdx": 30,
    "banner": 30,
    "copyright": 30,
    "metadata": 30,
    # Phase 4: Linting, formatage et vérification de type
    "lint": 40,
    "format": 40,
    "typecheck": 40,
    "mypy": 40,
    "flake8": 40,
    "ruff": 40,
    "pep8": 40,
    "black": 40,
    "isort": 40,
    "sort-imports": 40,
    "style": 40,
    # Phase 5: Obfuscation, protection et transpilation (dernière passe)
    "obfuscation": 50,
    "obfuscate": 50,
    "transpile": 50,
    "protect": 50,
    "encrypt": 50,
    "minify": 50,
}

# Valeur par défaut pour les tags inconnus
DEFAULT_TAG_PRIORITY = 100


def compute_tag_order(meta_map: dict[str, dict[str, Any]]) -> list[str]:
    """Trie les plugins par score de tag (plus petit d'abord), puis par id.

    Utilise TAG_PRIORITY_MAP pour déterminer la priorité basée sur les tags.
    Tags pris depuis meta_map[pid]["tags"]. Inconnu => DEFAULT_TAG_PRIORITY.

    Phases d'exécution:
    - 0: Nettoyage (clean, cleanup, sanitize)
    - 10: Validation (check, requirements, verify)
    - 20: Préparation (prepare, generate, install, configure)
    - 30: Conformité (license, header, normalize, inject)
    - 40: Linting (lint, format, typecheck, style)
    - 50: Obfuscation (obfuscate, transpile, protect, encrypt)
    - 100: Défaut (aucun tag reconnu)
    """

    def _compute_score(pid: str) -> int:
        """Calcule le score de priorité pour un plugin.

        Retourne le score minimum parmi tous les tags du plugin.
        Si aucun tag, retourne DEFAULT_TAG_PRIORITY.
        """
        try:
            tags = meta_map.get(pid, {}).get("tags")
            if not tags:
                return DEFAULT_TAG_PRIORITY

            if not isinstance(tags, (list, tuple)):
                return DEFAULT_TAG_PRIORITY

            # Normaliser les tags et trouver le score minimum
            scores = []
            for tag in tags:
                tag_str = str(tag).strip().lower()
                if tag_str:
                    score = TAG_PRIORITY_MAP.get(tag_str, DEFAULT_TAG_PRIORITY)
                    scores.append(score)

            return min(scores) if scores else DEFAULT_TAG_PRIORITY
        except Exception:
            return DEFAULT_TAG_PRIORITY

    # Trier par (score, id) pour stabilité et lisibilité
    return sorted(meta_map.keys(), key=lambda x: (_compute_score(x), x))


def get_tag_phase_name(tag: str) -> str:
    """Retourne le nom lisible de la phase pour un tag donné."""
    tag_lower = str(tag).strip().lower()
    score = TAG_PRIORITY_MAP.get(tag_lower, DEFAULT_TAG_PRIORITY)

    phase_names = {
        0: "Nettoyage",
        10: "Validation",
        20: "Préparation",
        30: "Conformité",
        40: "Linting",
        50: "Obfuscation",
        100: "Défaut",
    }

    return phase_names.get(score, f"Phase {score}")


def describe_plugin_priority(plugin_id: str, tags: list[str]) -> str:
    """Retourne une description lisible de la priorité d'un plugin.

    Exemple: "plugin_id (lint, format) -> Phase 4: Linting"
    """
    if not tags:
        return f"{plugin_id} (aucun tag) -> Phase {DEFAULT_TAG_PRIORITY}: Défaut"

    tag_str = ", ".join(str(t).strip().lower() for t in tags)
    scores = [
        TAG_PRIORITY_MAP.get(str(t).strip().lower(), DEFAULT_TAG_PRIORITY) for t in tags
    ]
    min_score = min(scores) if scores else DEFAULT_TAG_PRIORITY
    phase_name = get_tag_phase_name(min_score)

    return f"{plugin_id} ({tag_str}) -> Phase {min_score}: {phase_name}"
