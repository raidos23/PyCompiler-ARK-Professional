# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
API_SDK.progress — Progress and messaging utilities for API plugins

This module encapsulates UI/console progress reporting and message boxes in a
single place for better modularity and independent evolution.
"""
import getpass
import platform
from typing import Optional

# Optional Qt toolkits
try:
    from PySide6 import QtCore as _QtC, QtWidgets as _QtW  # type: ignore
except Exception:  # pragma: no cover
    try:
        from PyQt5 import QtCore as _QtC, QtWidgets as _QtW  # type: ignore
    except Exception:  # pragma: no cover
        _QtW = None  # type: ignore
        _QtC = None  # type: ignore

# Try to import app-level ProgressDialog for consistency
try:
    from Core.dialogs import ProgressDialog as _AppProgressDialog  # type: ignore
except Exception:
    _AppProgressDialog = None


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


def show_msgbox(kind: str, title: str, text: str, *, parent=None, buttons=None, default=None):
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
            return True if (default and str(default).lower() in ("yes", "ok", "true", "1")) else False
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
            return True if (default and str(default).lower() in ("yes", "ok", "true", "1")) else False
        return None


class ProgressHandle:
    """UI/console progress dialog with optional cancelation support.

    - Uses app-level ProgressDialog when available for consistent behavior.
    - Falls back to QProgressDialog if Qt is available; else prints to console.
    - Not thread-safe by itself; intended for use from the GUI thread.
    """

    def __init__(self, title: str = "", text: str = "", maximum: int = 0, cancelable: bool = False) -> None:
        self._title = str(title)
        self._text = str(text)
        self.maximum = int(maximum) if maximum else 0
        self.value = 0
        self._cancelable = bool(cancelable)
        self._canceled = False
        self._dlg = None
        self._app_dlg = None
        self._last_pct = -1
        # Non-interactive or no QApplication: skip any Qt dialogs, use console fallback
        if _is_noninteractive() or _QtW is None or _QtW.QApplication.instance() is None:
            return
        # Prefer the app-level ProgressDialog for consistent behavior
        if _AppProgressDialog is not None and _QtW is not None:
            try:
                parent = _qt_active_parent()
                dlg = _AppProgressDialog(self._title or "Progress", parent, cancelable=self._cancelable)
                dlg.set_message(self._text or self._title)
                if self.maximum > 0:
                    dlg.set_progress(0, self.maximum)
                else:
                    dlg.set_progress(0, 0)
                dlg.show()
                try:
                    _ = _QtW.QApplication.processEvents()
                    try:
                        dlg.raise_()
                        dlg.activateWindow()
                    except Exception:
                        pass
                except Exception:
                    pass
                self._app_dlg = dlg
                return
            except Exception:
                self._app_dlg = None
        # Fallback to Qt's QProgressDialog
        if _QtW is not None and _QtW.QApplication.instance() is not None:
            try:
                parent = _qt_active_parent()
                dlg = _QtW.QProgressDialog(parent)
                dlg.setWindowTitle(self._title or "Progress")
                dlg.setLabelText(self._text or self._title)
                if self._cancelable:
                    dlg.setCancelButtonText("Cancel")
                else:
                    dlg.setCancelButton(None)
                dlg.setAutoClose(False)
                dlg.setAutoReset(False)
                if self.maximum > 0:
                    dlg.setRange(0, self.maximum)
                else:
                    dlg.setRange(0, 0)
                dlg.setMinimumDuration(0)
                try:
                    if _QtC is not None:
                        dlg.setWindowModality(_QtC.Qt.WindowModal)
                except Exception:
                    pass
                try:
                    dlg.canceled.connect(self._on_canceled)  # type: ignore[attr-defined]
                except Exception:
                    pass
                dlg.show()
                try:
                    _ = _QtW.QApplication.processEvents()
                    try:
                        dlg.raise_()
                        dlg.activateWindow()
                    except Exception:
                        pass
                except Exception:
                    pass
                self._dlg = dlg
            except Exception:
                self._dlg = None

    def _on_canceled(self) -> None:
        self._canceled = True

    @property
    def canceled(self) -> bool:
        try:
            if self._app_dlg is not None and hasattr(self._app_dlg, "is_canceled") and self._app_dlg.is_canceled():
                self._canceled = True
        except Exception:
            pass
        return self._canceled

    def set_maximum(self, maximum: int) -> None:
        self.maximum = int(maximum) if maximum else 0
        if self._app_dlg is not None:
            try:
                if self.maximum > 0:
                    self._app_dlg.set_progress(0, self.maximum)
                else:
                    self._app_dlg.set_progress(0, 0)
            except Exception:
                pass
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
        if self._app_dlg is not None:
            try:
                if text is not None:
                    self._app_dlg.set_message(self._text)
                if self.maximum > 0:
                    self._app_dlg.set_progress(min(self.value, self.maximum))
                else:
                    _ = _QtW.QApplication.processEvents()  # type: ignore[attr-defined]
                try:
                    if self._app_dlg.is_canceled():
                        self._canceled = True
                except Exception:
                    pass
            except Exception:
                pass
        elif self._dlg is not None:
            try:
                if text is not None:
                    self._dlg.setLabelText(self._text)
                if self.maximum > 0:
                    self._dlg.setValue(min(self.value, self.maximum))
                try:
                    self._dlg.repaint()
                except Exception:
                    pass
                _ = _QtW.QApplication.processEvents()  # type: ignore[attr-defined]
            except Exception:
                pass
        else:
            if self.maximum > 0:
                pct = int(min(100, max(0, (self.value * 100) / self.maximum)))
                print(f"[PROGRESS] {self._title}: {pct}% - {self._text}")
            else:
                print(f"[PROGRESS] {self._title}: {self._text}")

    def step(self, delta: int = 1) -> None:
        self.update(self.value + int(delta))

    def close(self) -> None:
        if self._app_dlg is not None:
            try:
                self._app_dlg.close()
            except Exception:
                pass
            finally:
                self._app_dlg = None
        if self._dlg is not None:
            try:
                if self.maximum > 0:
                    self._dlg.setValue(self.maximum)
                self._dlg.reset()
                self._dlg.close()
            except Exception:
                pass
            finally:
                self._dlg = None

    def __enter__(self) -> ProgressHandle:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.close()
        except Exception:
            pass
        return False


def create_progress(title: str, text: str = "", maximum: int = 0, cancelable: bool = False) -> ProgressHandle:
    return ProgressHandle(title=title, text=text, maximum=maximum, cancelable=cancelable)


def progress(title: str, text: str = "", maximum: int = 0, cancelable: bool = False) -> ProgressHandle:
    return create_progress(title=title, text=text, maximum=maximum, cancelable=cancelable)


def sys_msgbox_for_installing(
    subject: str, explanation: Optional[str] = None, title: str = "Installation required"
) -> Optional[tuple]:
    """Ask for install authorization (multi-OS).

    Windows: returns ("uac", None) if confirmed.
    Linux/macOS: returns ("sudo", password) if confirmed.
    None if canceled.
    """
    is_windows = platform.system().lower().startswith("win")
    msg = (
        f"Installation of '{subject}' requires administrator privileges.\n"
        + (f"\n{explanation}\n" if explanation else "")
        + (
            "\nOn Windows, UAC elevation will be requested."
            if is_windows
            else "\nOn Linux/macOS, your sudo password is required."
        )
    )
    if _is_noninteractive():
        try:
            print(f"[INSTALL] {title}: {msg} (non-interactive)")
        except Exception:
            pass
        return None
    if _QtW is not None and _QtW.QApplication.instance() is not None:
        try:
            parent = _qt_active_parent()
            from Plugins_SDK.progress import show_msgbox as _show

            proceed = _show("question", title, msg, default="Yes")
            if not proceed:
                return None
            if is_windows:
                return ("uac", None)
            pwd, ok = _QtW.QInputDialog.getText(
                parent,
                title,
                "Enter your password (sudo):",
                _QtW.QLineEdit.Password,
            )
            if not ok:
                return None
            pwd = str(pwd)
            return ("sudo", pwd) if pwd else None
        except Exception:
            pass
    try:
        print(f"[INSTALL] {title}: {msg}")
        ans = input("Continue? [y/N] ").strip().lower()
        if ans not in ("y", "yes", "o", "oui"):
            return None
    except Exception:
        pass
    if is_windows:
        return ("uac", None)
    try:
        pwd = getpass.getpass("Password (sudo): ")
        return ("sudo", pwd) if pwd else None
    except Exception:
        return None


__all__ = [
    "ProgressHandle",
    "create_progress",
    "progress",
    "show_msgbox",
    "sys_msgbox_for_installing",
]
