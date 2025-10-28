# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

import hashlib
import os
import platform
import shutil
import sys

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .dialogs import ProgressDialog

class VenvManager:
    """
    Encapsulates all virtual environment (venv) related operations for the GUI.

    Responsibilities:
    - Manual venv selection (updates parent UI label and internal path)
    - Create venv if missing
    - Check/install tools in an existing venv
    - Install project requirements.txt
    - Report/terminate active background tasks related to venv operations

    The class uses the parent QWidget to own QProcess instances and for logging/UI.
    """

    def __init__(self, parent_widget):
        self.parent = parent_widget
        # QProcess references for graceful termination
        self._venv_create_process = None
        self._venv_check_process = None
        self._venv_check_install_process = None
        self._req_install_process = None
        # Marker for requirements checksum to avoid redundant installs
        self._req_marker_path = None
        self._req_marker_hash = None
        # State for pip three-phase (ensurepip -> upgrade -> install)
        self._pip_phase = None  # 'ensurepip' | 'upgrade' | 'install'
        self._venv_python_exe = None
        self._req_path = None

        # State for ongoing operations
        self._venv_progress_lines = 0
        self._pip_progress_lines = 0

        # For tool check/installation
        self._venv_check_pkgs = []
        self._venv_check_index = 0
        self._venv_check_pip_exe = None
        self._venv_check_path = None

        # For fresh venv install flow (no longer used for tool installs)

        # Progress dialogs
        self.venv_progress_dialog = None
        self.venv_check_progress = None
        self.progress_dialog = None

        # Internal timers to enforce timeouts on background processes
        self._proc_timers: list[QTimer] = []
    # ---------- Public helpers for engines ----------
    def resolve_project_venv(self) -> str | None:
        """Resolve the venv root to use based on manual selection or workspace.
        Prefers an existing .venv over venv; if none exists, returns the default path (.venv).
        """
        try:
            manual = getattr(self.parent, "venv_path_manuel", None)
            if manual:
                base = os.path.abspath(manual)
                return base
            if getattr(self.parent, "workspace_dir", None):
                base = os.path.abspath(self.parent.workspace_dir)
                existing, default_path = self._detect_venv_in(base)
                return existing or default_path
        except Exception:
            return None
        return None

    def pip_path(self, venv_root: str) -> str:
        return os.path.join(
            venv_root, "Scripts" if platform.system() == "Windows" else "bin", "pip"
        )

    def python_path(self, venv_root: str) -> str:
        base = os.path.join(
            venv_root, "Scripts" if platform.system() == "Windows" else "bin"
        )
        if platform.system() == "Windows":
            cand = os.path.join(base, "python.exe")
            return cand
        # Linux/macOS: prefer 'python', fallback to 'python3'
        cand1 = os.path.join(base, "python")
        cand2 = os.path.join(base, "python3")
        return cand1 if os.path.isfile(cand1) else cand2

    def has_tool_binary(self, venv_root: str, tool: str) -> bool:
        """Non-blocking heuristic check: detect console script/binary inside the venv.
        This avoids spawning subprocesses and keeps UI fully responsive.
        """
        try:
            bindir = os.path.join(
                venv_root, "Scripts" if platform.system() == "Windows" else "bin"
            )
            if not os.path.isdir(bindir):
                return False
            names: list[str] = []
            t = tool.strip().lower()
            if t == "pyinstaller":
                names = ["pyinstaller", "pyinstaller.exe", "pyinstaller-script.py"]
            elif t == "nuitka":
                names = ["nuitka", "nuitka3", "nuitka.exe", "nuitka-script.py"]
            else:
                # generic: try tool, tool.exe, and tool-script.py
                names = [t, f"{t}.exe", f"{t}-script.py"]
            for n in names:
                p = os.path.join(bindir, n)
                if os.path.isfile(p):
                    try:
                        return os.access(p, os.X_OK) or p.endswith(".py")
                    except Exception:
                        return True
            return False
        except Exception:
            return False

    def is_tool_installed(self, venv_root: str, tool: str) -> bool:
        """Non-blocking check for tool presence in venv.
        Uses has_tool_binary() only (no subprocess run). If uncertain, returns False
        so that callers can trigger the asynchronous ensure_tools_installed() flow.
        """
        return self.has_tool_binary(venv_root, tool)

    def is_tool_installed_async(self, venv_root: str, tool: str, callback) -> None:
        """Asynchronous check using 'pip show <tool>' via QProcess, then callback(bool).
        Safe for UI: does not block. On any error, returns False.
        """
        try:
            pip_exe = self.pip_path(venv_root)
            if not pip_exe or not os.path.isfile(pip_exe):
                callback(False)
                return
            proc = QProcess(self.parent)

            def _done(code, _status):
                try:
                    callback(code == 0)
                except Exception:
                    pass
            proc.finished.connect(_done)
            proc.setProgram(pip_exe)
            proc.setArguments(["show", tool])
            proc.setWorkingDirectory(venv_root)
            proc.start()
        except Exception:
            try:
                callback(False)
            except Exception:
                pass

    def ensure_tools_installed(self, venv_root: str, tools: list[str]) -> None:
        """Asynchronously check/install the provided tools list with progress dialog."""
        try:
            self._venv_check_pkgs = list(tools)
            self._venv_check_index = 0
            self._venv_check_pip_exe = self.pip_path(venv_root)
            self._venv_check_path = venv_root
            self.venv_check_progress = ProgressDialog(
                "Vérification du venv", self.parent
            )
            self.venv_check_progress.set_message(f"Vérification de {tools[0]}...")
            self.venv_check_progress.set_progress(0, len(tools))
            self.venv_check_progress.show()
            self._check_next_venv_pkg()
        except Exception as e:
            self._safe_log(f"❌ Erreur ensure_tools_installed: {e}")
    # ---------- Utility ----------
    def _safe_log(self, text: str):
        try:
            if hasattr(self.parent, "_safe_log"):
                self.parent._safe_log(text)
                return
        except Exception:
            pass
        try:
            if hasattr(self.parent, "log") and self.parent.log:
                self.parent.log.append(text)
            else:
                print(text)
        except Exception:
            try:
                print(text)
            except Exception:
                pass

    def _prompt_recreate_invalid_venv(self, venv_root: str, reason: str) -> bool:
        """Show an English message box explaining the invalid venv and propose deletion/recreation.
        Returns True if user accepted to recreate, False otherwise.
        """
        try:
            title = "Environnement virtuel invalide / Invalid virtual environment"
            folder = os.path.basename(os.path.normpath(venv_root))
            msg = (
                "L'environnement virtuel du workspace est invalide :\n"
                f"- {reason}\n\n"
                f"Voulez-vous supprimer le dossier '{folder}' et le recréer ?\n\n"
                "The workspace virtual environment is invalid:\n"
                f"- {reason}\n\n"
                f"Do you want to delete the '{folder}' folder and recreate it?"
            )
            reply = QMessageBox.question(
                self.parent,
                title,
                msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                try:
                    shutil.rmtree(venv_root)
                    self._safe_log(f"🗑️ Deleted invalid venv: {venv_root}")
                except Exception as e:
                    try:
                        QMessageBox.critical(
                            self.parent,
                            title,
                            f"Échec suppression venv / Failed to delete venv: {e}",
                        )
                    except Exception:
                        pass
                    return False
                # Recreate fresh venv under the workspace
                try:
                    workspace_dir = os.path.dirname(venv_root)
                    self.create_venv_if_needed(workspace_dir)
                    return True
                except Exception as e:
                    try:
                        QMessageBox.critical(
                            self.parent,
                            title,
                            f"Échec de recréation du venv / Failed to recreate venv: {e}",
                        )
                    except Exception:
                        pass
                    return False
            return False
        except Exception:
            return False
    # ---------- Venv validation ----------
    def _is_within(self, path: str, root: str) -> bool:
        try:
            rp = os.path.realpath(path)
            rr = os.path.realpath(root)
            return os.path.commonpath([rp, rr]) == rr
        except Exception:
            return False

    def validate_venv_strict(self, venv_root: str) -> tuple[bool, str]:
        """Validation stricte d'un venv.
        Retourne (ok, raison_si_ko).
        Règles:
          - Dossier existant
          - pyvenv.cfg présent
          - Scripts/python.exe (Windows) ou bin/python[3] (POSIX) présent
          - include-system-site-packages=false (refus si true)
          - pyvenv.cfg, dossier Scripts/bin et exécutable Python doivent rester confinés dans le venv (pas de liens sortants)
        """
        try:
            if not venv_root or not os.path.isdir(venv_root):
                return False, "Chemin invalide (dossier manquant)"
            cfg = os.path.join(venv_root, "pyvenv.cfg")
            if not os.path.isfile(cfg):
                return False, "pyvenv.cfg introuvable"
            bindir = "Scripts" if platform.system() == "Windows" else "bin"
            bpath = os.path.join(venv_root, bindir)
            if not os.path.isdir(bpath):
                return False, f"Dossier {bindir}/ introuvable"
            if platform.system() == "Windows":
                pyexe = os.path.join(bpath, "python.exe")
                if not os.path.isfile(pyexe):
                    return False, "python.exe introuvable dans Scripts/"
            else:
                cand1 = os.path.join(bpath, "python")
                cand2 = os.path.join(bpath, "python3")
                if not (os.path.isfile(cand1) or os.path.isfile(cand2)):
                    return False, "python ou python3 introuvable dans bin/"
                pyexe = cand1 if os.path.isfile(cand1) else cand2
            # Politique pyvenv.cfg: include-system-site-packages doit être false
            try:
                with open(cfg, encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                for line in text.splitlines():
                    if "include-system-site-packages" in line.lower():
                        _, _, v = line.partition("=")
                        if str(v).strip().lower() in ("1", "true", "yes"):
                            return False, "include-system-site-packages=true (refusé)"
                        break
            except Exception:
                pass
            # Confinement: pyvenv.cfg et le dossier bin/Scripts doivent rester dans le venv.
            # L'exécutable Python peut être un lien symbolique hors venv selon la plateforme;
            # la vérification de liaison (verify_venv_binding) garantira l'isolation effective.
            for p in (cfg, bpath):
                if not self._is_within(p, venv_root):
                    return (
                        False,
                        f"Lien/symlink sortant du venv: {os.path.relpath(p, venv_root)}",
                    )
            return True, ""
        except Exception as e:
            return False, f"Erreur validation venv: {e}"

    def is_valid_venv(self, venv_root: str) -> bool:
        ok, _ = self.validate_venv_strict(venv_root)
        return ok
    # ---------- Manual selection ----------
    def select_venv_manually(self):
        folder = QFileDialog.getExistingDirectory(
            self.parent, "Choisir un dossier venv", ""
        )
        if folder:
            path = os.path.abspath(folder)
            ok, reason = self.validate_venv_strict(path)
            if ok:
                self.parent.venv_path_manuel = path
                if hasattr(self.parent, "venv_label") and self.parent.venv_label:
                    self.parent.venv_label.setText(f"Venv sélectionné : {path}")
                self._safe_log(f"✅ Venv valide sélectionné: {path}")
            else:
                self._safe_log(f"❌ Venv refusé: {reason}")
                self.parent.venv_path_manuel = None
                if hasattr(self.parent, "venv_label") and self.parent.venv_label:
                    self.parent.venv_label.setText("Venv sélectionné : Aucun")
        else:
            self.parent.venv_path_manuel = None
            if hasattr(self.parent, "venv_label") and self.parent.venv_label:
                self.parent.venv_label.setText("Venv sélectionné : Aucun")
    # ---------- Existing venv: check and install tools ----------
    def check_tools_in_venv(self, venv_path: str):
        try:
            ok, reason = self.validate_venv_strict(venv_path)
            if not ok:
                self._safe_log(f"❌ Invalid venv: {reason}")
                # Offer to delete and recreate
                self._prompt_recreate_invalid_venv(venv_path, reason)
                return

            # Vérification asynchrone de la liaison python/pip → venv
            def _after_binding(ok_bind: bool):
                if not ok_bind:
                    self._safe_log(
                        "❌ Invalid venv binding: python/pip do not point to the selected venv."
                    )
                    self._prompt_recreate_invalid_venv(
                        venv_path, "Python/pip do not point to the selected venv"
                    )
                    return
                pip_exe = os.path.join(
                    venv_path,
                    "Scripts" if platform.system() == "Windows" else "bin",
                    "pip",
                )
                self._venv_check_pkgs = ["pyinstaller", "nuitka"]
                self._venv_check_index = 0
                self._venv_check_pip_exe = pip_exe
                self._venv_check_path = venv_path
                self.venv_check_progress = ProgressDialog(
                    "Vérification du venv", self.parent
                )
                self.venv_check_progress.set_message("Vérification de PyInstaller...")
                self.venv_check_progress.set_progress(0, len(self._venv_check_pkgs))
                self.venv_check_progress.show()
                self._check_next_venv_pkg()
            self._verify_venv_binding_async(venv_path, _after_binding)
        except Exception as e:
            self._safe_log(f"❌ Erreur lors de la vérification du venv: {e}")

    def _check_next_venv_pkg(self):
        if self._venv_check_index >= len(self._venv_check_pkgs):
            try:
                self.venv_check_progress.set_message("Vérification terminée.")
                total = (
                    len(self._venv_check_pkgs)
                    if hasattr(self, "_venv_check_pkgs") and self._venv_check_pkgs
                    else 0
                )
                self.venv_check_progress.set_progress(total, total)
                self.venv_check_progress.close()
            except Exception:
                pass
            # Installer les dépendances du projet si un requirements.txt est présent
            try:
                if getattr(self.parent, "workspace_dir", None):
                    self.install_requirements_if_needed(self.parent.workspace_dir)
            except Exception:
                pass
            return
        pkg = self._venv_check_pkgs[self._venv_check_index]
        process = QProcess(self.parent)
        self._venv_check_process = process
        process.setProgram(self._venv_check_pip_exe)
        process.setArguments(["show", pkg])
        process.setWorkingDirectory(self._venv_check_path)
        process.finished.connect(
            lambda code, status: self._on_venv_pkg_checked(process, code, status, pkg)
        )
        process.start()
        # Safety timeout for pip show (30s)
        self._arm_process_timeout(process, 30_000, f"pip show {pkg}")

    def _on_venv_pkg_checked(self, process, code, status, pkg):
        if getattr(self.parent, "_closing", False):
            return
        if code == 0:
            self._safe_log(f"✅ {pkg} déjà installé dans le venv.")
            self._venv_check_index += 1
            try:
                next_label = (
                    self._venv_check_pkgs[self._venv_check_index]
                    if self._venv_check_index < len(self._venv_check_pkgs)
                    else ""
                )
                self.venv_check_progress.set_message(f"Vérification de {next_label}...")
                self.venv_check_progress.set_progress(
                    self._venv_check_index, len(self._venv_check_pkgs)
                )
            except Exception:
                pass
            self._check_next_venv_pkg()
        else:
            self._safe_log(f"📦 Installation automatique de {pkg} dans le venv...")
            try:
                self.venv_check_progress.set_message(f"Installation de {pkg}...")
                self.venv_check_progress.progress.setRange(0, 0)
            except Exception:
                pass
            process2 = QProcess(self.parent)
            self._venv_check_install_process = process2
            process2.setProgram(self._venv_check_pip_exe)
            process2.setArguments(["install", pkg])
            process2.setWorkingDirectory(self._venv_check_path)
            process2.readyReadStandardOutput.connect(
                lambda: self._on_venv_check_output(process2)
            )
            process2.readyReadStandardError.connect(
                lambda: self._on_venv_check_output(process2, error=True)
            )
            process2.finished.connect(
                lambda code2, status2: self._on_venv_pkg_installed(
                    process2, code2, status2, pkg
                )
            )
            process2.start()
            # Safety timeout for pip install of single tool (10 min)
            self._arm_process_timeout(process2, 600_000, f"pip install {pkg}")

    def _on_venv_check_output(self, process, error=False):
        if getattr(self.parent, "_closing", False):
            return
        data = (
            process.readAllStandardError().data().decode()
            if error
            else process.readAllStandardOutput().data().decode()
        )
        try:
            if self.venv_check_progress:
                lines = data.strip().splitlines()
                if lines:
                    self.venv_check_progress.set_message(lines[-1])
        except Exception:
            pass
        self._safe_log(data)

    def verify_venv_binding(self, venv_root: str) -> bool:
        """Conservation de la version synchrone pour compat interne (éviter blocages ailleurs)."""
        try:
            import subprocess

            vpython = self.python_path(venv_root)
            if not os.path.isfile(vpython):
                return False
            cp = subprocess.run(
                [vpython, "-c", "import sys, os; print(os.path.realpath(sys.prefix))"],
                capture_output=True,
                text=True,
            )
            if cp.returncode != 0:
                return False
            sys_prefix = os.path.realpath(cp.stdout.strip())
            if not self._is_within(sys_prefix, venv_root):
                return False
            vpip = self.pip_path(venv_root)
            if not os.path.isfile(vpip):
                return False
            cp2 = subprocess.run([vpip, "--version"], capture_output=True, text=True)
            if cp2.returncode != 0:
                return False
            import re as _re

            m = _re.search(r" from (.+?) \(python ", cp2.stdout.strip())
            if not m:
                return False
            site_path = os.path.realpath(m.group(1))
            if not self._is_within(site_path, venv_root):
                return False
            return True
        except Exception:
            return False

    def _verify_venv_binding_async(self, venv_root: str, callback):
        """Vérifie de manière asynchrone que python et pip du venv pointent bien vers ce venv, puis appelle callback(bool)."""
        try:
            vpython = self.python_path(venv_root)
            if not os.path.isfile(vpython):
                callback(False)
                return
            # Étape 1: vérifier sys.prefix
            p1 = QProcess(self.parent)

            def _p1_finished(code, _status):
                try:
                    if code != 0:
                        callback(False)
                        return
                    out = p1.readAllStandardOutput().data().decode().strip()
                    sys_prefix = os.path.realpath(out)
                    if not self._is_within(sys_prefix, venv_root):
                        callback(False)
                        return
                    # Étape 2: vérifier pip --version et site-path
                    vpip = self.pip_path(venv_root)
                    if not os.path.isfile(vpip):
                        callback(False)
                        return
                    p2 = QProcess(self.parent)

                    def _p2_finished(code2, _status2):
                        try:
                            if code2 != 0:
                                callback(False)
                                return
                            text = p2.readAllStandardOutput().data().decode().strip()
                            import re as _re

                            m = _re.search(r" from (.+?) \(python ", text)
                            if not m:
                                callback(False)
                                return
                            site_path = os.path.realpath(m.group(1))
                            callback(self._is_within(site_path, venv_root))
                        except Exception:
                            callback(False)
                    p2.finished.connect(_p2_finished)
                    p2.setProgram(vpip)
                    p2.setArguments(["--version"])
                    p2.setWorkingDirectory(venv_root)
                    p2.start()
                except Exception:
                    callback(False)
            p1.finished.connect(_p1_finished)
            p1.setProgram(vpython)
            p1.setArguments(
                ["-c", "import sys, os; print(os.path.realpath(sys.prefix))"]
            )
            p1.setWorkingDirectory(venv_root)
            p1.start()
        except Exception:
            callback(False)

    def _arm_process_timeout(self, process: QProcess, timeout_ms: int, label: str):
        """Arm a one-shot timer to kill a long-running process and keep UI responsive."""
        try:
            if timeout_ms and timeout_ms > 0:
                t = QTimer(self.parent)
                t.setSingleShot(True)

                def _on_timeout():
                    try:
                        if process.state() != QProcess.NotRunning:
                            self._safe_log(
                                f"⏱️ Timeout exceeded for {label} ({timeout_ms} ms). Killing process…"
                            )
                            process.kill()
                    except Exception:
                        pass
                t.timeout.connect(_on_timeout)
                t.start(timeout_ms)
                # keep reference to avoid GC
                self._proc_timers.append(t)

                # also attach to process so timer can be cleared if process finishes earlier
                def _clear_timer(*_args):
                    try:
                        if t.isActive():
                            t.stop()
                    except Exception:
                        pass
                process.finished.connect(_clear_timer)
        except Exception:
            pass

    def _detect_venv_in(self, base: str) -> tuple[str | None, str]:
        """Return (existing_venv_path_or_None, default_venv_path). Prefers .venv if present, otherwise venv. Default path is .venv."""
        try:
            base = os.path.abspath(base)
        except Exception:
            pass
        p_dot = os.path.join(base, ".venv")
        p_std = os.path.join(base, "venv")
        existing = (
            p_dot if os.path.isdir(p_dot) else (p_std if os.path.isdir(p_std) else None)
        )
        default = p_dot
        return existing, default

    def _on_venv_pkg_installed(self, process, code, status, pkg):
        if getattr(self.parent, "_closing", False):
            return
        if code == 0:
            self._safe_log(f"✅ {pkg} installé dans le venv.")
        else:
            self._safe_log(f"❌ Erreur installation {pkg} (code {code})")
        self._venv_check_index += 1
        try:
            self.venv_check_progress.progress.setRange(0, len(self._venv_check_pkgs))
            self.venv_check_progress.set_progress(
                self._venv_check_index, len(self._venv_check_pkgs)
            )
        except Exception:
            pass
        self._check_next_venv_pkg()
    # ---------- Create venv if needed ----------
    def create_venv_if_needed(self, path: str):
        existing, default_path = self._detect_venv_in(path)
        venv_path = existing or default_path
        if existing:
            # Validate existing venv; if invalid, propose deletion/recreation
            ok, reason = self.validate_venv_strict(venv_path)
            if not ok:
                self._safe_log(f"❌ Invalid venv detected: {reason}")
                recreated = self._prompt_recreate_invalid_venv(venv_path, reason)
                if not recreated:
                    return
            else:
                return
        self._safe_log("🔧 Aucun venv trouvé, création automatique...")
        try:
            # Recherche d'un python embarqué à côté de l'exécutable
            python_candidate = None
            exe_dir = os.path.dirname(sys.executable)
            # Windows: python.exe, Linux/Mac: python3 ou python
            candidates = [
                os.path.join(exe_dir, "python.exe"),
                os.path.join(exe_dir, "python3"),
                os.path.join(exe_dir, "python"),
                os.path.join(exe_dir, "python_embedded", "python.exe"),
                os.path.join(exe_dir, "python_embedded", "python3"),
                os.path.join(exe_dir, "python_embedded", "python"),
            ]
            # Recherche également les interpréteurs système disponibles dans le PATH
            path_candidates = []
            try:
                if platform.system() == "Windows":
                    w = shutil.which("py")
                    if w:
                        path_candidates.append(w)
                for name in ("python3", "python"):
                    w = shutil.which(name)
                    if w:
                        path_candidates.append(w)
            except Exception:
                pass
            for c in path_candidates:
                if c not in candidates:
                    candidates.append(c)
            for c in candidates:
                if os.path.isfile(c):
                    python_candidate = c
                    break
            if not python_candidate:
                python_candidate = sys.executable
            # Journalisation du type d'interpréteur détecté
            base = os.path.basename(python_candidate).lower()
            if (
                python_candidate.startswith(exe_dir)
                or "python_embedded" in python_candidate
            ):
                self._safe_log(
                    f"➡️ Utilisation de l'interpréteur Python embarqué : {python_candidate}"
                )
            elif base in ("py", "py.exe") or shutil.which(base):
                self._safe_log(
                    f"➡️ Utilisation de l'interpréteur système : {python_candidate}"
                )
            else:
                self._safe_log(f"➡️ Utilisation de sys.executable : {python_candidate}")

            self.venv_progress_dialog = ProgressDialog(
                "Création de l'environnement virtuel", self.parent
            )
            self.venv_progress_dialog.set_message("Création du venv...")

            process = QProcess(self.parent)
            self._venv_create_process = process
            process.setProgram(python_candidate)
            args = ["-m", "venv", venv_path]
            # Si l'on utilise le launcher Windows 'py', forcer Python 3 avec -3
            if base in ("py", "py.exe"):
                args = ["-3"] + args
            process.setArguments(args)
            process.setWorkingDirectory(path)
            process.readyReadStandardOutput.connect(
                lambda: self._on_venv_output(process)
            )
            process.readyReadStandardError.connect(
                lambda: self._on_venv_output(process, error=True)
            )
            process.finished.connect(
                lambda code, status: self._on_venv_created(
                    process, code, status, venv_path
                )
            )
            self._venv_progress_lines = 0
            self.venv_progress_dialog.show()
            process.start()
            # Safety timeout for venv creation (10 min)
            self._arm_process_timeout(process, 600_000, "venv creation")
        except Exception as e:
            self._safe_log(
                f"❌ Échec de création du venv ou installation de PyInstaller : {e}"
            )

    def _on_venv_output(self, process, error=False):
        if getattr(self.parent, "_closing", False):
            return
        data = (
            process.readAllStandardError().data().decode()
            if error
            else process.readAllStandardOutput().data().decode()
        )
        try:
            if self.venv_progress_dialog:
                lines = data.strip().splitlines()
                if lines:
                    self.venv_progress_dialog.set_message(lines[-1])
                self._venv_progress_lines += len(lines)
                self.venv_progress_dialog.set_progress(self._venv_progress_lines, 0)
        except Exception:
            pass
        self._safe_log(data)

    def _on_venv_created(self, process, code, status, venv_path):
        if getattr(self.parent, "_closing", False):
            return
        if code == 0:
            self._safe_log("✅ Environnement virtuel créé avec succès.")
            try:
                if self.venv_progress_dialog:
                    self.venv_progress_dialog.set_message("Venv créé.")
                    self.venv_progress_dialog.close()
            except Exception:
                pass
            # Installer les dépendances du projet à partir de requirements.txt si présent
            try:
                self.install_requirements_if_needed(os.path.dirname(venv_path))
            except Exception:
                pass
        else:
            self._safe_log(f"❌ Échec de création du venv (code {code})")
            try:
                if self.venv_progress_dialog:
                    self.venv_progress_dialog.set_message(
                        "Erreur lors de la création du venv."
                    )
                    self.venv_progress_dialog.close()
            except Exception:
                pass
        QApplication.processEvents()
    # ---------- Install requirements.txt ----------
    def install_requirements_if_needed(self, path: str):
        req_path = os.path.join(path, "requirements.txt")
        if not os.path.exists(req_path):
            return
        existing, default_path = self._detect_venv_in(path)
        venv_root = existing or default_path
        if not existing:
            # Create default .venv if none exists
            self.create_venv_if_needed(path)
            existing2, _ = self._detect_venv_in(path)
            venv_root = existing2 or venv_root
        ok, reason = self.validate_venv_strict(venv_root)
        if not ok:
            self._safe_log(f"⚠️ Invalid venv for requirements: {reason}")
            # Offer to delete and recreate, then retry installation
            if self._prompt_recreate_invalid_venv(venv_root, reason):
                # if recreated, try install again
                self._start_requirements_install(path, venv_root, req_path)
            return

        # Vérifier la liaison de manière asynchrone, puis démarrer l'installation
        def _after_binding(ok_bind: bool):
            if not ok_bind:
                self._safe_log(
                    "⚠️ Liaison venv invalide (python/pip ne pointent pas vers le venv); installation ignorée."
                )
                return
            self._start_requirements_install(path, venv_root, req_path)
        self._verify_venv_binding_async(venv_root, _after_binding)

    def _start_requirements_install(self, path: str, venv_root: str, req_path: str):
        py_exe = self.python_path(venv_root)
        if not os.path.isfile(py_exe):
            self._safe_log(
                "⚠️ python introuvable dans le venv; installation requirements ignorée."
            )
            return
        # Compute checksum and skip install if unchanged
        try:
            with open(req_path, "rb") as f:
                data = f.read()
            req_hash = hashlib.sha256(data).hexdigest()
        except Exception as e:
            self._safe_log(f"⚠️ Impossible de calculer le hash de requirements.txt: {e}")
            req_hash = None
        marker_path = os.path.join(venv_root, ".requirements.sha256")
        if req_hash and os.path.isfile(marker_path):
            try:
                with open(marker_path, encoding="utf-8") as mf:
                    current = mf.read().strip()
                if current == req_hash:
                    self._safe_log(
                        "✅ requirements.txt déjà installé (aucun changement détecté)."
                    )
                    return
            except Exception:
                pass
        self._safe_log(
            "📦 Installation des dépendances à partir de requirements.txt..."
        )
        try:
            # remember marker info to write after success
            self._req_marker_path = marker_path
            self._req_marker_hash = req_hash
            self._req_path = req_path
            self._venv_python_exe = py_exe
            self._pip_phase = "ensurepip"
            self.progress_dialog = ProgressDialog(
                "Installation des dépendances", self.parent
            )
            self.progress_dialog.set_message("Activation de pip (ensurepip)...")
            process = QProcess(self.parent)
            self._req_install_process = process
            process.setProgram(py_exe)
            process.setArguments(["-m", "ensurepip", "--upgrade"])
            process.setWorkingDirectory(path)
            process.readyReadStandardOutput.connect(
                lambda: self._on_pip_output(process)
            )
            process.readyReadStandardError.connect(
                lambda: self._on_pip_output(process, error=True)
            )
            process.finished.connect(
                lambda code, status: self._on_pip_finished(process, code, status)
            )
            self._pip_progress_lines = 0
            self.progress_dialog.show()
            process.start()
            # Safety timeout for ensurepip (3 min)
            self._arm_process_timeout(process, 180_000, "ensurepip")
        except Exception as e:
            self._safe_log(f"❌ Échec installation requirements.txt : {e}")

    def _on_pip_output(self, process, error=False):
        if getattr(self.parent, "_closing", False):
            return
        data = (
            process.readAllStandardError().data().decode()
            if error
            else process.readAllStandardOutput().data().decode()
        )
        try:
            if self.progress_dialog:
                # Affiche la dernière ligne reçue
                lines = data.strip().splitlines()
                if lines:
                    self.progress_dialog.set_message(lines[-1])
                self._pip_progress_lines += len(lines)
                # Simule une progression (pip ne donne pas de %)
                self.progress_dialog.set_progress(self._pip_progress_lines, 0)
        except Exception:
            pass
        self._safe_log(data)

    def _on_pip_finished(self, process, code, status):
        if getattr(self.parent, "_closing", False):
            return
        phase = self._pip_phase
        if phase == "ensurepip":
            # Proceed to upgrade pip/setuptools/wheel regardless of ensurepip result
            try:
                if self.progress_dialog:
                    self.progress_dialog.set_message(
                        "Mise à niveau de pip/setuptools/wheel..."
                    )
            except Exception:
                pass
            p2 = QProcess(self.parent)
            self._req_install_process = p2
            p2.setProgram(self._venv_python_exe)
            p2.setArguments(
                ["-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"]
            )
            p2.setWorkingDirectory(os.path.dirname(self._req_path))
            p2.readyReadStandardOutput.connect(lambda: self._on_pip_output(p2))
            p2.readyReadStandardError.connect(
                lambda: self._on_pip_output(p2, error=True)
            )
            self._pip_phase = "upgrade"
            p2.finished.connect(
                lambda code2, status2: self._on_pip_finished(p2, code2, status2)
            )
            p2.start()
            # Safety timeout for upgrade (5 min)
            self._arm_process_timeout(p2, 300_000, "pip upgrade core")
            return
        elif phase == "upgrade":
            if code == 0:
                # now install requirements.txt
                try:
                    if self.progress_dialog:
                        self.progress_dialog.set_message(
                            "Installation des dépendances (requirements.txt)..."
                        )
                except Exception:
                    pass
                p2 = QProcess(self.parent)
                self._req_install_process = p2
                p2.setProgram(self._venv_python_exe)
                p2.setArguments(["-m", "pip", "install", "-r", self._req_path])
                p2.setWorkingDirectory(os.path.dirname(self._req_path))
                p2.readyReadStandardOutput.connect(lambda: self._on_pip_output(p2))
                p2.readyReadStandardError.connect(
                    lambda: self._on_pip_output(p2, error=True)
                )
                self._pip_phase = "install"
                p2.finished.connect(
                    lambda code2, status2: self._on_pip_finished(p2, code2, status2)
                )
                p2.start()
                # Safety timeout for requirements install (15 min)
                self._arm_process_timeout(
                    p2, 900_000, "pip install -r requirements.txt"
                )
                return
            else:
                self._safe_log(
                    f"❌ Échec mise à niveau pip/setuptools/wheel (code {code})"
                )
                try:
                    if self.progress_dialog:
                        self.progress_dialog.set_message(
                            "Échec upgrade pip/setuptools/wheel."
                        )
                except Exception:
                    pass
        else:
            if code == 0:
                self._safe_log("✅ requirements.txt installé.")
                # Write/update marker if we computed it
                try:
                    if getattr(self, "_req_marker_path", None) and getattr(
                        self, "_req_marker_hash", None
                    ):
                        with open(self._req_marker_path, "w", encoding="utf-8") as mf:
                            mf.write(self._req_marker_hash)
                except Exception:
                    pass
                finally:
                    self._req_marker_path = None
                    self._req_marker_hash = None
                try:
                    if self.progress_dialog:
                        self.progress_dialog.set_message("Installation terminée.")
                except Exception:
                    pass
            else:
                self._safe_log(f"❌ Échec installation requirements.txt (code {code})")
                try:
                    if self.progress_dialog:
                        self.progress_dialog.set_message(
                            "Erreur lors de l'installation."
                        )
                except Exception:
                    pass
        try:
            if self.progress_dialog:
                self.progress_dialog.close()
        except Exception:
            pass
        QApplication.processEvents()
    # ---------- Background tasks status/control ----------
    def has_active_tasks(self) -> bool:
        try:
            if self.venv_progress_dialog and self.venv_progress_dialog.isVisible():
                return True
        except Exception:
            pass
        try:
            if self.progress_dialog and self.progress_dialog.isVisible():
                return True
        except Exception:
            pass
        try:
            if self.venv_check_progress and self.venv_check_progress.isVisible():
                return True
        except Exception:
            pass
        return False

    def terminate_tasks(self):
        # Kill processes
        for attr in [
            "_venv_create_process",
            "_venv_check_process",
            "_venv_check_install_process",
            "_req_install_process",
        ]:
            proc = getattr(self, attr, None)
            try:
                if proc:
                    proc.kill()
            except Exception:
                pass
            setattr(self, attr, None)
        # Close dialogs
        for dlg_attr in [
            "venv_progress_dialog",
            "progress_dialog",
            "venv_check_progress",
        ]:
            dlg = getattr(self, dlg_attr, None)
            try:
                if dlg:
                    dlg.close()
            except Exception:
                pass

    def get_active_task_labels(self, lang: str) -> list[str]:
        """Return active venv task labels in requested language ('English' or 'Français')."""
        labels_fr = {
            "create": "création du venv",
            "reqs": "installation des dépendances",
            "check": "vérification/installation du venv",
        }
        labels_en = {
            "create": "venv creation",
            "reqs": "dependencies installation",
            "check": "venv check/installation",
        }
        L = labels_en if lang == "English" else labels_fr
        out = []
        try:
            if self.venv_progress_dialog and self.venv_progress_dialog.isVisible():
                out.append(L["create"])
        except Exception:
            pass
        try:
            if self.progress_dialog and self.progress_dialog.isVisible():
                out.append(L["reqs"])
        except Exception:
            pass
        try:
            if self.venv_check_progress and self.venv_check_progress.isVisible():
                out.append(L["check"])
        except Exception:
            pass
        return out
