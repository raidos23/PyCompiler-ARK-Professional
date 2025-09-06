# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

"""
Thin bridge API between engines and the operating system for system-level interactions.

This module exposes generic helpers only. Engines (Nuitka, PyOxidizer, etc.)
are responsible for their own dependency policy and user interaction logic
(consent dialogs, exact package lists, commands, etc.).

Provided helpers:
- tr(parent, fr, en): simple translation helper leveraging GUI state
- detect_linux_package_manager(): detect apt/dnf/pacman/zypper
- ask_sudo_password(parent): masked input prompt for sudo
- which(cmd): shutil.which wrapper
- shell_run(cmd | str, cwd=None): run command, capture output (no sudo)
- run_sudo_shell(cmd_str, password): run a shell command string with sudo -S (Linux)
- open_urls(urls): open URLs in default browser
"""

import platform
import shutil
import subprocess
import webbrowser
from typing import Optional, Union

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from .dialogs import ProgressDialog


class SysDependencyManager:
    def __init__(self, parent_widget=None):
        self.parent_widget = parent_widget
        # Register list of system dependency tasks on the parent widget for global coordination
        try:
            if parent_widget is not None and not hasattr(parent_widget, "_sysdep_tasks"):
                parent_widget._sysdep_tasks = []  # list of dicts: {process, dialog, label_fr, label_en}
        except Exception:
            pass

    def _register_task(self, proc: QProcess, dlg: ProgressDialog, label_fr: str, label_en: str) -> None:
        try:
            if self.parent_widget is None:
                return
            tasks = getattr(self.parent_widget, "_sysdep_tasks", None)
            if tasks is None:
                tasks = []
                setattr(self.parent_widget, "_sysdep_tasks", tasks)
            tasks.append(
                {
                    "process": proc,
                    "dialog": dlg,
                    "label_fr": label_fr,
                    "label_en": label_en,
                }
            )
        except Exception:
            pass

    def _unregister_task(self, proc: QProcess) -> None:
        try:
            if self.parent_widget is None or not hasattr(self.parent_widget, "_sysdep_tasks"):
                return
            tasks = getattr(self.parent_widget, "_sysdep_tasks")
            for t in list(tasks):
                if t.get("process") is proc:
                    tasks.remove(t)
        except Exception:
            pass

    # ------------- Generic helpers -------------
    def tr(self, fr: str, en: str) -> str:
        try:
            lang = getattr(self.parent_widget, "current_language", "Français")
            return en if lang == "English" else fr
        except Exception:
            return fr

    def detect_linux_package_manager(self) -> Optional[str]:
        """Detect common Linux package managers: apt, dnf, pacman, zypper."""
        for pm in ("apt", "dnf", "pacman", "zypper"):
            if shutil.which(pm):
                return pm
        return None

    def ask_sudo_password(self) -> Optional[str]:
        """Ask for sudo password using a masked input dialog."""
        pwd, ok = QInputDialog.getText(
            self.parent_widget,
            self.tr("Mot de passe administrateur requis", "Administrator password required"),
            self.tr(
                "Pour installer les dépendances, entrez votre mot de passe administrateur :",
                "To install dependencies, enter your administrator password:",
            ),
            QLineEdit.Password,
        )
        if ok and pwd:
            return pwd
        return None

    # ------------- MessageBox helpers -------------
    def msg_info(self, title_fr: str, title_en: str, body_fr: str, body_en: str) -> None:
        """Show an information message box (no return)."""
        try:
            QMessageBox.information(
                self.parent_widget,
                self.tr(title_fr, title_en),
                self.tr(body_fr, body_en),
            )
        except Exception:
            pass

    def msg_warning(self, title_fr: str, title_en: str, body_fr: str, body_en: str) -> None:
        """Show a warning message box (no return)."""
        try:
            QMessageBox.warning(
                self.parent_widget,
                self.tr(title_fr, title_en),
                self.tr(body_fr, body_en),
            )
        except Exception:
            pass

    def msg_error(self, title_fr: str, title_en: str, body_fr: str, body_en: str) -> None:
        """Show an error (critical) message box (no return)."""
        try:
            QMessageBox.critical(
                self.parent_widget,
                self.tr(title_fr, title_en),
                self.tr(body_fr, body_en),
            )
        except Exception:
            pass

    def ask_yes_no(self, title_fr: str, title_en: str, text_fr: str, text_en: str, default_yes: bool = True) -> bool:
        """Ask a Yes/No question. Return True if Yes selected, else False."""
        try:
            msg = QMessageBox(self.parent_widget)
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle(self.tr(title_fr, title_en))
            msg.setText(self.tr(text_fr, text_en))
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes if default_yes else QMessageBox.No)
            return msg.exec() == QMessageBox.Yes
        except Exception:
            return False

    def prompt_text(
        self, title_fr: str, title_en: str, label_fr: str, label_en: str, default: str = "", password: bool = False
    ) -> tuple[Optional[str], bool]:
        """Prompt a text input. If password=True, mask input. Return (value|None, ok)."""
        try:
            echo = QLineEdit.Password if password else QLineEdit.Normal
            val, ok = QInputDialog.getText(
                self.parent_widget,
                self.tr(title_fr, title_en),
                self.tr(label_fr, label_en),
                echo,
                default,
            )
            return (val if ok else None), bool(ok)
        except Exception:
            return None, False

    def which(self, cmd: str) -> Optional[str]:
        """Wrapper around shutil.which."""
        return shutil.which(cmd)

    def shell_run(self, cmd: Union[str, list[str]], cwd: Optional[str] = None) -> tuple[int, str, str]:
        """Run a command (no sudo). Returns (rc, stdout, stderr)."""
        try:
            if isinstance(cmd, list):
                proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
            else:
                proc = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
            return proc.returncode, proc.stdout, proc.stderr
        except Exception as e:
            return 1, "", str(e)

    def run_sudo_shell(self, cmd_str: str, password: str) -> tuple[int, str, str]:
        """
        Run a shell command string that expects sudo -S on stdin. Linux only.
        Returns (rc, stdout, stderr).
        """
        try:
            proc = subprocess.run(
                cmd_str,
                shell=True,
                input=(password or "") + "\n",
                encoding="utf-8",
                capture_output=True,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except Exception as e:
            return 1, "", str(e)

    def open_urls(self, urls: list[str]) -> None:
        for u in urls or []:
            try:
                webbrowser.open(u)
            except Exception:
                pass

    # ------------- Windows package installs (winget) -------------
    def detect_windows_package_manager(self) -> Optional[str]:
        """Detect winget (preferred) or choco on Windows."""
        try:
            if platform.system() != "Windows":
                return None
            if shutil.which("winget"):
                return "winget"
            if shutil.which("choco"):
                return "choco"
        except Exception:
            return None
        return None

    def install_packages_windows(self, packages: list[dict]) -> Optional[QProcess]:
        """
        Install Windows packages via winget with a progress dialog.
        packages: list of dicts with keys:
          - id: winget package id (e.g., 'Microsoft.VisualStudio.2022.BuildTools')
          - override: optional string for --override parameters
        Returns the first QProcess started (installation is chained), or None on failure/cancel.
        """
        try:
            if platform.system() != "Windows":
                self.msg_error(
                    "Plateforme non supportée",
                    "Unsupported platform",
                    "L'installation automatisée via winget est disponible uniquement sous Windows.",
                    "Automated install via winget is available on Windows only.",
                )
                return None
            if not packages:
                return None
            pm = self.detect_windows_package_manager()
            if pm != "winget":
                # Fallback: open official pages if winget unavailable
                self.msg_warning(
                    "Gestionnaire indisponible",
                    "Manager unavailable",
                    "winget est indisponible. L'installation guidée sera proposée.",
                    "winget is unavailable. Guided installation will be proposed.",
                )
                return None
            # Consent
            names = ", ".join([p.get("id", "?") for p in packages])
            if not self.ask_yes_no(
                "Installer dépendances Windows",
                "Install Windows dependencies",
                f"Installation via winget: {names}. Continuer ?",
                f"Install via winget: {names}. Proceed?",
                True,
            ):
                return None
            # Progress dialog
            dlg = ProgressDialog(
                self.tr("Installation des dépendances Windows", "Installing Windows dependencies"), self.parent_widget
            )
            dlg.set_message(self.tr("Préparation…", "Preparing…"))
            dlg.progress.setRange(0, 0)
            dlg.show()
            queue = list(packages)
            proc = QProcess(self.parent_widget)

            def _start_next():
                if not queue:
                    try:
                        dlg.close()
                    except Exception:
                        pass
                    self._unregister_task(proc)
                    return
                pkg = queue.pop(0)
                pkg_id = str(pkg.get("id", "")).strip()
                override = str(pkg.get("override", "")).strip()
                if not pkg_id:
                    _start_next()
                    return
                args = ["install", "--id", pkg_id, "-e", "--source", "winget", "--silent"]
                if override:
                    args += ["--override", override]
                try:
                    dlg.set_message(self.tr(f"Installation: {pkg_id}", f"Installing: {pkg_id}"))
                except Exception:
                    pass
                proc.setProgram("winget")
                proc.setArguments(args)
                proc.start()

            def _on_output(p: QProcess, error: bool = False):
                try:
                    data = (
                        p.readAllStandardError().data().decode() if error else p.readAllStandardOutput().data().decode()
                    )
                    lines = [ln for ln in data.strip().splitlines() if ln.strip()]
                    if lines:
                        dlg.set_message(lines[-1][:200])
                except Exception:
                    pass

            def _on_finished(_ec, _es):
                _start_next()

            proc.readyReadStandardOutput.connect(lambda p=proc: _on_output(p, False))
            proc.readyReadStandardError.connect(lambda p=proc: _on_output(p, True))
            proc.finished.connect(_on_finished)
            # register task and kick off
            self._register_task(proc, dlg, "installation winget", "winget install")
            _start_next()
            self._last_progress_dialog = dlg
            self._last_process = proc
            return proc
        except Exception:
            return None

    # ------------- Progress helpers for system installs -------------
    def start_process_with_progress(
        self,
        program: str,
        args: list[str] | None = None,
        cwd: Optional[str] = None,
        title_fr: str = "Installation des dépendances système",
        title_en: str = "Installing system dependencies",
        start_msg_fr: str = "Démarrage...",
        start_msg_en: str = "Starting...",
    ) -> Optional[QProcess]:
        """
        Lance un processus avec une boîte de progression indéterminée.
        Retourne l'objet QProcess (non bloquant) ou None en cas d'échec.
        Le dialogue se ferme automatiquement à la fin du processus.
        """
        try:
            dlg = ProgressDialog(self.tr(title_fr, title_en), self.parent_widget)
            dlg.set_message(self.tr(start_msg_fr, start_msg_en))
            dlg.progress.setRange(0, 0)  # indéterminé
            dlg.show()
            proc = QProcess(self.parent_widget)
            if cwd:
                proc.setWorkingDirectory(cwd)
            proc.setProgram(program)
            proc.setArguments(list(args or []))

            # Mise à jour du message avec la dernière ligne reçue
            def _on_output(p: QProcess, error: bool = False):
                try:
                    data = (
                        p.readAllStandardError().data().decode() if error else p.readAllStandardOutput().data().decode()
                    )
                    lines = [ln for ln in data.strip().splitlines() if ln.strip()]
                    if lines:
                        dlg.set_message(lines[-1])
                except Exception:
                    pass

            proc.readyReadStandardOutput.connect(lambda p=proc: _on_output(p, False))
            proc.readyReadStandardError.connect(lambda p=proc: _on_output(p, True))

            def _on_finished_wrapper(_ec, _es):
                try:
                    dlg.close()
                except Exception:
                    pass
                finally:
                    self._unregister_task(proc)

            proc.finished.connect(_on_finished_wrapper)
            # Register task for global coordination (quit handling)
            self._register_task(proc, dlg, "installation des dépendances", "dependencies installation")
            proc.start()
            # Conserver des refs sur l'instance pour éviter la GC
            self._last_progress_dialog = dlg
            self._last_process = proc
            return proc
        except Exception:
            try:
                # En cas d'échec, fermer la boîte si elle existe
                if getattr(self, "_last_progress_dialog", None):
                    self._last_progress_dialog.close()
            except Exception:
                pass
            return None

    def run_sudo_shell_with_progress(
        self,
        cmd_str: str,
        password: str,
        cwd: Optional[str] = None,
        title_fr: str = "Installation des dépendances système",
        title_en: str = "Installing system dependencies",
        start_msg_fr: str = "Démarrage...",
        start_msg_en: str = "Starting...",
    ) -> Optional[QProcess]:
        """
        Exécute une commande shell (Linux) qui attend un sudo -S sur stdin, avec boîte de progression indéterminée.
        Retourne QProcess (non bloquant). Le mot de passe est écrit sur stdin au démarrage.
        """
        try:
            if platform.system() != "Linux":
                self.msg_error(
                    "Plateforme non supportée",
                    "Unsupported platform",
                    "Cette op��ration sudo est supportée uniquement sous Linux.",
                    "This sudo operation is supported on Linux only.",
                )
                return None
            dlg = ProgressDialog(self.tr(title_fr, title_en), self.parent_widget)
            dlg.set_message(self.tr(start_msg_fr, start_msg_en))
            dlg.progress.setRange(0, 0)
            dlg.show()
            proc = QProcess(self.parent_widget)
            if cwd:
                proc.setWorkingDirectory(cwd)
            # Utiliser bash -lc pour exécuter la chaîne
            proc.setProgram("/bin/bash")
            proc.setArguments(["-lc", cmd_str])

            # maj message sur sortie
            def _on_output(p: QProcess, error: bool = False):
                try:
                    data = (
                        p.readAllStandardError().data().decode() if error else p.readAllStandardOutput().data().decode()
                    )
                    lines = [ln for ln in data.strip().splitlines() if ln.strip()]
                    if lines:
                        dlg.set_message(lines[-1])
                except Exception:
                    pass

            def _on_started():
                try:
                    if password:
                        proc.write((password + "\n").encode("utf-8"))
                except Exception:
                    pass

            proc.started.connect(_on_started)
            proc.readyReadStandardOutput.connect(lambda p=proc: _on_output(p, False))
            proc.readyReadStandardError.connect(lambda p=proc: _on_output(p, True))

            def _on_finished_wrapper(_ec, _es):
                try:
                    dlg.close()
                except Exception:
                    pass
                finally:
                    self._unregister_task(proc)

            proc.finished.connect(_on_finished_wrapper)
            # Register task for global coordination (quit handling)
            self._register_task(proc, dlg, "installation des dépendances", "dependencies installation")
            proc.start()
            self._last_progress_dialog = dlg
            self._last_process = proc
            return proc
        except Exception:
            try:
                if getattr(self, "_last_progress_dialog", None):
                    self._last_progress_dialog.close()
            except Exception:
                pass
            return None

    def install_packages_linux(
        self, packages: list[str], pm: Optional[str] = None, password: Optional[str] = None
    ) -> Optional[QProcess]:
        """
        Helper haut-niveau: demande consentement + mot de passe (si absent),
        construit la commande selon le gestionnaire et lance l'installation avec une
        boîte de progression indéterminée. Retourne QProcess (non bloquant) ou None.
        """
        try:
            if platform.system() != "Linux":
                self.msg_error(
                    "Plateforme non supportée",
                    "Unsupported platform",
                    "L'installation de paquets système automatisée est disponible uniquement sous Linux.",
                    "Automated system package install is available on Linux only.",
                )
                return None
            if not packages:
                return None
            pm = pm or self.detect_linux_package_manager()
            if not pm:
                self.msg_error(
                    "Gestionnaire non détecté",
                    "Package manager not detected",
                    "Impossible de détecter apt/dnf/pacman/zypper.",
                    "Unable to detect apt/dnf/pacman/zypper.",
                )
                return None
            text_fr = "Le moteur requiert l'installation de: {}. Continuer ?".format(", ".join(packages))
            text_en = "The engine requires installing: {}. Proceed?".format(", ".join(packages))
            if not self.ask_yes_no(
                "Installer dépendances système", "Install system dependencies", text_fr, text_en, True
            ):
                return None
            if password is None:
                password = self.ask_sudo_password() or ""
                if not password:
                    self.msg_warning(
                        "Mot de passe requis",
                        "Password required",
                        "Aucun mot de passe fourni. Installation annulée.",
                        "No password provided. Installation cancelled.",
                    )
                    return None
            if pm == "apt":
                cmd = "sudo -S apt update && sudo -S apt install -y " + " ".join(packages)
            elif pm == "dnf":
                cmd = "sudo -S dnf install -y " + " ".join(packages)
            elif pm == "pacman":
                cmd = "sudo -S pacman -Sy " + " ".join(packages)
            else:  # zypper
                cmd = "sudo -S zypper install -y " + " ".join(packages)
            return self.run_sudo_shell_with_progress(
                cmd,
                password,
                title_fr="Installation des dépendances système",
                title_en="Installing system dependencies",
                start_msg_fr="Téléchargement/installation...",
                start_msg_en="Downloading/Installing...",
            )
        except Exception:
            return None
