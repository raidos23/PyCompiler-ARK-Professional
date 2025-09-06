# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

# Stable i18n facade for engines
from utils.i18n import (
    normalize_lang_pref,
    available_languages,
    resolve_system_language,
    get_translations,
)  # type: ignore[F401]

__all__ = [
    "normalize_lang_pref",
    "available_languages",
    "resolve_system_language",
    "get_translations",
]
