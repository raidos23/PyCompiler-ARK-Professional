# SPDX-License-Identifier: GPL-3.0-only
"""
Dialog Creator (ACASL) - Boîtes de dialogue sûres pour plugins

Objectif
- Fournir aux plugins une façade simple pour demander une autorisation utilisateur,
  des entrées texte ou une liste de permissions.
- Utilise PySide6 (Qt) quand disponible, avec retombée sûre (valeurs par défaut)
  en environnement non interactif/headless.

Fonctions
- ask_yes_no(title, text, default=False) -> bool
- request_text_input(title, label, default="", multiline=False) -> Optional[str]
- request_permissions(title, description, permissions, default_grant=False) -> dict

Note
- Aucune fenêtre n’est affichée en mode non interactif; les valeurs par défaut sont renvoyées.
- Un QApplication minimal est créé à la demande si nécessaire et absent.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

Permission = Union[Tuple[str, str], Dict[str, Any]]

__all__ = [
    "ask_yes_no",
    "request_permissions",
    "request_text_input",
    "Permission",
]


# --------------------------
# Détection d'environnement
# --------------------------

def _truthy_env(v: Optional[str]) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _is_noninteractive() -> bool:
    # Honorer les flags globaux injectés par l'hôte/sandbox
    if _truthy_env(os.environ.get("PYCOMPILER_ACASL_NONINTERACTIVE")):
        return True
    if _truthy_env(os.environ.get("PYCOMPILER_NONINTERACTIVE")):
        return True
    # Détection headless rapide (Linux/macOS)
    try:
        if os.name != "nt" and (not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")):
            return True
    except Exception:
        pass
    return False


# --------------------------
# Helpers Qt (import paresseux)
# --------------------------

def _ensure_qapp() -> Optional[Any]:
    """S'assure qu'une QApplication existe si PySide6 est disponible.
    Retourne l'instance de QApplication ou None si indisponible/échec.
    """
    try:
        from PySide6.QtWidgets import QApplication  # type: ignore
    except Exception:
        return None
    try:
        app = QApplication.instance()
        if app is not None:
            return app
        return QApplication([])
    except Exception:
        return None


# --------------------------
# API publique
# --------------------------

def ask_yes_no(title: str, text: str, *, default: bool = False, parent: Optional[Any] = None) -> bool:
    """Question binaire Oui/Non. Retourne True (Oui) ou False (Non).
    En mode non interactif/headless, renvoie 'default'.
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
    """Demande à l'utilisateur une saisie texte. Retourne str ou None si annulé.
    En mode non interactif/headless, renvoie 'default' si fourni, sinon None.
    """
    if _is_noninteractive():
        return str(default) if default is not None else None
    app = _ensure_qapp()
    if app is None:
        return str(default) if default is not None else None
    try:
        from PySide6.QtWidgets import (  # type: ignore
            QDialog,
            QVBoxLayout,
            QLabel,
            QLineEdit,
            QPlainTextEdit,
            QHBoxLayout,
            QPushButton,
        )
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
    """Affiche une boîte de dialogue de permissions (liste de cases à cocher).

    permissions: itérable de tuples (key, label) ou de dicts {key, label, default}
    default_grant: coche par défaut en l'absence d'UI

    Retourne un dict:
      - accepted: bool (True si OK)
      - remember: bool (souvenir du choix)
      - granted: dict[str, bool] (clé -> accordée)
    """
    # Normaliser les permissions
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

    # Fallback non interactif / pas d'UI
    fallback = {
        "accepted": True,
        "remember": False,
        "granted": {s["key"]: bool(s["default"]) for s in specs},
    }
    if _is_noninteractive():
        return fallback
    app = _ensure_qapp()
    if app is None:
        return fallback

    try:
        from PySide6.QtWidgets import (  # type: ignore
            QCheckBox,
            QDialog,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
            QWidget,
        )
    except Exception:
        return fallback

    try:
        dlg = QDialog(parent)
        dlg.setWindowTitle(str(title))
        root = QVBoxLayout(dlg)
        if description:
            root.addWidget(QLabel(str(description), dlg))

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

        chk_remember = QCheckBox("Remember my choice", dlg)
        root.addWidget(chk_remember)

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
        return fallback