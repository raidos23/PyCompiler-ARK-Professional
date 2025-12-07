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


class PyInstallerEngine(CompilerEngine):
    id = "pyinstaller"
    name = "PyInstaller"

    def _resolve_venv_root(self, gui) -> Optional[str]:
        try:
            vroot = resolve_project_venv(gui)
            return vroot
        except Exception:
            return None

    def _pip_exe(self, vroot: str) -> str:
        return pip_executable(vroot)

    def _ensure_tool_with_pip(self, gui, vroot: str, package: str) -> bool:
        pip = self._pip_exe(vroot)
        try:
            if pip_show(gui, pip, package) == 0:
                try:
                    gui.log.append(
                        gui.tr(
                            f"✅ {package} déjà installé",
                            f"✅ {package} already installed",
                        )
                    )
                except Exception:
                    pass
                return True
            try:
                gui.log.append(
                    gui.tr(
                        f"📦 Installation de {package}…", f"📦 Installing {package}…"
                    )
                )
            except Exception:
                pass
            ok = pip_install(gui, pip, package) == 0
            try:
                if ok:
                    gui.log.append(
                        gui.tr("✅ Installation réussie", "✅ Installation successful")
                    )
                else:
                    gui.log.append(
                        gui.tr(
                            f"❌ Installation échouée ({package})",
                            f"❌ Installation failed ({package})",
                        )
                    )
            except Exception:
                pass
            return ok
        except Exception:
            return False

    def preflight(self, gui, file: str) -> bool:
        # Ensure venv exists and PyInstaller is installed; trigger install if needed
        try:
            # System dependencies (Linux)
            try:
                import shutil as _shutil

                def _tr(fr, en):
                    try:
                        return gui.tr(fr, en)
                    except Exception:
                        return fr

                if platform.system() == "Linux":
                    missing = []
                    if not _shutil.which("patchelf"):
                        missing.append("patchelf")
                    if not _shutil.which("objdump"):
                        missing.append("objdump (binutils)")
                    if not (_shutil.which("7z") or _shutil.which("7za")):
                        missing.append("p7zip (7z/7za)")
                    if missing:
                        sdm = SysDependencyManager(parent_widget=gui)
                        pm = sdm.detect_linux_package_manager()
                        if pm:
                            if pm == "apt":
                                packages = ["binutils", "patchelf", "p7zip-full"]
                            elif pm == "dnf":
                                packages = ["binutils", "patchelf", "p7zip"]
                            elif pm == "pacman":
                                packages = ["binutils", "patchelf", "p7zip"]
                            else:
                                packages = ["binutils", "patchelf", "p7zip-full"]
                            try:
                                gui.log.append(
                                    _tr(
                                        "🔧 Dépendances système PyInstaller manquantes: ",
                                        "🔧 Missing PyInstaller system dependencies: ",
                                    )
                                    + ", ".join(missing)
                                )
                            except Exception:
                                pass
                            proc = sdm.install_packages_linux(packages, pm=pm)
                            if proc:
                                try:
                                    gui.log.append(
                                        _tr(
                                            "⏳ Installation des dépendances système en arrière‑plan… Relancez la compilation après l'installation.",
                                            "⏳ Installing system dependencies in background… Relaunch the build after installation.",
                                        )
                                    )
                                except Exception:
                                    pass
                                # Ne pas bloquer l'UI: arrêter le préflight et relancer plus tard
                                return False
                            else:
                                try:
                                    gui.log.append(
                                        _tr(
                                            "⛔ Installation des dépendances système annulée ou non démarrée.",
                                            "⛔ System dependencies installation cancelled or not started.",
                                        )
                                    )
                                except Exception:
                                    pass
                                return False
                        else:
                            try:
                                from PySide6.QtWidgets import QMessageBox

                                QMessageBox.critical(
                                    gui,
                                    _tr(
                                        "Gestionnaire de paquets non détecté",
                                        "Package manager not detected",
                                    ),
                                    _tr(
                                        "Impossible d'installer automatiquement les dépendances système (patchelf, p7zip).",
                                        "Unable to auto-install system dependencies (patchelf, p7zip).",
                                    ),
                                )
                            except Exception:
                                pass
                            return False
            except Exception:
                pass

            vroot = self._resolve_venv_root(gui)
            if not vroot:
                # Demander à la GUI de créer le venv si VenvManager dispo
                vm = getattr(gui, "venv_manager", None)
                if vm and getattr(gui, "workspace_dir", None):
                    vm.create_venv_if_needed(gui.workspace_dir)
                else:
                    try:
                        gui.log.append(
                            gui.tr(
                                "❌ Aucun venv détecté. Créez un venv dans le workspace.",
                                "❌ No venv detected. Create a venv in the workspace.",
                            )
                        )
                    except Exception:
                        pass
                return False
            # Utiliser VenvManager s'il est là, sinon fallback pip
            vm = getattr(gui, "venv_manager", None)
            if vm:
                # Fast non-blocking heuristic; if present, proceed
                if vm.is_tool_installed(vroot, "pyinstaller"):
                    return True
                # Async confirm, then install if missing
                try:
                    gui.log.append(
                        gui.tr(
                            "🔎 Vérification de PyInstaller dans le venv (asynchrone)…",
                            "🔎 Verifying PyInstaller in venv (async)…",
                        )
                    )
                except Exception:
                    pass

                def _on_check(ok: bool):
                    try:
                        if ok:
                            try:
                                gui.log.append(
                                    gui.tr(
                                        "✅ PyInstaller déjà installé",
                                        "✅ PyInstaller already installed",
                                    )
                                )
                            except Exception:
                                pass
                        else:
                            try:
                                gui.log.append(
                                    gui.tr(
                                        "📦 Installation de PyInstaller dans le venv (asynchrone)…",
                                        "📦 Installing PyInstaller in venv (async)…",
                                    )
                                )
                            except Exception:
                                pass
                            vm.ensure_tools_installed(vroot, ["pyinstaller"])
                    except Exception:
                        pass

                try:
                    vm.is_tool_installed_async(vroot, "pyinstaller", _on_check)
                except Exception:
                    try:
                        gui.log.append(
                            gui.tr(
                                "📦 Installation de PyInstaller dans le venv (asynchrone)…",
                                "📦 Installing PyInstaller in venv (async)…",
                            )
                        )
                    except Exception:
                        pass
                    vm.ensure_tools_installed(vroot, ["pyinstaller"])
                return False
            else:
                return self._ensure_tool_with_pip(gui, vroot, "pyinstaller")
        except Exception:
            return True

    def build_command(self, gui, file: str) -> list[str]:
        # Reuse existing logic from gui (compiler.py build_pyinstaller_command)
        return gui.build_pyinstaller_command(file)

    def program_and_args(self, gui, file: str) -> Optional[tuple[str, list[str]]]:
        cmd = self.build_command(gui, file)
        # Resolve pyinstaller binary from venv via VenvManager
        try:
            vm = getattr(gui, "venv_manager", None)
            vroot = vm.resolve_project_venv() if vm else None
            if not vroot:
                gui.log.append(
                    gui.tr(
                        "❌ Venv introuvable pour résoudre pyinstaller.",
                        "❌ Venv not found to resolve pyinstaller.",
                    )
                )
                gui.show_error_dialog(os.path.basename(file))
                return None
            vbin = os.path.join(
                vroot, "Scripts" if platform.system() == "Windows" else "bin"
            )
            pyinstaller_path = os.path.join(
                vbin,
                "pyinstaller" if platform.system() != "Windows" else "pyinstaller.exe",
            )
            if not os.path.isfile(pyinstaller_path):
                gui.log.append(
                    gui.tr(
                        "❌ pyinstaller non trouvé dans le venv : ",
                        "❌ pyinstaller not found in venv: ",
                    )
                    + str(pyinstaller_path)
                )
                gui.show_error_dialog(os.path.basename(file))
                return None
            return pyinstaller_path, cmd[1:]
        except Exception:
            return None



    def environment(self, gui, file: str) -> Optional[dict[str, str]]:
        return None

    def create_tab(self, gui):
        # Reuse existing tab if present (from UI file)
        try:
            from PySide6.QtWidgets import QWidget

            tab = getattr(gui, "tab_pyinstaller", None)
            if tab and isinstance(tab, QWidget):
                return tab, gui.tr("PyInstaller", "PyInstaller")
        except Exception:
            pass
        return None
