# SPDX-License-Identifier: GPL-3.0-only
# Language/i18n utilities for PyCompiler Pro++ (async-only public API)

from __future__ import annotations

import json
import locale
import os
import asyncio
from typing import Dict, Any, List

# Built-in fallback for English if language files are missing
FALLBACK_EN: Dict[str, Any] = {
    "_meta": {"code": "en", "name": "English"},
    # Sidebar & main buttons
    "select_folder": "📁 Workspace",
    "select_files": "📋 Files",
    "build_all": "🚀 Build",
    "export_config": "💾 Export config",
    "import_config": "📥 Import config",
    "cancel_all": "⛔ Cancel",
    "suggest_deps": "🔎 Analyze dependencies",
    "help": "❓ Help",
    "show_stats": "📊 Statistics",
    "select_lang": "Choose language",
    "select_theme": "Choose theme",
    "choose_theme_button": "Choose theme",
    "choose_theme_system_button": "Choose theme (System)",
    # Workspace
    "venv_button": "Choose venv folder manually",
    "label_workspace_section": "1. Select workspace folder",
    "venv_label": "venv selected: None",
    "label_folder": "No folder selected",
    # Files
    "label_files_section": "2. Files to build",
    "btn_remove_file": "🗑️ Remove selected file",
    # Logs
    "label_logs_section": "Build logs",
    # PyInstaller tab
    "tab_pyinstaller": "PyInstaller",
    "opt_onefile": "Onefile",
    "opt_windowed": "Windowed",
    "opt_noconfirm": "Noconfirm",
    "opt_clean": "Clean",
    "opt_noupx": "No UPX",
    "opt_main_only": "Build only main.py or app.py",
    "btn_select_icon": "🎨 Choose icon (.ico)",
    "opt_debug": "Debug mode (--debug)",
    "opt_auto_install": "Auto-install missing modules",
    "opt_silent_errors": "Do not show error box (silent mode)",
    # Nuitka tab
    "tab_nuitka": "Nuitka",
    "nuitka_onefile": "Onefile (--onefile)",
    "nuitka_standalone": "Standalone (--standalone)",
    "nuitka_disable_console": "Disable Windows console (--windows-disable-console)",
    "nuitka_show_progress": "Show progress (--show-progress)",
    # "nuitka_plugins": removed (auto-managed)
    "nuitka_output_dir": "Output folder (--output-dir)",
    "btn_nuitka_icon": "🎨 Choose Nuitka icon (.ico)",
}


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _languages_dir() -> str:
    return os.path.join(_project_root(), "languages")


# Normalization helper must be pure (no I/O or system lookups)
# Leave "System" unresolved; callers must resolve system language asynchronously when needed.
async def normalize_lang_pref(pref: str | None) -> str:
    if not pref or pref == "System":
        return "System"
    pref_l = pref.lower()
    if pref_l in ("english", "en"):
        return "en"
    if pref_l in ("français", "francais", "fr"):
        return "fr"
    # Arbitrary language code - accept as-is
    return pref


# Internal sync helpers (non-public); used via asyncio.to_thread

def _resolve_system_language_sync() -> str:
    try:
        loc = locale.getdefaultlocale()[0] or ""
        return "fr" if loc.lower().startswith(("fr", "fr_")) else "en"
    except Exception:
        return "en"


def _load_language_file_sync(code: str) -> Dict[str, Any] | None:
    fpath = os.path.join(_languages_dir(), f"{code}.json")
    if not os.path.isfile(fpath):
        return None
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _available_languages_sync() -> List[Dict[str, str]]:
    langs: List[Dict[str, str]] = []
    try:
        path = _languages_dir()
        if not os.path.isdir(path):
            return [{"code": FALLBACK_EN["_meta"]["code"], "name": FALLBACK_EN["_meta"]["name"]}]
        for fname in sorted(os.listdir(path)):
            if not fname.endswith(".json"):
                continue
            default_code = os.path.splitext(fname)[0]
            fpath = os.path.join(path, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("_meta", {}) if isinstance(data, dict) else {}
                name = None
                code = None
                if isinstance(data, dict):
                    name = data.get("name") or (meta.get("name") if isinstance(meta, dict) else None)
                    code = data.get("code") or (meta.get("code") if isinstance(meta, dict) else None)
                langs.append({
                    "code": code or default_code,
                    "name": name or default_code,
                })
            except Exception:
                langs.append({"code": default_code, "name": default_code})
    except Exception:
        pass
    if not langs:
        langs = [{"code": FALLBACK_EN["_meta"]["code"], "name": FALLBACK_EN["_meta"]["name"]}]
    return langs


# Public async API
async def resolve_system_language() -> str:
    return await asyncio.to_thread(_resolve_system_language_sync)


async def available_languages() -> List[Dict[str, str]]:
    return await asyncio.to_thread(_available_languages_sync)


async def get_translations(lang_pref: str | None) -> Dict[str, Any]:
    code = await normalize_lang_pref(lang_pref)
    if code == "System":
        code = await resolve_system_language()
    data = await asyncio.to_thread(_load_language_file_sync, code)
    if not isinstance(data, dict) or not data:
        # Fallback to bundled English
        data = FALLBACK_EN.copy()
    # Normalize meta: support either top-level fields or nested _meta
    top_name = data.get("name") if isinstance(data, dict) else None
    top_code = data.get("code") if isinstance(data, dict) else None
    meta_in = data.get("_meta", {}) if isinstance(data, dict) else {}
    meta = {
        "code": (top_code or (meta_in.get("code") if isinstance(meta_in, dict) else None) or code),
        "name": (top_name or (meta_in.get("name") if isinstance(meta_in, dict) else None) or ("English" if code == "en" else ("Français" if code == "fr" else code)))
    }
    data["_meta"] = meta
    return data
