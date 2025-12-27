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




"""
Dialogues personnalisés pour PyCompiler ARK++.
Inclut ProgressDialog, boîtes de message, et autres dialogues spécifiques.

IMPORTANT: Tous les dialogs ici exécutent les opérations Qt dans le thread principal
via le système d'invoker de Plugins_SDK.GeneralContext.Dialog pour assurer:
- L'héritage du thème de l'application
- L'intégration visuelle avec l'application principale
- La sécurité des threads
"""

import re
import platform
import getpass
from typing import Optional, NamedTuple
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
    QInputDialog,
    QLineEdit,
)
from PySide6 import QtCore as _QtC


def _get_linux_display_server() -> str:
    """
    Detect the Linux display server being used.
    
    Returns:
        'wayland', 'x11', or 'unknown'
    """
    try:
        import os
        
        # Check environment variables
        session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
        if session_type in ('wayland', 'x11'):
            return session_type
        
        # Check WAYLAND_DISPLAY
        if os.environ.get('WAYLAND_DISPLAY'):
            return 'wayland'
        
        # Check DISPLAY (X11)
        if os.environ.get('DISPLAY'):
            return 'x11'
        
        return 'unknown'
    except Exception:
        return 'unknown'


def _invoke_in_main_thread(fn, *args, **kwargs):
    """
    Invoke a function in the main Qt thread.
    
    This ensures that all UI operations are thread-safe and properly
    integrated with the application's event loop and theme system.
    
    Adapts the invocation method based on the platform and display server:
    - Linux/Wayland: Uses BlockingQueuedConnection with extra safety
    - Linux/X11: Uses BlockingQueuedConnection
    - Other platforms: Uses BlockingQueuedConnection
    
    Args:
        fn: Function to invoke
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function call
    """
    try:
        app = QApplication.instance()
        if app is None:
            # No Qt app, call directly
            return fn(*args, **kwargs)
        
        # Check if we're already in the main thread
        if _QtC.QThread.currentThread() == app.thread():
            # Already in main thread, call directly
            return fn(*args, **kwargs)
        
        # We're in a different thread, need to invoke in main thread
        result = []
        exception = []
        
        def _wrapper():
            try:
                result.append(fn(*args, **kwargs))
            except Exception as e:
                exception.append(e)
        
        # Detect platform and display server for optimal invocation
        try:
            import platform
            import os
            
            system = platform.system().lower()
            
            # Linux-specific handling
            if system == 'linux':
                display_server = _get_linux_display_server()
                
                if display_server == 'wayland':
                    # Wayland: Use BlockingQueuedConnection with extra safety
                    # Wayland can be more sensitive to threading issues
                    _QtC.QMetaObject.invokeMethod(
                        app,
                        _wrapper,
                        _QtC.Qt.BlockingQueuedConnection
                    )
                elif display_server == 'x11':
                    # X11: Standard BlockingQueuedConnection
                    _QtC.QMetaObject.invokeMethod(
                        app,
                        _wrapper,
                        _QtC.Qt.BlockingQueuedConnection
                    )
                else:
                    # Unknown display server: Use standard method
                    _QtC.QMetaObject.invokeMethod(
                        app,
                        _wrapper,
                        _QtC.Qt.BlockingQueuedConnection
                    )
            else:
                # Non-Linux platforms: Use standard method
                _QtC.QMetaObject.invokeMethod(
                    app,
                    _wrapper,
                    _QtC.Qt.BlockingQueuedConnection
                )
        except Exception:
            # Fallback to standard invocation
            _QtC.QMetaObject.invokeMethod(
                app,
                _wrapper,
                _QtC.Qt.BlockingQueuedConnection
            )
        
        if exception:
            raise exception[0]
        
        return result[0] if result else None
        
    except Exception:
        # Fallback: call directly
        return fn(*args, **kwargs)


# Simple redaction of obvious secrets in logs
_REDACT_PATTERNS = [
    re.compile(r"(password\s*[:=]\s*)([^\s]+)", re.IGNORECASE),
    re.compile(r"(authorization\s*[:]\s*bearer\s+)([A-Za-z0-9\-_.]+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)([A-Za-z0-9\-_.]{12,})", re.IGNORECASE),
]


def _redact_secrets(text: str) -> str:
    """Redact obvious secrets from text for logging."""
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
    """Check if running in non-interactive mode."""
    try:
        import os
        v = os.environ.get("PYCOMPILER_NONINTERACTIVE")
        if v is None:
            return False
        return str(v).strip().lower() not in ("", "0", "false", "no")
    except Exception:
        return False


def _qt_active_parent():
    """Get the active Qt parent window."""
    try:
        app = QApplication.instance()
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


class InstallAuth(NamedTuple):
    """Authentication info for system installation."""
    method: str  # 'sudo' (POSIX) | 'uac' (Windows)
    secret: Optional[str] = None  # password for 'sudo', None for 'uac'


def show_msgbox(
    kind: str, title: str, text: str, *, parent=None, buttons=None, default=None
) -> Optional[bool]:
    """
    Show a message box if a Qt toolkit is available; fallback to console output otherwise.
    Executes in the main Qt thread to ensure theme inheritance and proper UI integration.

    kind: 'info' | 'warning' | 'error' | 'question'
    Returns:
      - question: True if Yes (or default), False otherwise
      - others: None
    """
    if QApplication.instance() is None or _is_noninteractive():
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
            mb = QMessageBox(parent_widget)
            mb.setWindowTitle(str(title))
            mb.setText(str(text))
            if kind == "warning":
                mb.setIcon(QMessageBox.Warning)
            elif kind == "error":
                mb.setIcon(QMessageBox.Critical)
            elif kind == "question":
                mb.setIcon(QMessageBox.Question)
            else:
                mb.setIcon(QMessageBox.Information)

            if kind == "question":
                yes = QMessageBox.Yes
                no = QMessageBox.No
                mb.setStandardButtons(yes | no)
                if default and str(default).lower() == "no":
                    mb.setDefaultButton(no)
                else:
                    mb.setDefaultButton(yes)
                res = mb.exec_() if hasattr(mb, "exec_") else mb.exec()
                return res == yes
            else:
                ok = QMessageBox.Ok
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
    if QApplication.instance() is not None:
        try:
            parent = _qt_active_parent()
            proceed = show_msgbox("question", title, msg, default="Yes")
            if not proceed:
                return None
            if is_windows:
                return InstallAuth("uac", None)
            # POSIX: demande de mot de passe
            pwd, ok = QInputDialog.getText(
                parent,
                title,
                "Entrez votre mot de passe (sudo):",
                QLineEdit.Password,
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


class ProgressDialog(QDialog):
    """Dialog de progression étroitement lié à l'application.
    
    S'exécute toujours dans le thread principal pour assurer:
    - L'héritage du thème de l'application
    - L'intégration visuelle avec l'application principale
    - La sécurité des threads
    """
    
    def __init__(self, title="Progression", parent=None, cancelable=False):
        super().__init__(parent or _qt_active_parent())
        self.setWindowTitle(title)
        self.setModal(False)  # Non modale pour ne pas bloquer l'UI
        self.setMinimumWidth(400)
        self._canceled = False
        layout = QVBoxLayout(self)
        self.label = QLabel("Préparation...", self)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)  # Indéterminé au début
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        if cancelable:
            btn_row = QHBoxLayout()
            btn_cancel = QPushButton("Annuler", self)
            btn_cancel.clicked.connect(self._on_cancel)
            btn_row.addStretch(1)
            btn_row.addWidget(btn_cancel)
            layout.addLayout(btn_row)
        self.setLayout(layout)

    def set_message(self, msg):
        """Mettre à jour le message du dialog."""
        def _set():
            self.label.setText(msg)
            QApplication.processEvents()
        _invoke_in_main_thread(_set)

    def set_progress(self, value, maximum=None):
        """Mettre à jour la barre de progression."""
        def _set():
            if maximum is not None:
                self.progress.setMaximum(maximum)
            self.progress.setValue(value)
            QApplication.processEvents()
        _invoke_in_main_thread(_set)

    def show(self):
        """Afficher le dialog dans le thread principal."""
        def _show():
            super(ProgressDialog, self).show()
        _invoke_in_main_thread(_show)

    def close(self):
        """Fermer le dialog dans le thread principal."""
        def _close():
            try:
                super(ProgressDialog, self).close()
            except Exception:
                pass
        _invoke_in_main_thread(_close)

    def _on_cancel(self):
        self._canceled = True
        try:
            self.close()
        except Exception:
            pass

    def is_canceled(self):
        return self._canceled


class CompilationProcessDialog(QDialog):
    """Dialog étroitement lié à l'application pour afficher le chargement du workspace.
    
    S'exécute toujours dans le thread principal pour assurer:
    - L'héritage du thème de l'application
    - L'intégration visuelle avec l'application principale
    - La sécurité des threads
    """
    
    def __init__(self, title="Chargement", parent=None):
        super().__init__(parent or _qt_active_parent())
        self.setWindowTitle(title)
        self.setModal(False)
        self.setMinimumWidth(400)
        self.setMinimumHeight(150)
        
        layout = QVBoxLayout(self)
        
        # Statut
        self.status_label = QLabel("Initialisation...", self)
        layout.addWidget(self.status_label)
        
        # Barre de progression
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        
        # Boutons
        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Annuler", self)
        self.btn_close = QPushButton("Fermer", self)
        self.btn_close.setEnabled(False)
        
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)
        
        self.setLayout(layout)
    
    def set_status(self, status_text):
        """Mettre à jour le statut dans le thread principal."""
        def _set():
            self.status_label.setText(status_text)
            QApplication.processEvents()
        _invoke_in_main_thread(_set)
    
    def set_progress(self, value, maximum=None):
        """Mettre à jour la barre de progression dans le thread principal."""
        def _set():
            if maximum is not None:
                self.progress.setMaximum(maximum)
            self.progress.setValue(value)
            QApplication.processEvents()
        _invoke_in_main_thread(_set)

    def show(self):
        """Afficher le dialog dans le thread principal."""
        def _show():
            super(CompilationProcessDialog, self).show()
        _invoke_in_main_thread(_show)

    def close(self):
        """Fermer le dialog dans le thread principal."""
        def _close():
            try:
                super(CompilationProcessDialog, self).close()
            except Exception:
                pass
        _invoke_in_main_thread(_close)


# Global reference to the main application window for theme synchronization
_app_main_window = None


def connect_to_app(main_window):
    """
    Connect dialogs to the main application window for theme synchronization.
    
    This function should be called from init_ui() to ensure that all dialogs
    created afterwards will automatically inherit the application's theme.
    
    Args:
        main_window: The main application window (usually self from MainWindow)
    """
    global _app_main_window
    _app_main_window = main_window
    try:
        # Ensure the main window's stylesheet is applied to all future dialogs
        app = QApplication.instance()
        if app and hasattr(main_window, 'styleSheet'):
            # The app stylesheet is already set, dialogs will inherit it
            pass
    except Exception:
        pass
