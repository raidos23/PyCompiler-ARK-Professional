


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
- shell_run(cmd | list[str], cwd=None, on_output=None, on_error=None, on_finished=None): non-blocking, headless
- run_sudo_shell(cmd_str, password, cwd=None, on_output=None, on_error=None, on_finished=None): non-blocking, headless (Linux)
- open_urls(urls): open URLs in default browser
"""

import platform
import shutil
import webbrowser
from collections.abc import Callable
from typing import Optional, Union

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from .dialogs import ProgressDialog


class SysDependencyManager:
    def __init__(self, parent_widget=None):
        self.parent_widget = parent_widget
        # Register list of system dependency tasks on the parent widget for global coordination
        try:
            if parent_widget is not None and not hasattr(
                parent_widget, "_sysdep_tasks"
            ):
                parent_widget._sysdep_tasks = (
                    []
                )  # list of dicts: {process, dialog, label_fr, label_en}
        except Exception:
            pass

    def _register_task(
        self, proc: QProcess, dlg: ProgressDialog, label_fr: str, label_en: str
    ) -> None:
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
            if self.parent_widget is None or not hasattr(
                self.parent_widget, "_sysdep_tasks"
            ):
                return
            tasks = getattr(self.parent_widget, "_sysdep_tasks")
            for t in list(tasks):
                if t.get("process") is proc:
                    tasks.remove(t)
        except Exception:
            pass

    # ------------- Debug/telemetry helpers -------------
    def set_debug(self, enabled: bool = True) -> None:
        self._debug_enabled = bool(enabled)

    def _dbg(self, message: str) -> None:
        try:
            if not getattr(self, "_debug_enabled", True):
                return
            buf = getattr(self, "_debug_buffer", None)
            if buf is None:
                buf = []
                self._debug_buffer = buf
            line = str(message)
            buf.append(line)
            if len(buf) > 1000:
                del buf[: len(buf) - 1000]
            pw = self.parent_widget
            if pw is not None:
                try:
                    if hasattr(pw, "log_debug") and callable(pw.log_debug):
                        pw.log_debug(line)
                    elif hasattr(pw, "append_debug") and callable(pw.append_debug):
                        pw.append_debug(line)
                    elif hasattr(pw, "logger") and hasattr(pw.logger, "debug"):
                        pw.logger.debug(line)
                    else:
                        print(line)
                except Exception:
                    print(line)
            else:
                print(line)
        except Exception:
            pass

    def get_debug_log(self) -> str:
        try:
            return "\n".join(getattr(self, "_debug_buffer", [])[-1000:])
        except Exception:
            return ""

    # ------------- Generic helpers -------------
    def tr(self, fr: str, en: str) -> str:
        try:
            lang = getattr(self.parent_widget, "current_language", "Français")
            return en if lang == "English" else fr
        except Exception:
            return fr

    def detect_linux_package_manager(self) -> Optional[str]:
        """Detect common Linux package managers: apt, dnf, yum, pacman, zypper."""
        for pm in ("apt", "dnf", "yum", "pacman", "zypper"):
            if shutil.which(pm):
                return pm
        return None

    def ask_sudo_password(self) -> Optional[str]:
        """Ask for sudo password using a masked input dialog."""
        pwd, ok = QInputDialog.getText(
            self.parent_widget,
            self.tr(
                "Mot de passe administrateur requis", "Administrator password required"
            ),
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
    def msg_info(
        self, title_fr: str, title_en: str, body_fr: str, body_en: str
    ) -> None:
        """Show an information message box (no return)."""
        try:
            QMessageBox.information(
                self.parent_widget,
                self.tr(title_fr, title_en),
                self.tr(body_fr, body_en),
            )
        except Exception:
            pass

    def msg_warning(
        self, title_fr: str, title_en: str, body_fr: str, body_en: str
    ) -> None:
        """Show a warning message box (no return)."""
        try:
            QMessageBox.warning(
                self.parent_widget,
                self.tr(title_fr, title_en),
                self.tr(body_fr, body_en),
            )
        except Exception:
            pass

    def msg_error(
        self, title_fr: str, title_en: str, body_fr: str, body_en: str
    ) -> None:
        """Show an error (critical) message box (no return)."""
        try:
            QMessageBox.critical(
                self.parent_widget,
                self.tr(title_fr, title_en),
                self.tr(body_fr, body_en),
            )
        except Exception:
            pass

    def ask_yes_no(
        self,
        title_fr: str,
        title_en: str,
        text_fr: str,
        text_en: str,
        default_yes: bool = True,
    ) -> bool:
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
        self,
        title_fr: str,
        title_en: str,
        label_fr: str,
        label_en: str,
        default: str = "",
        password: bool = False,
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

    def shell_run(
        self,
        cmd: Union[str, list[str]],
        cwd: Optional[str] = None,
        on_output: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int, QProcess.ExitStatus], None]] = None,
    ) -> Optional[QProcess]:
        """
        Non-blocking execution of a command without sudo using QProcess.
        Does not display any dialog and streams output via callbacks.
        Returns the QProcess instance or None on failure.
        """
        try:
            proc = QProcess(self.parent_widget)
            if cwd:
                proc.setWorkingDirectory(cwd)

            if isinstance(cmd, list) and cmd:
                program, args = cmd[0], list(cmd[1:])
                proc.setProgram(program)
                proc.setArguments(args)
            else:
                # Use bash -lc for shell features when a string command is provided
                proc.setProgram("/bin/bash")
                proc.setArguments(["-lc", str(cmd)])

            def _emit_output(p: QProcess, is_error: bool = False):
                try:
                    data = (
                        p.readAllStandardError().data().decode()
                        if is_error
                        else p.readAllStandardOutput().data().decode()
                    )
                    if data:
                        try:
                            self._dbg(
                                ("STDERR: " if is_error else "STDOUT: ") + data.strip()
                            )
                        except Exception:
                            pass
                        if is_error and callable(on_error):
                            on_error(data)
                        elif (not is_error) and callable(on_output):
                            on_output(data)
                except Exception:
                    pass

            def _on_finished(ec: int, es: QProcess.ExitStatus):
                try:
                    if callable(on_finished):
                        on_finished(ec, es)
                finally:
                    self._unregister_task(proc)

            proc.readyReadStandardOutput.connect(lambda p=proc: _emit_output(p, False))
            proc.readyReadStandardError.connect(lambda p=proc: _emit_output(p, True))
            proc.finished.connect(_on_finished)

            # Register task for potential global coordination (dialog=None)
            try:
                self._register_task(proc, None, "commande système", "system command")
            except Exception:
                pass

            try:
                self._dbg(
                    f"shell_run start: program={proc.program()} args={' '.join(proc.arguments())} cwd={cwd or ''}"
                )
            except Exception:
                pass
            proc.start()
            self._last_process = proc
            return proc
        except Exception:
            return None

    def run_sudo_shell(
        self,
        cmd_str: str,
        password: str,
        cwd: Optional[str] = None,
        on_output: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int, QProcess.ExitStatus], None]] = None,
        timeout_s: Optional[int] = None,
    ) -> Optional[QProcess]:
        """
        Non-blocking execution of a sudo-enabled shell command string on Linux using QProcess.
        No dialog is shown. The sudo password is written to stdin when the process starts.
        Streams output via callbacks and returns the QProcess instance or None on failure.
        """
        try:
            if platform.system() != "Linux":
                self.msg_error(
                    "Plateforme non supportée",
                    "Unsupported platform",
                    "Cette opération sudo est supportée uniquement sous Linux.",
                    "This sudo operation is supported on Linux only.",
                )
                return None

            proc = QProcess(self.parent_widget)
            if cwd:
                proc.setWorkingDirectory(cwd)
            proc.setProgram("/bin/bash")
            proc.setArguments(["-lc", cmd_str])

            def _emit_output(p: QProcess, is_error: bool = False):
                try:
                    data = (
                        p.readAllStandardError().data().decode()
                        if is_error
                        else p.readAllStandardOutput().data().decode()
                    )
                    if data:
                        # Auto-respond to sudo password prompts if they reappear
                        try:
                            low = data.lower()
                            if (
                                password
                                and ("password" in low)
                                and (
                                    "sudo" in low
                                    or "[sudo]" in low
                                    or "password for" in low
                                )
                            ):
                                p.write((password + "\n").encode("utf-8"))
                                try:
                                    self._dbg(
                                        "sudo: password prompt detected, password re-sent"
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        try:
                            self._dbg(
                                ("STDERR: " if is_error else "STDOUT: ") + data.strip()
                            )
                        except Exception:
                            pass
                        if is_error and callable(on_error):
                            on_error(data)
                        elif (not is_error) and callable(on_output):
                            on_output(data)
                except Exception:
                    pass

            def _on_started():
                try:
                    if password:
                        proc.write((password + "\n").encode("utf-8"))
                except Exception:
                    pass

            def _on_finished(ec: int, es: QProcess.ExitStatus):
                try:
                    if callable(on_finished):
                        on_finished(ec, es)
                finally:
                    self._unregister_task(proc)

            proc.started.connect(_on_started)
            proc.readyReadStandardOutput.connect(lambda p=proc: _emit_output(p, False))
            proc.readyReadStandardError.connect(lambda p=proc: _emit_output(p, True))
            proc.finished.connect(_on_finished)

            try:
                self._register_task(proc, None, "commande sudo", "sudo command")
            except Exception:
                pass

            # Optional timeout to enforce robustness
            if timeout_s and int(timeout_s) > 0:
                try:
                    timer = QTimer(self.parent_widget)
                    timer.setSingleShot(True)
                    timer.timeout.connect(
                        lambda: (
                            self._dbg(
                                f"sudo shell timeout after {timeout_s}s; killing"
                            ),
                            proc.kill(),
                        )
                    )
                    timer.start(int(timeout_s) * 1000)
                    proc.finished.connect(lambda *_: timer.stop())
                    self._last_timer = timer
                except Exception:
                    pass

            try:
                self._dbg(
                    f"sudo shell start: program={proc.program()} args={' '.join(proc.arguments())} cwd={cwd or ''}"
                )
            except Exception:
                pass
            proc.start()
            self._last_process = proc
            return proc
        except Exception:
            return None

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
            names = ", ".join([p.get("id", "?") for p in packages])
            try:
                self._dbg(f"winget install: {names}")
            except Exception:
                pass
            # Progress dialog
            dlg = ProgressDialog(
                self.tr(
                    "Installation des dépendances Windows",
                    "Installing Windows dependencies",
                ),
                self.parent_widget,
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
                args = [
                    "install",
                    "--id",
                    pkg_id,
                    "-e",
                    "--source",
                    "winget",
                    "--silent",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ]
                if override:
                    args += ["--override", override]
                try:
                    dlg.set_message(
                        self.tr(f"Installation: {pkg_id}", f"Installing: {pkg_id}")
                    )
                except Exception:
                    pass
                proc.setProgram("winget")
                proc.setArguments(args)
                try:
                    self._dbg(f"winget start: id={pkg_id} args={' '.join(args)}")
                except Exception:
                    pass
                proc.start()

            def _on_output(p: QProcess, error: bool = False):
                try:
                    data = (
                        p.readAllStandardError().data().decode()
                        if error
                        else p.readAllStandardOutput().data().decode()
                    )
                    try:
                        self._dbg(
                            ("winget STDERR: " if error else "winget STDOUT: ")
                            + data.strip()
                        )
                    except Exception:
                        pass
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
                        p.readAllStandardError().data().decode()
                        if error
                        else p.readAllStandardOutput().data().decode()
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
            self._register_task(
                proc, dlg, "installation des dépendances", "dependencies installation"
            )
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
        timeout_s: Optional[int] = None,
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
                    "Cette opération sudo est supportée uniquement sous Linux.",
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
                        p.readAllStandardError().data().decode()
                        if error
                        else p.readAllStandardOutput().data().decode()
                    )
                    # Auto-respond to sudo password prompts if they reappear
                    try:
                        low = data.lower()
                        if (
                            password
                            and ("password" in low)
                            and (
                                "sudo" in low
                                or "[sudo]" in low
                                or "password for" in low
                            )
                        ):
                            proc.write((password + "\n").encode("utf-8"))
                            try:
                                self._dbg(
                                    "sudo: password prompt detected (progress), password re-sent"
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        self._dbg(("STDERR: " if error else "STDOUT: ") + data.strip())
                    except Exception:
                        pass
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
            self._register_task(
                proc, dlg, "installation des dépendances", "dependencies installation"
            )

            # Optional timeout to enforce robustness
            if timeout_s and int(timeout_s) > 0:
                try:
                    timer = QTimer(self.parent_widget)
                    timer.setSingleShot(True)
                    timer.timeout.connect(
                        lambda: (
                            self._dbg(
                                f"sudo shell (progress) timeout after {timeout_s}s; killing"
                            ),
                            proc.kill(),
                            dlg.set_message(self.tr("Délai dépassé", "Timed out")),
                        )
                    )
                    timer.start(int(timeout_s) * 1000)
                    proc.finished.connect(lambda *_: timer.stop())
                    self._last_timer = timer
                except Exception:
                    pass

            try:
                self._dbg(
                    f"sudo shell (progress) start: program={proc.program()} args={' '.join(proc.arguments())} cwd={cwd or ''}"
                )
            except Exception:
                pass
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
        self,
        packages: list[str],
        pm: Optional[str] = None,
        password: Optional[str] = None,
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
                    "Impossible de détecter apt/dnf/yum/pacman/zypper.",
                    "Unable to detect apt/dnf/yum/pacman/zypper.",
                )
                return None
            # Auto-consent: proceed without prompting the user
            # (Previously asked via ask_yes_no, now forced to Yes to avoid interruptions)
            try:
                self._dbg(f"linux install pm={pm} packages={packages}")
            except Exception:
                pass
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
            pkgs = " ".join(packages)
            if pm == "apt":
                cmd = (
                    "set -euo pipefail; for i in 1 2 3; do "
                    "sudo -S env DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 update -yq && "
                    'sudo -S env DEBIAN_FRONTEND=noninteractive apt-get -o Dpkg::Options::="--force-confdef" '
                    '-o Dpkg::Options::="--force-confnew" -o Acquire::Retries=3 install -yq --no-install-recommends '
                    + pkgs
                    + " "
                    '&& break || { ec=$?; echo "SYSDEP: apt attempt $i failed (exit=$ec), retrying..."; sleep 5; }; done'
                )
            elif pm == "dnf":
                cmd = (
                    "set -euo pipefail; for i in 1 2 3; do "
                    "sudo -S dnf -y install --setopt=install_weak_deps=False --best --allowerasing "
                    + pkgs
                    + " "
                    '&& break || { ec=$?; echo "SYSDEP: dnf attempt $i failed (exit=$ec), retrying..."; sleep 5; }; done'
                )
            elif pm == "yum":
                cmd = (
                    "set -euo pipefail; for i in 1 2 3; do "
                    "sudo -S yum -y install " + pkgs + " "
                    '&& break || { ec=$?; echo "SYSDEP: yum attempt $i failed (exit=$ec), retrying..."; sleep 5; }; done'
                )
            elif pm == "pacman":
                cmd = (
                    "set -euo pipefail; for i in 1 2 3; do "
                    "sudo -S pacman -Sy --noconfirm && sudo -S pacman -S --noconfirm --needed "
                    + pkgs
                    + " "
                    '&& break || { ec=$?; echo "SYSDEP: pacman attempt $i failed (exit=$ec), retrying..."; sleep 5; }; done'
                )
            else:  # zypper
                cmd = (
                    "set -euo pipefail; for i in 1 2 3; do "
                    "sudo -S zypper --non-interactive --gpg-auto-import-keys --no-gpg-checks install -y "
                    + pkgs
                    + " "
                    '&& break || { ec=$?; echo "SYSDEP: zypper attempt $i failed (exit=$ec), retrying..."; sleep 5; }; done'
                )
            try:
                self._dbg(f"linux install cmd: {cmd}")
            except Exception:
                pass
            return self.run_sudo_shell_with_progress(
                cmd,
                password,
                title_fr="Installation des dépendances système",
                title_en="Installing system dependencies",
                start_msg_fr="Téléchargement/installation...",
                start_msg_en="Downloading/Installing...",
                timeout_s=3600,
            )
        except Exception:
            return None
