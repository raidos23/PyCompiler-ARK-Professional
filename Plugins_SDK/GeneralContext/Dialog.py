# Système de Dialog pour Plugins
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    NamedTuple,
)
import fnmatch
import json
import getpass
import re
import platform
import io

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
    try:
        parent = parent or _qt_active_parent()
        mb = _QtW.QMessageBox(parent)
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


class ProgressHandle:
    """Gestion d'une progression avec Qt (QProgressDialog) si disponible, sinon fallback console.

    Utilisation typique:
        ph = create_progress("Installation", "Téléchargement...", maximum=100)
        for i in range(101):
            ph.update(i, f"Étape {i}/100")
        ph.close()
    """

    def __init__(
        self,
        title: str = "",
        text: str = "",
        maximum: int = 0,
        cancelable: bool = False,
    ) -> None:
        self._title = str(title)
        self._text = str(text)
        self.maximum = int(maximum) if maximum else 0
        self.value = 0
        self._cancelable = bool(cancelable)
        self._canceled = False
        self._dlg = None
        self._last_pct = -1
        if _QtW is not None:
            try:
                parent = _qt_active_parent()
                dlg = _QtW.QProgressDialog(parent)
                dlg.setWindowTitle(self._title or "Progression")
                dlg.setLabelText(self._text or self._title)
                if self._cancelable:
                    dlg.setCancelButtonText("Annuler")
                else:
                    dlg.setCancelButton(None)
                dlg.setAutoClose(False)
                dlg.setAutoReset(False)
                if self.maximum > 0:
                    dlg.setRange(0, self.maximum)
                else:
                    # Indéterminée (busy)
                    dlg.setRange(0, 0)
                dlg.setMinimumDuration(0)
                try:
                    dlg.canceled.connect(self._on_canceled)  # type: ignore[attr-defined]
                except Exception:
                    pass
                dlg.show()
                self._dlg = dlg
            except Exception:
                self._dlg = None

    def _on_canceled(self) -> None:  # Qt signal
        self._canceled = True

    @property
    def canceled(self) -> bool:
        return self._canceled

    def set_maximum(self, maximum: int) -> None:
        self.maximum = int(maximum) if maximum else 0
        if self._dlg is not None:
            try:
                if self.maximum > 0:
                    self._dlg.setRange(0, self.maximum)
                else:
                    self._dlg.setRange(0, 0)
            except Exception:
                pass

    def update(self, value: Optional[int] = None, text: Optional[str] = None) -> None:
        if value is not None:
            self.value = max(0, int(value))
        if text is not None:
            self._text = str(text)
        if self._dlg is not None:
            try:
                if text is not None:
                    self._dlg.setLabelText(self._text)
                if self.maximum > 0:
                    self._dlg.setValue(min(self.value, self.maximum))
                _ = _QtW.QApplication.processEvents()  # type: ignore[attr-defined]
            except Exception:
                pass
        else:
            # Fallback console simple (évite le spam)
            if self.maximum > 0:
                pct = int(min(100, max(0, (self.value * 100) / self.maximum)))
                if pct != self._last_pct:
                    print(f"[PROGRESS] {self._title}: {pct}% - {self._text}")
                    self._last_pct = pct
            else:
                print(f"[PROGRESS] {self._title}: {self._text}")

    def step(self, delta: int = 1) -> None:
        self.update(self.value + int(delta))

    def close(self) -> None:
        if self._dlg is not None:
            try:
                # Valeur finale si bornée
                if self.maximum > 0:
                    self._dlg.setValue(self.maximum)
                self._dlg.reset()
                self._dlg.close()
            except Exception:
                pass
            finally:
                self._dlg = None


def create_progress(
    title: str, text: str = "", maximum: int = 0, cancelable: bool = False
) -> ProgressHandle:
    """Crée un handle de progression (Qt si dispo, sinon console)."""
    return ProgressHandle(
        title=title, text=text, maximum=maximum, cancelable=cancelable
    )


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

    # methode de boîtes de Dialog pour permettre une interaction Ui avec les Plugins
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
    ) -> "ProgressHandle":
        """Crée et retourne un handle de progression utilisable pour suivre une tâche.
        - maximum=0 => progression indéterminée (busy)
        - cancelable=True => bouton Annuler (si Qt disponible)
        """
        return create_progress(
            title=title, text=text, maximum=maximum, cancelable=cancelable
        )
