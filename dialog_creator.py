# SPDX-License-Identifier: GPL-3.0-only
"""
Dialog Creator - Safe user dialogs for API plugins

Purpose
- Provide a small, safe facade for plugins to request user authorizations or inputs.
- Uses Qt (PySide6) when available. Gracefully falls back to defaults in non-interactive/headless environments.
- Keeps a narrow surface: yes/no, permission checklist, and text input dialogs.

Design goals
- No global side effects. Creates a QApplication only if strictly needed (and absent).
- Non-interactive mode detection via environment flags: PYCOMPILER_NONINTERACTIVE in particular.
- Reasonable defaults when UI is not available or is disabled.

Usage (from a plugin)
    from dialog_creator import ask_yes_no, request_permissions

    ok = ask_yes_no("Dangerous operation", "Do you allow this?", default=False)
    perms = request_permissions(
        "Permissions",
        "Grant the following permissions to this plugin:",
        [("network", "Allow network access"), ("fs_write", "Allow file writes")],
        default_grant=False,
    )
    if not perms["accepted"]:
        # user canceled
        return
    if not perms["granted"].get("fs_write"):
        raise PermissionError("Plugin requires fs_write permission")
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

Permission = Union[Tuple[str, str], Dict[str, Any]]

__all__ = [
    "ask_yes_no",
    "request_permissions",
    "request_text_input",
]


# --------------------------
# Environment detection
# --------------------------

def _is_truthy_env(value: Optional[str]) -> bool:
    if value is None:
        return False
    v = str(value).strip().lower()
    return v in ("1", "true", "yes", "y")


def _is_noninteractive() -> bool:
    # Honor host-side non-interactive setting propagated to sandbox
    if _is_truthy_env(os.environ.get("PYCOMPILER_NONINTERACTIVE")):
        return True
    # Quick headless detection (Linux/macOS)
    try:
        if os.name != "nt" and (not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")):
            return True
    except Exception:
        pass
    return False


# --------------------------
# Qt helpers (lazy import)
# --------------------------

def _ensure_qapp() -> Optional[Any]:
    """Ensure a QApplication instance exists when Qt is available.
    Returns QApplication instance or None on failure/unavailable.
    """
    try:
        from PySide6.QtWidgets import QApplication  # type: ignore
    except Exception:
        return None
    try:
        app = QApplication.instance()
        if app is not None:
            return app
        # Create a minimal application (no arguments) in sandbox if permitted
        return QApplication([])
    except Exception:
        return None


# --------------------------
# Public API
# --------------------------

def ask_yes_no(title: str, text: str, *, default: bool = False, parent: Optional[Any] = None) -> bool:
    """Display a Yes/No question. Returns True for Yes, False for No.
    In non-interactive/headless mode, returns the 'default' value.
    """
    if _is_noninteractive():
        return bool(default)
    app = _ensure_qapp()
    if app is None:
        return bool(default)
    try:
        from PySide6.QtWidgets import QMessageBox  # type: ignore
    except Exception:
        return bool(default)
    try:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(str(title))
        box.setText(str(text))
        yes_btn = box.addButton(QMessageBox.Yes)
        no_btn = box.addButton(QMessageBox.No)
        # default button
        box.setDefaultButton(yes_btn if default else no_btn)
        box.exec()
        return box.clickedButton() is yes_btn
    except Exception:
        return bool(default)


def request_text_input(
    title: str,
    label: str,
    *,
    default: str = "",
    multiline: bool = False,
    parent: Optional[Any] = None,
) -> Optional[str]:
    """Ask the user for text input. Returns str or None when canceled.
    In non-interactive/headless mode, returns 'default' if provided, else None.
    """
    if _is_noninteractive():
        return str(default) if default is not None else None
    app = _ensure_qapp()
    if app is None:
        return str(default) if default is not None else None
    try:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QHBoxLayout, QPushButton  # type: ignore
    except Exception:
        return str(default) if default is not None else None

    try:
        dlg = QDialog(parent)
        dlg.setWindowTitle(str(title))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(str(label), dlg))
        if multiline:
            editor: Any = QPlainTextEdit(dlg)
            editor.setPlainText(str(default or ""))
        else:
            editor = QLineEdit(dlg)
            editor.setText(str(default or ""))
        lay.addWidget(editor)
        btns = QHBoxLayout()
        btn_ok = QPushButton("OK", dlg)
        btn_cancel = QPushButton("Cancel", dlg)
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        btns.addStretch(1)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        lay.addLayout(btns)
        if dlg.exec() == QDialog.Accepted:
            return editor.toPlainText() if multiline else editor.text()
        return None
    except Exception:
        return str(default) if default is not None else None


def request_permissions(
    title: str,
    description: str,
    permissions: Iterable[Permission],
    *,
    default_grant: bool = False,
    parent: Optional[Any] = None,
) -> Dict[str, Any]:
    """Show a checklist dialog to request multiple permissions at once.

    Parameters
    - title: Dialog title
    - description: A short description of why these permissions are required
    - permissions: iterable of (key, label) tuples or dicts with keys: key, label, default
    - default_grant: default checked state when UI is not available/non-interactive

    Returns a dict with keys:
      - accepted: bool -> True if user pressed OK
      - remember: bool -> True if user wants to remember this decision
      - granted: dict[str, bool] -> mapping of permission key to granted state
    """
    # Normalize permission specs
    specs: List[Dict[str, Any]] = []
    for p in permissions:
        if isinstance(p, dict):
            key = str(p.get("key", "")).strip()
            label = str(p.get("label", key or "Permission"))
            dflt = bool(p.get("default", default_grant))
        else:
            k, l = p  # type: ignore[misc]
            key = str(k).strip()
            label = str(l)
            dflt = bool(default_grant)
        if not key:
            continue
        specs.append({"key": key, "label": label, "default": dflt})

    # Non-interactive/headless fallback -> deny or default_grant
    if _is_noninteractive():
        return {
            "accepted": True,
            "remember": False,
            "granted": {s["key"]: bool(s["default"]) for s in specs},
        }

    app = _ensure_qapp()
    if app is None:
        return {
            "accepted": True,
            "remember": False,
            "granted": {s["key"]: bool(s["default"]) for s in specs},
        }

    try:
        from PySide6.QtWidgets import (
            QCheckBox,
            QDialog,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
            QWidget,
        )  # type: ignore
    except Exception:
        return {
            "accepted": True,
            "remember": False,
            "granted": {s["key"]: bool(s["default"]) for s in specs},
        }

    try:
        dlg = QDialog(parent)
        dlg.setWindowTitle(str(title))
        root = QVBoxLayout(dlg)
        if description:
            root.addWidget(QLabel(str(description), dlg))

        # Scrollable area for many permissions
        area = QScrollArea(dlg)
        area.setWidgetResizable(True)
        inner = QWidget(area)
        inner_lay = QVBoxLayout(inner)
        checks: List[Tuple[str, QCheckBox]] = []
        for s in specs:
            cb = QCheckBox(str(s["label"]))
            cb.setChecked(bool(s["default"]))
            checks.append((s["key"], cb))
            inner_lay.addWidget(cb)
        inner_lay.addStretch(1)
        area.setWidget(inner)
        root.addWidget(area)

        # Remember
        chk_remember = QCheckBox("Remember my choice", dlg)
        root.addWidget(chk_remember)

        # Buttons
        row = QHBoxLayout()
        btn_ok = QPushButton("OK", dlg)
        btn_cancel = QPushButton("Cancel", dlg)
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        row.addStretch(1)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        root.addLayout(row)

        accepted = dlg.exec() == QDialog.Accepted
        granted = {k: cb.isChecked() for (k, cb) in checks}
        return {"accepted": accepted, "remember": chk_remember.isChecked(), "granted": granted}
    except Exception:
        return {
            "accepted": True,
            "remember": False,
            "granted": {s["key"]: bool(s["default"]) for s in specs},
        }
