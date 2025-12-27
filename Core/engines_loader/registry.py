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

from __future__ import annotations

from typing import Optional, Any

from .base import CompilerEngine
from Core.ark_config_loader import load_engine_ui_state, save_engine_ui_state

_REGISTRY: dict[str, type[CompilerEngine]] = {}
_ORDER: list[str] = []
# UI mapping: engine id -> tab index
_TAB_INDEX: dict[str, int] = {}
# Keep live engine instances to support dynamic interactions (e.g., i18n refresh)
_INSTANCES: dict[str, CompilerEngine] = {}


def unregister(eid: str) -> None:
    """Unregister an engine id and its tab mapping if present."""
    try:
        if eid in _REGISTRY:
            del _REGISTRY[eid]
        if eid in _ORDER:
            _ORDER.remove(eid)
        if eid in _TAB_INDEX:
            del _TAB_INDEX[eid]
    except Exception:
        pass


def register(engine_cls: type[CompilerEngine]):
    """Register an engine class. Enforces a non-empty unique id.

    If the same id is registered again with the same class object, this is a no-op.
    If a different class attempts to register the same id, the new registration is ignored.
    """
    eid = getattr(engine_cls, "id", None)
    if not eid or not isinstance(eid, str):
        raise ValueError("Engine class must define an 'id' attribute (str)")
    try:
        existing = _REGISTRY.get(eid)
        if existing is not None and existing is not engine_cls:
            # Ignore conflicting registration to avoid destabilizing at runtime
            return existing
        _REGISTRY[eid] = engine_cls
        if eid not in _ORDER:
            _ORDER.append(eid)
        return engine_cls
    except Exception:
        # Fail closed: do not crash the app
        return engine_cls


def _apply_widgets_state(container, widgets_state: dict) -> None:
    """Apply basic properties to child widgets given a simple state mapping.
    Supported props: checked, text, enabled, visible, currentIndex.
    """
    try:
        for wname, props in widgets_state.items():
            try:
                w = container.findChild(object, wname)
                if w is None:
                    continue
                for k, v in (props or {}).items():
                    try:
                        if k == "checked" and hasattr(w, "setChecked"):
                            w.setChecked(bool(v))
                        elif k == "text" and hasattr(w, "setText"):
                            w.setText(str(v))
                        elif k == "enabled" and hasattr(w, "setEnabled"):
                            w.setEnabled(bool(v))
                        elif k == "visible" and hasattr(w, "setVisible"):
                            w.setVisible(bool(v))
                        elif k == "currentIndex" and hasattr(w, "setCurrentIndex"):
                            w.setCurrentIndex(int(v))
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass


def save_engine_ui(gui, engine_id: str, updates: dict[str, dict[str, Any]]) -> bool:
    """Public helper for engines to persist UI state into ARK_Main_Config.yml.
    Engines pass a mapping {widgetName: {prop: value}}. Returns True on success.
    """
    try:
        ws = getattr(gui, "workspace_dir", None)
        if not ws:
            return False
        return save_engine_ui_state(ws, engine_id, updates)
    except Exception:
        return False


def get_engine(eid: str) -> Optional[type[CompilerEngine]]:
    try:
        return _REGISTRY.get(eid)
    except Exception:
        return None


def available_engines() -> list[str]:
    try:
        return list(_ORDER)
    except Exception:
        return []


def bind_tabs(gui) -> None:
    """Create tabs for all registered engines that expose create_tab and store indexes.
    Robust to individual engine failures and avoids raising to the UI layer.
    """
    try:
        tabs = getattr(gui, "compiler_tabs", None)
        if not tabs:
            return
        for eid in list(_ORDER):
            try:
                engine = create(eid)
                # Keep instance for later interactions (i18n, etc.)
                _INSTANCES[eid] = engine
                res = getattr(engine, "create_tab", None)
                if not callable(res):
                    continue
                pair = res(gui)
                if not pair:
                    continue
                widget, label = pair
                # Apply saved UI state for this engine (simple mapping by objectName)
                try:
                    ws = getattr(gui, "workspace_dir", None)
                    if ws:
                        widgets_state = load_engine_ui_state(ws, eid)
                        if isinstance(widgets_state, dict) and widgets_state:
                            _apply_widgets_state(widget, widgets_state)
                except Exception:
                    pass
                try:
                    existing = tabs.indexOf(widget)
                except Exception:
                    existing = -1
                if isinstance(existing, int) and existing >= 0:
                    _TAB_INDEX[eid] = existing
                else:
                    idx = tabs.addTab(widget, label)
                    _TAB_INDEX[eid] = int(idx)
                # Apply engine i18n immediately if GUI already has active translations
                try:
                    tr = getattr(gui, "_tr", None)
                    fn = getattr(engine, "apply_i18n", None)
                    if callable(fn) and isinstance(tr, dict):
                        fn(gui, tr)
                except Exception:
                    pass
            except Exception:
                # keep UI responsive even if a plugin tab fails
                continue
    except Exception:
        # Swallow to avoid breaking app init
        pass


def apply_translations(gui, tr: dict) -> None:
    """Propagate i18n translations to all engines that expose 'apply_i18n(gui, tr)'."""
    try:
        for eid, inst in list(_INSTANCES.items()):
            try:
                fn = getattr(inst, "apply_i18n", None)
                if callable(fn):
                    fn(gui, tr)
            except Exception:
                continue
    except Exception:
        pass


def get_engine_for_tab(index: int) -> Optional[str]:
    try:
        for eid, idx in _TAB_INDEX.items():
            if idx == index:
                return eid
    except Exception:
        pass
    return None


def create(eid: str) -> CompilerEngine:
    cls = get_engine(eid)
    if not cls:
        raise KeyError(f"Engine '{eid}' is not registered")
    try:
        return cls()
    except Exception as e:
        # If engine instantiation fails, propagate a clearer message
        raise RuntimeError(f"Failed to instantiate engine '{eid}': {e}")
