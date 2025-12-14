# Système de Dialog pour Plugins

from typing import Optional

# Qt toolkits
try:
    from PySide6 import QtCore as _QtC, QtWidgets as _QtW  # type: ignore
except Exception:  # pragma: no cover
    _QtW = None  # type: ignore
    _QtC = None  # type: ignore

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

    
   
from typing import Optional

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


class Dialog:
    
    def show_msgbox(self, kind: str, title: str, text: str, *, default: Optional[str] = None) -> Optional[bool]:
        return show_msgbox(kind, title, text, default=default)

    def msg_info(self, title: str, text: str) -> None:
        show_msgbox("info", title, text)

    def msg_warn(self, title: str, text: str) -> None:
        show_msgbox("warning", title, text)

    def msg_error(self, title: str, text: str) -> None:
        show_msgbox("error", title, text)

    def msg_question(self, title: str, text: str, default_yes: bool = True) -> bool:
        return bool(show_msgbox("question", title, text, default="Yes" if default_yes else "No"))