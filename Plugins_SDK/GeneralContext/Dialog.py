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

from pathlib import Path
from typing import (
    Optional,
    NamedTuple,
)
import getpass
import re
import platform

# Simple redaction of obvious secrets in logs
_REDACT_PATTERNS = [
    re.compile(r"(password\s*[:=]\s*)([^\s]+)", re.IGNORECASE),
    re.compile(r"(authorization\s*[:]\s*bearer\s+)([A-Za-z0-9\-_.]+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)([A-Za-z0-9\-_.]{12,})", re.IGNORECASE),
]

# Qt toolkits
try:
    from PySide6 import QtCore as _QtC, QtWidgets as _QtW  # type: ignore
except Exception:  # pragma: no cover
    _QtW = None  # type: ignore
    _QtC = None  # type: ignore

# Import des classes de Core.dialogs
from Core.dialogs import ProgressDialog, CompilationProcessDialog, _invoke_in_main_thread


def _redact_secrets(text: str) -> str:
    if not text:
        return text
    redacted = str(text)
    try:
        for pat in _REDACT_PATTERNS:
            redacted = pat.sub(lambda m: m.group(1) + "<redacted>", redacted)
    except Exception:
        pass
    return redacted


def _is_noninteractive() -> bool:
    try:
        import os as _os

        v = _os.environ.get("PYCOMPILER_NONINTERACTIVE")
        if v is None:
            return False
        return str(v).strip().lower() not in ("", "0", "false", "no")
    except Exception:
        return False


def _qt_active_parent():
    if _QtW is None:
        return None
    try:
        app = _QtW.QApplication.instance()
        if app is None:
            return None
        w = app.activeWindow()
        if w:
            return w
        try:
            tls = app.topLevelWidgets()
            if tls:
                return tls[0]
        except Exception:
            pass
        return None
    except Exception:
        return None


def show_msgbox(
    kind: str, title: str, text: str, *, parent=None, buttons=None, default=None
):
    """
    Show a message box if a Qt toolkit is available; fallback to console output otherwise.
    Executes in the main Qt thread to ensure theme inheritance and proper UI integration.

    kind: 'info' | 'warning' | 'error' | 'question'
    Returns:
      - question: True if Yes (or default), False otherwise
      - others: None
    """
    if _QtW is None or _QtW.QApplication.instance() is None or _is_noninteractive():
        # Console fallback
        print(f"[MSGBOX:{kind}] {title}: {text}")
        if kind == "question":
            return (
                True
                if (default and str(default).lower() in ("yes", "ok", "true", "1"))
                else False
            )
        return None
    
    def _show_in_main_thread():
        try:
            parent_widget = parent or _qt_active_parent()
            mb = _QtW.QMessageBox(parent_widget)
            mb.setWindowTitle(str(title))
            mb.setText(str(text))
            if kind == "warning":
                mb.setIcon(_QtW.QMessageBox.Warning)
            elif kind == "error":
                mb.setIcon(_QtW.QMessageBox.Critical)
            elif kind == "question":
                mb.setIcon(_QtW.QMessageBox.Question)
            else:
                mb.setIcon(_QtW.QMessageBox.Information)

            if kind == "question":
                yes = _QtW.QMessageBox.Yes
                no = _QtW.QMessageBox.No
                mb.setStandardButtons(yes | no)
                if default and str(default).lower() == "no":
                    mb.setDefaultButton(no)
                else:
                    mb.setDefaultButton(yes)
                res = mb.exec_() if hasattr(mb, "exec_") else mb.exec()
                return res == yes
            else:
                ok = _QtW.QMessageBox.Ok
                mb.setStandardButtons(ok)
                mb.setDefaultButton(ok)
                _ = mb.exec_() if hasattr(mb, "exec_") else mb.exec()
                return None
        except Exception:
            print(f"[MSGBOX:{kind}] {title}: {text}")
            if kind == "question":
                return (
                    True
                    if (default and str(default).lower() in ("yes", "ok", "true", "1"))
                    else False
                )
            return None
    
    return _invoke_in_main_thread(_show_in_main_thread)


class InstallAuth(NamedTuple):
    method: str  # 'sudo' (POSIX) | 'uac' (Windows)
    secret: Optional[str] = None  # password for 'sudo', None for 'uac'


def sys_msgbox_for_installing(
    subject: str, explanation: Optional[str] = None, title: str = "Installation requise"
) -> Optional[InstallAuth]:
    """Demande interactive d'autorisation d'installation multi-OS.

    - Windows: pas de mot de passe (UAC natif). Retourne InstallAuth(method='uac', secret=None) si confirmé.
    - Linux/macOS: demande de mot de passe sudo. Retourne InstallAuth(method='sudo', secret='<pwd>') si confirmé.

    Aucun secret n'est loggé. Fournit uniquement les informations nécessaires au plugin pour exécuter
    l'installation avec élévation adaptée à l'OS.
    """
    is_windows = platform.system().lower().startswith("win")
    msg = (
        f"L'installation de '{subject}' nécessite des privilèges administrateur.\n"
        + (f"\n{explanation}\n" if explanation else "")
        + (
            "\nSur Windows, une élévation UAC sera demandée."
            if is_windows
            else "\nSur Linux/macOS, votre mot de passe sudo est requis."
        )
    )
    # UI Qt
    if _QtW is not None:
        try:
            parent = _qt_active_parent()
            proceed = show_msgbox("question", title, msg, default="Yes")
            if not proceed:
                return None
            if is_windows:
                return InstallAuth("uac", None)
            # POSIX: demande de mot de passe
            pwd, ok = _QtW.QInputDialog.getText(
                parent,
                title,
                "Entrez votre mot de passe (sudo):",
                _QtW.QLineEdit.Password,
            )
            if not ok:
                return None
            pwd = str(pwd)
            return InstallAuth("sudo", pwd) if pwd else None
        except Exception:
            # Fallback console si problème Qt
            pass
    # Fallback console
    try:
        print(f"[INSTALL] {title}: {msg}")
        ans = input("Continuer ? [y/N] ").strip().lower()
        if ans not in ("y", "yes", "o", "oui"):
            return None
    except Exception:
        # Si input non disponible, on tente quand même la suite
        pass
    if is_windows:
        return InstallAuth("uac", None)
    try:
        pwd = getpass.getpass("Mot de passe (sudo): ")
        return InstallAuth("sudo", pwd) if pwd else None
    except Exception:
        return None


class Dialog:
    """Dialog class for plugins - uses Core.dialogs classes for all UI operations."""

    def show_msgbox(
        self, kind: str, title: str, text: str, *, default: Optional[str] = None
    ) -> Optional[bool]:
        return show_msgbox(kind, title, text, default=default)

    def msg_info(self, title: str, text: str) -> None:
        show_msgbox("info", title, text)

    def msg_warn(self, title: str, text: str) -> None:
        show_msgbox("warning", title, text)

    def msg_error(self, title: str, text: str) -> None:
        show_msgbox("error", title, text)

    def msg_question(self, title: str, text: str, default_yes: bool = True) -> bool:
        return bool(
            show_msgbox("question", title, text, default="Yes" if default_yes else "No")
        )

    def log(self, message: str) -> None:
        """Log a message with optional redaction of secrets."""
        msg = _redact_secrets(message) if getattr(self, "redact_logs", True) else message
        if hasattr(self, "log_fn") and self.log_fn:
            try:
                self.log_fn(msg)
                return
            except Exception:
                pass
        print(msg)

    def log_info(self, message: str) -> None:
        self.log(f"[INFO] {message}")

    def log_warn(self, message: str) -> None:
        self.log(f"[WARN] {message}")

    def log_error(self, message: str) -> None:
        self.log(f"[ERROR] {message}")

    def sys_msgbox_for_installing(
        self,
        subject: str,
        explanation: Optional[str] = None,
        title: str = "Installation requise",
    ) -> Optional[InstallAuth]:
        return sys_msgbox_for_installing(subject, explanation=explanation, title=title)

    def progress(
        self, title: str, text: str = "", maximum: int = 0, cancelable: bool = False
    ) -> ProgressDialog:
        """Crée et retourne un ProgressDialog de Core pour suivre une tâche.
        
        Utilise directement Core.dialogs.ProgressDialog pour assurer:
        - L'héritage du thème de l'application
        - L'intégration visuelle avec l'application principale
        - La sécurité des threads
        
        Args:
            title: Titre du dialog
            text: Texte initial du dialog
            maximum: Valeur maximale (0 = indéterminé)
            cancelable: Si True, affiche un bouton Annuler
            
        Returns:
            ProgressDialog instance from Core.dialogs
        """
        return ProgressDialog(title=title, cancelable=cancelable)
