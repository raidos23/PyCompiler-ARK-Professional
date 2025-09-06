# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

# Stable i18n facade for engines
from utils.i18n import (
    available_languages,
    get_translations,
    normalize_lang_pref,
    resolve_system_language,
)

__all__ = [
    "normalize_lang_pref",
    "available_languages",
    "resolve_system_language",
    "get_translations",
]
