# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

"""
PyCompiler Pro++ — Cross-platform hardened bootstrap
- OS-specific environment safety (UTF-8, DPI, Wayland/macOS)
- Crash logging to platform-appropriate directories
- Qt message handler and high-DPI attributes configured before QApplication
- Global excepthook and faulthandler
- Graceful signal handling (SIGINT/SIGTERM; SIGBREAK on Windows)
- macOS PATH augmentation for GUI-launched app (Homebrew paths)
"""

import faulthandler
import os
import platform
import signal
import sys
import traceback
from pathlib import Path

# Ensure project root has priority on sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path[:1]:
    sys.path.insert(0, ROOT_DIR)

from Core import __version__ as APP_VERSION

IS_WINDOWS = os.name == "nt" or platform.system().lower().startswith("win")
IS_DARWIN = platform.system().lower().startswith("darwin")
IS_LINUX = platform.system().lower().startswith("linux")

# Reduce Qt startup noise unless explicitly verbose
if not os.environ.get("PYCOMPILER_VERBOSE"):
    os.environ.setdefault(
        "QT_LOGGING_RULES",
        "qt.qpa.*=false;qt.quick.*=false;qt.scenegraph.*=false;qt.*.debug=false;qt.*.info=false;qt.gui.*.warning=false;qt.widgets.*.warning=false",
    )

# UTF-8 everywhere
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# DPI/scaling hints
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
# Wayland fractional scaling workaround (Linux)
if IS_LINUX:
    os.environ.setdefault("QT_WAYLAND_DISABLE_FRACTIONAL_SCALE", "1")
# macOS: prefer layer-backed widgets for better rendering
if IS_DARWIN:
    os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")
    # GUI-launched apps often have a reduced PATH; ensure common Homebrew paths are present
    try:
        path = os.environ.get("PATH", "")
        add = []
        for p in ("/opt/homebrew/bin", "/usr/local/bin"):
            if p not in path:
                add.append(p)
        if add:
            os.environ["PATH"] = (
                os.pathsep.join(add + [path]) if path else os.pathsep.join(add)
            )
    except Exception:
        pass
# Linux: ensure a UTF-8 locale if not set
if IS_LINUX:
    if not os.environ.get("LC_ALL") and not os.environ.get("LANG"):
        os.environ["LC_ALL"] = "C.UTF-8"


# Determine a platform-appropriate crash log directory
def _platform_log_dir() -> Path:
    try:
        if IS_WINDOWS:
            base = (
                os.environ.get("LOCALAPPDATA")
                or os.environ.get("APPDATA")
                or str(Path.home() / "AppData" / "Local")
            )
            return Path(base) / "PyCompiler_ProPP" / "logs"
        if IS_DARWIN:
            return Path.home() / "Library" / "Logs" / "PyCompiler_ProPP"
        # Linux and others
        return Path.home() / ".cache" / "PyCompiler_ProPP"
    except Exception:
        return Path.cwd() / "logs"


# Enable faulthandler with persistent log file
try:
    _log_dir = _platform_log_dir()
    _log_dir.mkdir(parents=True, exist_ok=True)
    crash_log = _log_dir / "crash.log"
    try:
        _crash_fp = open(crash_log, "a", encoding="utf-8", errors="ignore")
        faulthandler.enable(_crash_fp)  # type: ignore[arg-type]
    except Exception:
        faulthandler.enable()
except Exception:
    try:
        faulthandler.enable()
    except Exception:
        pass

# Import Qt after environment tuning
from PySide6.QtCore import (
    QCoreApplication,
    Qt,
    QTimer,
    QtMsgType,
    qInstallMessageHandler,
)
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

# Application metadata and high-DPI attributes BEFORE QApplication
try:
    QCoreApplication.setOrganizationName("PyCompiler")
    QCoreApplication.setOrganizationDomain("pycompiler.local")
    QCoreApplication.setApplicationName("PyCompiler ARK++")
    QCoreApplication.setApplicationVersion(APP_VERSION)
    # Qt 6 enables high-DPI scaling by default; avoid deprecated attributes
    # Environment variables QT_AUTO_SCREEN_SCALE_FACTOR/QT_ENABLE_HIGHDPI_SCALING are set above
except Exception:
    pass

# Trigger dynamic discovery of engine plugins at startup (after env/Qt attributes)


def _qt_message_handler(mode, context, message):
    # Silence warnings/debug/info unless verbose requested
    if not os.environ.get("PYCOMPILER_VERBOSE") and mode in (
        QtMsgType.QtWarningMsg,
        QtMsgType.QtInfoMsg,
        QtMsgType.QtDebugMsg,
    ):
        return
    try:
        sys.__stderr__.write((message or "") + "\n")
    except Exception:
        pass


def _excepthook(etype, value, tb):
    # Global last-chance handler: print to stderr and crash log
    try:
        msg = "\n".join(
            [
                "\n=== Unhandled exception ===",
                f"Platform: {platform.platform()} Python: {platform.python_version()}",
                "".join(traceback.format_exception(etype, value, tb)),
                "=== End exception ===\n",
            ]
        )
        try:
            sys.__stderr__.write(msg)
        except Exception:
            pass
        try:
            if "crash_log" in globals():
                with open(crash_log, "a", encoding="utf-8", errors="ignore") as f:
                    f.write(msg)
        except Exception:
            pass
    finally:
        try:
            app = QApplication.instance()
            if app is not None:
                app.quit()
        except Exception:
            pass
        os._exit(1)


# Install handlers early
qInstallMessageHandler(_qt_message_handler)
sys.excepthook = _excepthook


# Graceful termination on signals
def _handle_signal(signum, _frame):
    try:
        app = QApplication.instance()
        if app is not None:
            app.quit()
    except Exception:
        pass


for _sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
    try:
        if _sig is not None:
            signal.signal(_sig, _handle_signal)
    except Exception:
        pass
# Windows: also catch CTRL_BREAK_EVENT
if IS_WINDOWS and hasattr(signal, "SIGBREAK"):
    try:
        signal.signal(signal.SIGBREAK, _handle_signal)  # type: ignore[attr-defined]
    except Exception:
        pass

from Core.worker import PyInstallerWorkspaceGUI


def main(argv: list[str]) -> int:
    try:
        app = QApplication(argv)
        # Splash screen: affiche l'image 'splash.*' depuis le dossier 'logo' si disponible
        splash = None
        try:
            logo_dir = os.path.join(ROOT_DIR, "logo")
            safe_ver = "".join(
                c for c in APP_VERSION if c.isalnum() or c in (".", "-", "_")
            )
            names = [
                f"splash_v{safe_ver}.png",
                "splash.png",
                "splash.jpg",
                "splash.jpeg",
                "splash.bmp",
            ]
            for _name in names:
                _path = os.path.join(logo_dir, _name)
                if os.path.isfile(_path):
                    _pix = QPixmap(_path)
                    if not _pix.isNull():
                        # Limiter la taille pour éviter tout affichage plein écran
                        try:
                            screen = app.primaryScreen()
                            geo = (
                                screen.availableGeometry()
                                if screen is not None
                                else None
                            )
                            max_side = 720
                            if geo is not None:
                                max_side = int(min(geo.width(), geo.height()) * 0.5)
                                max_side = max(240, min(max_side, 720))
                            if _pix.width() > max_side or _pix.height() > max_side:
                                _pix = _pix.scaled(
                                    max_side,
                                    max_side,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                        except Exception:
                            pass
                        splash = QSplashScreen(_pix)
                        splash.show()
                        try:
                            # Centrer le splash sur l'écran actif
                            if screen is not None:
                                sg = splash.frameGeometry()
                                center = (
                                    geo.center()
                                    if geo is not None
                                    else screen.geometry().center()
                                )
                                splash.move(
                                    center.x() - sg.width() // 2,
                                    center.y() - sg.height() // 2,
                                )
                        except Exception:
                            pass
                        app.processEvents()
                        # Messages d'étapes affichés sur le splash (FR/EN)
                        try:
                            align = Qt.AlignHCenter | Qt.AlignBottom
                            col = QColor(255, 255, 255)
                            splash.showMessage(
                                "Initialisation… / Initializing…", align, col
                            )
                            app.processEvents()
                            QTimer.singleShot(
                                700,
                                lambda: splash.showMessage(
                                    "Chargement du thème… / Loading theme…", align, col
                                ),
                            )
                            QTimer.singleShot(
                                1400,
                                lambda: splash.showMessage(
                                    "Découverte des moteurs… / Discovering engines…",
                                    align,
                                    col,
                                ),
                            )
                            QTimer.singleShot(
                                2300,
                                lambda: splash.showMessage(
                                    "Préparation de l’interface… / Preparing UI…",
                                    align,
                                    col,
                                ),
                            )
                        except Exception:
                            pass
                    break
        except Exception:
            splash = None
        if splash is not None:
            delay_ms = 3500
            try:
                delay_ms = int(os.environ.get("PYCOMPILER_SPLASH_DELAY_MS", "3500"))
            except Exception:
                delay_ms = 3500

            def _launch_main():
                try:
                    w = PyInstallerWorkspaceGUI()
                    w.show()
                    # Resserrement auto pour très petits écrans
                    try:
                        from PySide6.QtWidgets import QLabel, QLayout

                        screen2 = app.primaryScreen()
                        geo2 = (
                            screen2.availableGeometry() if screen2 is not None else None
                        )
                        if geo2 and (geo2.width() < 1000 or geo2.height() < 650):
                            try:
                                lays = (
                                    w.ui.findChildren(QLayout)
                                    if hasattr(w, "ui")
                                    else []
                                )
                                for _l in lays:
                                    try:
                                        _l.setContentsMargins(6, 6, 6, 6)
                                        _l.setSpacing(6)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            try:
                                lbl = getattr(w, "sidebar_logo", None)
                                if lbl is None and hasattr(w, "ui"):
                                    lbl = w.ui.findChild(QLabel, "sidebar_logo")
                                if lbl is not None and lbl.pixmap() is not None:
                                    pm = lbl.pixmap()
                                    if pm is not None:
                                        lbl.setPixmap(
                                            pm.scaled(
                                                120,
                                                120,
                                                Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation,
                                            )
                                        )
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        splash.finish(w)
                    except Exception:
                        pass
                except Exception:
                    _excepthook(*sys.exc_info())

            QTimer.singleShot(max(0, delay_ms), _launch_main)
        else:
            w = PyInstallerWorkspaceGUI()
            w.show()
            # Resserrement auto pour très petits écrans
            try:
                from PySide6.QtWidgets import QLabel, QLayout

                screen3 = app.primaryScreen()
                geo3 = screen3.availableGeometry() if screen3 is not None else None
                if geo3 and (geo3.width() < 1000 or geo3.height() < 650):
                    try:
                        lays = w.ui.findChildren(QLayout) if hasattr(w, "ui") else []
                        for _l in lays:
                            try:
                                _l.setContentsMargins(6, 6, 6, 6)
                                _l.setSpacing(6)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        lbl = getattr(w, "sidebar_logo", None)
                        if lbl is None and hasattr(w, "ui"):
                            lbl = w.ui.findChild(QLabel, "sidebar_logo")
                        if lbl is not None and lbl.pixmap() is not None:
                            pm = lbl.pixmap()
                            if pm is not None:
                                lbl.setPixmap(
                                    pm.scaled(
                                        120,
                                        120,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                )
                    except Exception:
                        pass
            except Exception:
                pass
        rc = app.exec()
        return int(rc) if isinstance(rc, int) else 0
    except Exception:
        _excepthook(*sys.exc_info())
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
