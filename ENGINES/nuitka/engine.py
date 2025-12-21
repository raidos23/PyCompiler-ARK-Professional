# SPDX-License-Identifier: GPL-3.0-only
# Author: Samuel Amen Ague
# Copyright (C) 2025 Samuel Amen Ague
from __future__ import annotations

import os
import platform
from typing import Optional

from engine_sdk import (
    CompilerEngine,
    SysDependencyManager,
    pip_executable,
    pip_install,
    pip_show,
    resolve_project_venv,
)
from engine_sdk.auto_build_command import _tr


class NuitkaEngine(CompilerEngine):
    id = "nuitka"
    name = "Nuitka"

    def preflight(self, gui, file: str) -> bool:
        # System deps (engine-owned)
        try:
            import shutil as _shutil
            import subprocess as _subprocess

            from PySide6.QtWidgets import QMessageBox

            def _tr(fr, en):
                try:
                    return gui.tr(fr, en)
                except Exception:
                    return fr

            os_name = platform.system()
            if os_name == "Linux":
                import shutil as _shutil

                # Vérification complète des dépendances système requises pour Nuitka
                # Outils/commandes requis
                required_cmds = {
                    "gcc": "gcc",
                    "g++": "g++",
                    "make": "make",
                    "pkg-config/pkgconf": "pkg-config",
                    "patchelf": "patchelf",
                    "python3-dev/python3-devel (headers)": "python3-config",
                }
                # Variantes 7zip
                sevenz = _shutil.which("7z") or _shutil.which("7za")
                missing = []
                for label, cmd in required_cmds.items():
                    c = _shutil.which(cmd)
                    if not c:
                        if cmd == "pkg-config" and not (
                            _shutil.which("pkg-config") or _shutil.which("pkgconf")
                        ):
                            missing.append("pkg-config/pkgconf")
                        elif cmd != "pkg-config":
                            missing.append(label)
                if not sevenz:
                    missing.append("p7zip (7z/7za)")

                # Python et en-têtes de développement
                python3_bin = _shutil.which("python3")
                if not python3_bin:
                    missing.append("python3")
                    has_python_dev = False
                else:
                    has_python_dev = False
                    try:
                        rc = _subprocess.run(
                            [
                                python3_bin,
                                "-c",
                                "import sysconfig,os,sys;p=sysconfig.get_config_h_filename();sys.exit(0 if p and os.path.exists(p) else 1)",
                            ],
                            stdout=_subprocess.DEVNULL,
                            stderr=_subprocess.DEVNULL,
                        )
                        has_python_dev = rc.returncode == 0
                    except Exception:
                        has_python_dev = False
                    if not has_python_dev:
                        if "python3-dev/python3-devel (headers)" not in missing:
                            missing.append("python3-dev")

                # Libs via pkg-config quand disponible
                has_pkgconf = (
                    _shutil.which("pkg-config") or _shutil.which("pkgconf")
                ) is not None
                missing_libs = []
                if has_pkgconf:
                    for pc in ("openssl", "zlib"):
                        try:
                            rc = _subprocess.run(
                                ["pkg-config", "--exists", pc],
                                stdout=_subprocess.DEVNULL,
                                stderr=_subprocess.DEVNULL,
                            )
                            if rc.returncode != 0:
                                missing_libs.append(pc)
                        except Exception:
                            pass
                # libxcrypt-compat (libcrypt.so.1)
                needs_libxcrypt = False
                try:
                    rc = _subprocess.run(
                        [
                            "bash",
                            "-lc",
                            "command -v ldconfig >/dev/null 2>&1 && ldconfig -p | grep -E 'libcrypt\\.so\\.1|libxcrypt' -q",
                        ],
                        stdout=_subprocess.DEVNULL,
                        stderr=_subprocess.DEVNULL,
                    )
                    needs_libxcrypt = rc.returncode != 0
                except Exception:
                    # Fallback best-effort
                    needs_libxcrypt = not (
                        os.path.exists("/usr/lib/libcrypt.so.1")
                        or os.path.exists("/lib/x86_64-linux-gnu/libcrypt.so.1")
                    )

                if missing or missing_libs or needs_libxcrypt:
                    sdm = SysDependencyManager(parent_widget=gui)
                    pm = sdm.detect_linux_package_manager()
                    if not pm:
                        from PySide6.QtWidgets import QMessageBox

                        QMessageBox.critical(
                            gui,
                            _tr(
                                "Gestionnaire de paquets non détecté",
                                "Package manager not detected",
                            ),
                            _tr(
                                "Impossible d'installer automatiquement les dépendances système (build tools, python3-dev, pkg-config, openssl, zlib, etc.).",
                                "Unable to auto-install system dependencies (build tools, python3-dev, pkg-config, openssl, zlib, etc.).",
                            ),
                        )
                        return False
                    # Paquets par distribution (liste complète)
                    if pm == "apt":
                        packages = [
                            "build-essential",
                            "python3",
                            "python3-dev",
                            "python3-pip",
                            "pkg-config",
                            "libssl-dev",
                            "zlib1g-dev",
                            "libxcrypt1",
                            "patchelf",
                            "p7zip-full",
                        ]
                    elif pm == "dnf":
                        packages = [
                            "gcc",
                            "gcc-c++",
                            "make",
                            "binutils",
                            "glibc-devel",
                            "python3",
                            "python3-devel",
                            "python3-pip",
                            "pkgconf-pkg-config",
                            "openssl-devel",
                            "zlib-devel",
                            "libxcrypt-compat",
                            "patchelf",
                            "p7zip",
                        ]
                    elif pm == "pacman":
                        packages = [
                            "base-devel",
                            "python",
                            "python-pip",
                            "pkgconf",
                            "openssl",
                            "zlib",
                            "libxcrypt-compat",
                            "patchelf",
                            "p7zip",
                        ]
                    else:  # zypper
                        packages = [
                            "gcc",
                            "gcc-c++",
                            "make",
                            "binutils",
                            "glibc-devel",
                            "python3",
                            "python3-devel",
                            "python3-pip",
                            "pkg-config",
                            "libopenssl-devel",
                            "zlib-devel",
                            "libxcrypt-compat",
                            "patchelf",
                            "p7zip-full",
                        ]
                    try:
                        details = []
                        if missing:
                            details.append("manquants: " + ", ".join(missing))
                        if missing_libs:
                            details.append("libs: " + ", ".join(missing_libs))
                        if needs_libxcrypt:
                            details.append("libxcrypt-compat")
                        if details:
                            gui.log.append(
                                "🔧 Dépendances système manquantes détectées ("
                                + "; ".join(details)
                                + ")."
                            )
                    except Exception:
                        pass
                    proc = sdm.install_packages_linux(packages, pm=pm)
                    if not proc:
                        gui.log.append(
                            "⛔ Compilation Nuitka annulée ou installation non démarrée.\n"
                        )
                        return False
                    try:
                        gui.log.append(
                            "⏳ Installation des dépendances système en arrière-plan..."
                        )
                    except Exception:
                        pass
                    return False
            elif os_name == "Windows":
                # Tentative d'installation automatique via winget: Visual Studio Build Tools (VCTools)
                sdm = SysDependencyManager(parent_widget=gui)
                pkgs = [
                    {
                        "id": "Microsoft.VisualStudio.2022.BuildTools",
                        "override": "--add Microsoft.VisualStudio.Workload.VCTools --passive --norestart",
                    }
                ]
                p = sdm.install_packages_windows(pkgs)
                if p is not None:
                    # Installation en cours (asynchrone); arrêter le préflight et relancer après
                    return False
                # Fallback: guidance MinGW-w64 si winget indisponible
                import webbrowser

                from PySide6.QtWidgets import QMessageBox

                msg = QMessageBox(gui)
                msg.setIcon(QMessageBox.Question)
                msg.setWindowTitle(
                    _tr("Installer MinGW-w64 (mhw)", "Install MinGW-w64 (mhw)")
                )
                msg.setText(
                    _tr(
                        "Pour compiler avec Nuitka sous Windows, il faut un compilateur C/C++.\n\nWinget indisponible. Voulez-vous ouvrir la page MinGW-w64 (winlibs.com) ?\n\nAprès installation, relancez la compilation.",
                        "To build with Nuitka on Windows, a C/C++ compiler is required.\n\nWinget unavailable. Do you want to open the MinGW-w64 page (winlibs.com)?\n\nAfter installation, restart the build.",
                    )
                )
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setDefaultButton(QMessageBox.Yes)
                if msg.exec() == QMessageBox.Yes:
                    webbrowser.open("https://winlibs.com/")
                    QMessageBox.information(
                        gui,
                        _tr("Téléchargement lancé", "Download started"),
                        _tr(
                            "La page officielle de MinGW-w64 a été ouverte. Installez puis relancez la compilation.",
                            "The official MinGW-w64 page has been opened. Install and retry the build.",
                        ),
                    )
                return False
        except Exception:
            pass
        # Venv + nuitka tool
        try:
            vm = getattr(gui, "venv_manager", None)
            # Résoudre le venv
            vroot = resolve_project_venv(gui)
            if not vroot:
                if vm and getattr(gui, "workspace_dir", None):
                    vm.create_venv_if_needed(gui.workspace_dir)
                else:
                    gui.log.append(
                        _tr(
                            "❌ Aucun venv détecté. Créez un venv dans le workspace.",
                            "❌ No venv detected. Create a venv in the workspace.",
                        )
                    )
                return False

            # Vérifier/installer nuitka
            def _ensure_tool_with_pip(package: str) -> bool:
                pip = pip_executable(vroot)
                try:
                    if pip_show(gui, pip, package) == 0:
                        gui.log.append(f"✅ {package} déjà installé")
                        return True
                    gui.log.append(f"📦 Installation de {package}…")
                    ok = pip_install(gui, pip, package) == 0
                    gui.log.append(
                        "✅ Installation réussie"
                        if ok
                        else f"❌ Installation échouée ({package})"
                    )
                    return ok
                except Exception:
                    return False

            if vm:
                # Fast non-blocking heuristic; if present, proceed
                if vm.is_tool_installed(vroot, "nuitka"):
                    return True
                # Async confirm, then install if missing
                gui.log.append(
                    _tr(
                        "🔎 Vérification de Nuitka dans le venv (asynchrone)...",
                        "🔎 Verifying Nuitka in venv (async)...",
                    )
                )

                def _on_check(ok: bool):
                    try:
                        if ok:
                            gui.log.append(
                                _tr(
                                    "✅ Nuitka déjà installé",
                                    "✅ Nuitka already installed",
                                )
                            )
                        else:
                            gui.log.append(
                                _tr(
                                    "📦 Installation de Nuitka dans le venv (asynchrone)...",
                                    "📦 Installing Nuitka in venv (async)...",
                                )
                            )
                            vm.ensure_tools_installed(vroot, ["nuitka"])
                    except Exception:
                        pass

                try:
                    vm.is_tool_installed_async(vroot, "nuitka", _on_check)
                except Exception:
                    gui.log.append(
                        _tr(
                            "📦 Installation de Nuitka dans le venv (asynchrone)...",
                            "📦 Installing Nuitka in venv (async)...",
                        )
                    )
                    vm.ensure_tools_installed(vroot, ["nuitka"])
                return False
            else:
                if not _ensure_tool_with_pip("nuitka"):
                    return False
                return True
        except Exception:
            pass
        return True

    def build_command(self, gui, file: str) -> list[str]:
        return gui.build_nuitka_command(file)

    def program_and_args(self, gui, file: str) -> Optional[tuple[str, list[str]]]:
        # Nuitka s'exécute avec python -m nuitka dans le venv; resolve via VenvManager
        try:
            vm = getattr(gui, "venv_manager", None)
            vroot = vm.resolve_project_venv() if vm else None
            if not vroot:
                gui.log.append(
                    _tr(
                        "❌ Venv introuvable pour exécuter Nuitka.",
                        "❌ Venv not found to run Nuitka.",
                    )
                )
                gui.show_error_dialog(os.path.basename(file))
                return None
            vbin = os.path.join(
                vroot, "Scripts" if platform.system() == "Windows" else "bin"
            )
            python_path = os.path.join(
                vbin, "python" if platform.system() != "Windows" else "python.exe"
            )
            if not os.path.isfile(python_path):
                gui.log.append(
                    _tr(
                        "❌ python non trouvé dans le venv : ",
                        "❌ python not found in venv: ",
                    )
                    + str(python_path)
                )
                gui.show_error_dialog(os.path.basename(file))
                return None
            cmd = self.build_command(gui, file)
            return python_path, cmd[1:]
        except Exception:
            return None

    def environment(self, gui, file: str) -> Optional[dict[str, str]]:
        return None

    def create_tab(self, gui):
        try:
            from PySide6.QtWidgets import QWidget

            tab = getattr(gui, "tab_nuitka", None)
            if tab and isinstance(tab, QWidget):
                return tab, _tr("Nuitka", "Nuitka")
        except Exception:
            pass
        return None
