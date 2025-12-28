import hashlib
import os
import platform
import shutil
import sys

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from ..dialogs import ProgressDialog


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

        # Retry counters for resilience
        self._venv_check_retries = {}
        self._max_retries = 2

        # Encoding detection for subprocess output
        self._output_encoding = "utf-8"
        self._fallback_encodings = ["utf-8", "latin-1", "cp1252", "ascii"]

        # Environment manager detection
        self._detected_manager = None  # 'pip', 'poetry', 'conda', 'pipenv', 'uv', 'pdm'
        self._manager_commands = {
            "poetry": {
                "create_venv": ["poetry", "env", "use", "python"],
                "install": ["poetry", "install"],
                "add": ["poetry", "add"],
                "show": ["poetry", "show"],
                "check": ["poetry", "check"],
                "lock": ["poetry", "lock"],
            },
            "conda": {
                "create_venv": ["conda", "create", "-y", "-n"],
                "install": ["conda", "install", "-y"],
                "activate": ["conda", "activate"],
                "list": ["conda", "list"],
                "check": ["conda", "list"],
            },
            "pipenv": {
                "create_venv": ["pipenv", "--python"],
                "install": ["pipenv", "install"],
                "add": ["pipenv", "install"],
                "show": ["pipenv", "graph"],
                "check": ["pipenv", "check"],
                "lock": ["pipenv", "lock"],
            },
            "uv": {
                "create_venv": ["uv", "venv"],
                "install": ["uv", "pip", "install", "-r"],
                "add": ["uv", "pip", "install"],
                "show": ["uv", "pip", "show"],
                "check": ["uv", "pip", "check"],
            },
            "pdm": {
                "create_venv": ["pdm", "venv", "create"],
                "install": ["pdm", "install"],
                "add": ["pdm", "add"],
                "show": ["pdm", "show"],
                "check": ["pdm", "check"],
                "lock": ["pdm", "lock"],
            },
            "pip": {
                "create_venv": ["python", "-m", "venv"],
                "install": ["pip", "install", "-r"],
                "add": ["pip", "install"],
                "show": ["pip", "show"],
                "check": ["pip", "check"],
            },
        }

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
    def _safe_decode(self, data: bytes, error_handling: str = "replace") -> str:
        """Safely decode bytes with fallback encodings."""
        if isinstance(data, str):
            return data
        for encoding in self._fallback_encodings:
            try:
                return data.decode(encoding, errors=error_handling)
            except Exception:
                continue
        # Last resort: decode with errors ignored
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return "[Decode Error]"

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

    def _is_stdlib_module(self, module_name: str) -> bool:
        """Check if a module is part of Python's standard library."""
        try:
            import sys
            import sysconfig
            import importlib.util

            # Check if it's a built-in module
            if module_name in sys.builtin_module_names:
                return True

            # Try to find the module spec
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                return False

            # Check if it's a built-in or frozen module
            if getattr(spec, "origin", None) in ("built-in", "frozen"):
                return True

            # Check if it's in the stdlib path
            stdlib_path = sysconfig.get_path("stdlib") or ""
            stdlib_path = os.path.realpath(stdlib_path)

            if getattr(spec, "origin", None):
                origin_path = os.path.realpath(spec.origin)
                if os.path.commonpath([origin_path, stdlib_path]) == stdlib_path:
                    return True

            for loc in spec.submodule_search_locations or []:
                loc_path = os.path.realpath(loc)
                try:
                    if os.path.commonpath([loc_path, stdlib_path]) == stdlib_path:
                        return True
                except Exception:
                    pass

            return False
        except Exception:
            return False

    def _safe_rmtree(self, path: str, max_retries: int = 3) -> bool:
        """Safely remove a directory tree with retries for locked files."""
        if not os.path.exists(path):
            return True
        for attempt in range(max_retries):
            try:
                shutil.rmtree(path)
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    try:
                        import time

                        time.sleep(0.5)  # Brief pause before retry
                    except Exception:
                        pass
                else:
                    self._safe_log(
                        f"⚠️ Failed to remove {path} after {max_retries} attempts: {e}"
                    )
                    return False
        return False

    def _safe_mkdir(self, path: str) -> bool:
        """Safely create a directory with error handling."""
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            self._safe_log(f"⚠️ Failed to create directory {path}: {e}")
            return False

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

    def _find_all_venvs_in(self, base: str) -> list[str]:
        """Find all potential venv directories in the base path.
        Returns a list of valid venv paths, sorted by preference.
        """
        try:
            base = os.path.abspath(base)
        except Exception:
            return []

        venvs = []
        common_names = [".venv", "venv", ".env", "env", "virtualenv"]

        for name in common_names:
            venv_path = os.path.join(base, name)
            if os.path.isdir(venv_path):
                ok, _ = self.validate_venv_strict(venv_path)
                if ok:
                    venvs.append(venv_path)

        return venvs

    def _score_venv(self, venv_path: str, workspace_dir: str) -> tuple[int, str]:
        """Score a venv based on its completeness and requirements satisfaction.
        Returns (score, reason) where higher score = better venv.

        Scoring criteria:
        - Has requirements.txt satisfied: +100
        - Has pyinstaller: +50
        - Has nuitka: +50
        - Has pip/setuptools/wheel: +30
        - Is valid venv: +10
        - Has binding verified: +20
        """
        score = 0
        reasons = []

        try:
            # Check if venv is valid
            ok, _ = self.validate_venv_strict(venv_path)
            if not ok:
                return 0, "Invalid venv structure"
            score += 10
            reasons.append("valid_structure")

            # Check binding
            if self.verify_venv_binding(venv_path):
                score += 20
                reasons.append("verified_binding")
            else:
                return score, "Invalid binding (python/pip don't point to venv)"

            # Check for requirements.txt
            req_path = os.path.join(workspace_dir, "requirements.txt")
            if os.path.isfile(req_path):
                # Check if requirements are already installed
                py_exe = self.python_path(venv_path)
                if os.path.isfile(py_exe):
                    try:
                        import subprocess

                        result = subprocess.run(
                            [py_exe, "-m", "pip", "check"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if result.returncode == 0:
                            score += 100
                            reasons.append("requirements_satisfied")
                        else:
                            reasons.append("requirements_not_satisfied")
                    except Exception:
                        reasons.append("requirements_check_failed")

            # Check for key tools
            tools_to_check = [
                ("pyinstaller", 50),
                ("nuitka", 50),
            ]
            for tool, tool_score in tools_to_check:
                if self.has_tool_binary(venv_path, tool):
                    score += tool_score
                    reasons.append(f"has_{tool}")

            # Check for pip/setuptools/wheel
            pip_exe = self.pip_path(venv_path)
            if os.path.isfile(pip_exe):
                score += 30
                reasons.append("has_pip")

            return score, ", ".join(reasons)
        except Exception as e:
            return 0, f"Scoring error: {e}"

    def select_best_venv(self, workspace_dir: str) -> str | None:
        """Select the best venv from multiple candidates.

        Strategy:
        1. Find all valid venvs in workspace
        2. Score each based on completeness and requirements satisfaction
        3. Return the highest-scoring venv
        4. If no valid venv found, return None
        """
        try:
            venvs = self._find_all_venvs_in(workspace_dir)

            if not venvs:
                self._safe_log("ℹ️ Aucun venv valide trouvé dans le workspace.")
                return None

            if len(venvs) == 1:
                self._safe_log(f"✅ Un seul venv trouvé: {venvs[0]}")
                return venvs[0]

            # Multiple venvs found - score and select the best
            self._safe_log(
                f"ℹ️ {len(venvs)} venv(s) trouvé(s), sélection du meilleur..."
            )

            scored_venvs = []
            for venv_path in venvs:
                score, reason = self._score_venv(venv_path, workspace_dir)
                scored_venvs.append((score, venv_path, reason))
                self._safe_log(
                    f"  - {os.path.basename(venv_path)}: score={score} ({reason})"
                )

            # Sort by score (descending)
            scored_venvs.sort(key=lambda x: x[0], reverse=True)

            best_score, best_venv, best_reason = scored_venvs[0]

            if best_score == 0:
                self._safe_log("❌ Aucun venv valide avec une bonne liaison.")
                return None

            self._safe_log(
                f"✅ Meilleur venv sélectionné: {os.path.basename(best_venv)} (score={best_score})"
            )
            return best_venv
        except Exception as e:
            self._safe_log(f"⚠️ Erreur lors de la sélection du meilleur venv: {e}")
            return None

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

    # ---------- Requirements detection and generation ----------
    def _find_requirements_files(
        self, path: str, workspace_dir: str | None = None
    ) -> list[str]:
        """Find all potential requirements files in the project.
        Supports: requirements.txt, requirements-*.txt, Pipfile, Pipfile.lock,
                  pyproject.toml, setup.py, setup.cfg, poetry.lock, etc.

        Uses ARK config to determine priority order if available.
        """
        try:
            path = os.path.abspath(path)
        except Exception:
            return []

        requirements_files = []

        # Load ARK config to get requirements file patterns
        try:
            from Core.ark_config_loader import load_ark_config, get_dependency_options

            if workspace_dir:
                ark_config = load_ark_config(workspace_dir)
                dep_opts = get_dependency_options(ark_config)
                patterns = dep_opts.get(
                    "requirements_files",
                    [
                        "requirements.txt",
                        "requirements-prod.txt",
                        "requirements-dev.txt",
                        "Pipfile",
                        "Pipfile.lock",
                        "pyproject.toml",
                        "setup.py",
                        "setup.cfg",
                        "poetry.lock",
                        "conda.yml",
                        "environment.yml",
                    ],
                )
            else:
                patterns = [
                    "requirements.txt",
                    "requirements-prod.txt",
                    "requirements-dev.txt",
                    "Pipfile",
                    "Pipfile.lock",
                    "pyproject.toml",
                    "setup.py",
                    "setup.cfg",
                    "poetry.lock",
                    "conda.yml",
                    "environment.yml",
                ]
        except Exception:
            patterns = [
                "requirements.txt",
                "requirements-prod.txt",
                "requirements-dev.txt",
                "Pipfile",
                "Pipfile.lock",
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "poetry.lock",
                "conda.yml",
                "environment.yml",
            ]

        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if not os.path.isfile(item_path):
                    continue

                # Check exact matches
                if item in patterns:
                    requirements_files.append(item_path)
                # Check wildcard patterns
                elif item.startswith("requirements-") and item.endswith(".txt"):
                    requirements_files.append(item_path)
        except Exception:
            pass

        return requirements_files

    def _generate_requirements_from_imports(self, workspace_dir: str) -> str | None:
        """Generate requirements.txt by analyzing Python imports in the project.
        Returns the path to the generated requirements.txt, or None if failed.
        """
        try:
            import ast
            import re as _re

            self._safe_log(
                "🔍 Génération de requirements.txt à partir des imports du projet..."
            )

            modules = set()
            python_files = []

            # Find all Python files
            for root, dirs, files in os.walk(workspace_dir):
                # Skip venv directories
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in (".venv", "venv", ".env", "env", "__pycache__")
                ]
                for file in files:
                    if file.endswith(".py"):
                        python_files.append(os.path.join(root, file))

            # Analyze imports
            for py_file in python_files:
                try:
                    with open(py_file, encoding="utf-8", errors="ignore") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=py_file)

                    # Standard imports
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                modules.add(alias.name.split(".")[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                modules.add(node.module.split(".")[0])

                    # Dynamic imports
                    dynamic_imports = _re.findall(
                        r"__import__\(['\"]([\w\.]+)['\"]\)", source
                    )
                    modules.update([mod.split(".")[0] for mod in dynamic_imports])
                    importlib_imports = _re.findall(
                        r"importlib\.import_module\(['\"]([\w\.]+)['\"]\)", source
                    )
                    modules.update([mod.split(".")[0] for mod in importlib_imports])
                except Exception:
                    pass

            # Filter out stdlib modules
            external_modules = []
            for mod in sorted(modules):
                if not self._is_stdlib_module(mod):
                    external_modules.append(mod)

            if not external_modules:
                self._safe_log("ℹ️ Aucun module externe détecté dans le projet.")
                return None

            # Generate requirements.txt
            req_path = os.path.join(workspace_dir, "requirements.txt")
            try:
                with open(req_path, "w", encoding="utf-8") as f:
                    f.write("# Auto-generated requirements.txt\n")
                    f.write("# Generated from project imports\n\n")
                    for mod in external_modules:
                        f.write(f"{mod}\n")

                self._safe_log(
                    f"✅ requirements.txt généré avec {len(external_modules)} dépendances"
                )
                return req_path
            except Exception as e:
                self._safe_log(
                    f"❌ Erreur lors de la génération de requirements.txt: {e}"
                )
                return None
        except Exception as e:
            self._safe_log(f"⚠️ Erreur lors de l'analyse des imports: {e}")
            return None

    def _extract_requirements_from_pyproject(self, pyproject_path: str) -> list[str]:
        """Extract dependencies from pyproject.toml (Poetry, Flit, etc.)"""
        try:
            import re as _re

            with open(pyproject_path, encoding="utf-8") as f:
                content = f.read()

            # Simple regex-based extraction (not a full TOML parser)
            # Look for dependencies sections
            deps = []

            # Poetry format: [tool.poetry.dependencies]
            poetry_match = _re.search(
                r"\[tool\.poetry\.dependencies\](.*?)(?=\[|$)", content, _re.DOTALL
            )
            if poetry_match:
                section = poetry_match.group(1)
                # Extract package names (simple format: package = "version")
                for line in section.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        pkg_name = line.split("=")[0].strip().strip("\"'")
                        if pkg_name and pkg_name != "python":
                            deps.append(pkg_name)

            # Flit format: [project] dependencies
            flit_match = _re.search(r"\[project\](.*?)(?=\[|$)", content, _re.DOTALL)
            if flit_match:
                section = flit_match.group(1)
                deps_match = _re.search(
                    r"dependencies\s*=\s*\[(.*?)\]", section, _re.DOTALL
                )
                if deps_match:
                    deps_str = deps_match.group(1)
                    for line in deps_str.split(","):
                        line = line.strip().strip("\"'")
                        if line:
                            # Extract package name from "package>=1.0" format
                            pkg_name = _re.split(r"[<>=!]", line)[0].strip()
                            if pkg_name:
                                deps.append(pkg_name)

            return list(set(deps))
        except Exception:
            return []

    def _extract_requirements_from_setup(self, setup_path: str) -> list[str]:
        """Extract dependencies from setup.py or setup.cfg"""
        try:
            import re as _re

            with open(setup_path, encoding="utf-8") as f:
                content = f.read()

            deps = []

            # Look for install_requires
            match = _re.search(r"install_requires\s*=\s*\[(.*?)\]", content, _re.DOTALL)
            if match:
                deps_str = match.group(1)
                for line in deps_str.split(","):
                    line = line.strip().strip("\"'")
                    if line:
                        pkg_name = _re.split(r"[<>=!]", line)[0].strip()
                        if pkg_name:
                            deps.append(pkg_name)

            return list(set(deps))
        except Exception:
            return []

    def _extract_requirements_from_pipfile(self, pipfile_path: str) -> list[str]:
        """Extract dependencies from Pipfile"""
        try:
            import re as _re

            with open(pipfile_path, encoding="utf-8") as f:
                content = f.read()

            deps = []

            # Look for [packages] section
            match = _re.search(r"\[packages\](.*?)(?=\[|$)", content, _re.DOTALL)
            if match:
                section = match.group(1)
                for line in section.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        pkg_name = line.split("=")[0].strip().strip("\"'")
                        if pkg_name:
                            deps.append(pkg_name)

            return list(set(deps))
        except Exception:
            return []

    def _get_requirements_file(self, workspace_dir: str) -> str | None:
        """Get or generate a requirements file for the project.

        Strategy:
        1. Load ARK config to get requirements file preferences
        2. Look for existing requirements files (requirements.txt, Pipfile, pyproject.toml, etc.)
        3. If found, convert to requirements.txt if needed
        4. If not found, generate from project imports (if enabled in ARK config)
        5. Return path to requirements.txt
        """
        try:
            workspace_dir = os.path.abspath(workspace_dir)

            # Load ARK config to get requirements file preferences
            try:
                from Core.ark_config_loader import (
                    load_ark_config,
                    get_dependency_options,
                )

                ark_config = load_ark_config(workspace_dir)
                dep_opts = get_dependency_options(ark_config)
                auto_generate = dep_opts.get("auto_generate_from_imports", True)
                output_file = dep_opts.get("generate_output_file", "requirements.txt")
            except Exception:
                auto_generate = True
                output_file = "requirements.txt"

            # Check for existing requirements files
            req_files = self._find_requirements_files(workspace_dir, workspace_dir)

            if req_files:
                self._safe_log(
                    f"ℹ️ Fichiers de dépendances trouvés: {[os.path.basename(f) for f in req_files]}"
                )

                # If requirements.txt exists, use it
                req_txt = os.path.join(workspace_dir, output_file)
                if os.path.isfile(req_txt):
                    return req_txt

                # Try to convert other formats to requirements.txt
                for req_file in req_files:
                    basename = os.path.basename(req_file)
                    deps = []

                    if basename == "Pipfile":
                        deps = self._extract_requirements_from_pipfile(req_file)
                    elif basename == "pyproject.toml":
                        deps = self._extract_requirements_from_pyproject(req_file)
                    elif basename in ("setup.py", "setup.cfg"):
                        deps = self._extract_requirements_from_setup(req_file)
                    elif basename.startswith("requirements-"):
                        # Use requirements-*.txt files
                        try:
                            with open(req_file, encoding="utf-8") as f:
                                deps = [
                                    line.strip()
                                    for line in f
                                    if line.strip() and not line.startswith("#")
                                ]
                        except Exception:
                            pass

                    if deps:
                        # Generate requirements.txt from extracted deps
                        try:
                            with open(req_txt, "w", encoding="utf-8") as f:
                                f.write(f"# Converted from {basename}\n")
                                f.write(
                                    f"# ARK Config: generate_output_file = {output_file}\n\n"
                                )
                                for dep in deps:
                                    f.write(f"{dep}\n")
                            self._safe_log(
                                f"✅ {output_file} généré à partir de {basename}"
                            )
                            return req_txt
                        except Exception as e:
                            self._safe_log(
                                f"⚠️ Erreur lors de la conversion de {basename}: {e}"
                            )

            # No requirements file found
            if not auto_generate:
                self._safe_log(
                    "ℹ️ Auto-génération des requirements désactivée dans ARK config"
                )
                return None

            # Generate from imports
            return self._generate_requirements_from_imports(workspace_dir)
        except Exception as e:
            self._safe_log(f"⚠️ Erreur lors de la détection des requirements: {e}")
            return None

    # ---------- Install requirements.txt ----------
    def install_requirements_if_needed(self, path: str):
        # Get or generate requirements file
        req_path = self._get_requirements_file(path)
        if not req_path:
            self._safe_log("ℹ️ Aucun fichier de dépendances trouvé ou généré.")
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

    # ---------- Environment Manager Detection & Handling ----------
    def _detect_environment_manager(self, workspace_dir: str) -> str:
        """Detect which environment manager is used in the project.

        Uses ARK configuration to determine priority order if available.
        Falls back to default priority if not configured.

        Default priority order:
        1. Poetry (pyproject.toml with [tool.poetry])
        2. Pipenv (Pipfile)
        3. Conda (environment.yml, conda.yml)
        4. PDM (pyproject.toml with [tool.pdm])
        5. UV (pyproject.toml with [tool.uv])
        6. Pip (requirements.txt, setup.py)
        """
        try:
            workspace_dir = os.path.abspath(workspace_dir)

            # Load ARK configuration to get manager priorities
            try:
                from Core.ark_config_loader import (
                    load_ark_config,
                    get_environment_manager_options,
                )

                ark_config = load_ark_config(workspace_dir)
                env_manager_opts = get_environment_manager_options(ark_config)
                priority_list = env_manager_opts.get(
                    "priority", ["poetry", "pipenv", "conda", "pdm", "uv", "pip"]
                )
                auto_detect = env_manager_opts.get("auto_detect", True)
                fallback_to_pip = env_manager_opts.get("fallback_to_pip", True)
                self._safe_log(f"📋 Priorités des gestionnaires (ARK): {priority_list}")
            except Exception:
                priority_list = ["poetry", "pipenv", "conda", "pdm", "uv", "pip"]
                auto_detect = True
                fallback_to_pip = True

            if not auto_detect:
                self._safe_log(
                    "ℹ️ Auto-détection des gestionnaires désactivée dans ARK config"
                )
                self._detected_manager = "pip"
                return "pip"

            # Detect available managers
            detected_managers = {}

            # Check for Poetry
            pyproject = os.path.join(workspace_dir, "pyproject.toml")
            if os.path.isfile(pyproject):
                try:
                    with open(pyproject, encoding="utf-8") as f:
                        content = f.read()
                    if "[tool.poetry]" in content:
                        detected_managers["poetry"] = "🎵"
                    if "[tool.pdm]" in content:
                        detected_managers["pdm"] = "📦"
                    if "[tool.uv]" in content:
                        detected_managers["uv"] = "⚡"
                except Exception:
                    pass

            # Check for Pipenv
            if os.path.isfile(os.path.join(workspace_dir, "Pipfile")):
                detected_managers["pipenv"] = "🔧"

            # Check for Conda
            for conda_file in ["environment.yml", "conda.yml", "environment.yaml"]:
                if os.path.isfile(os.path.join(workspace_dir, conda_file)):
                    detected_managers["conda"] = "🐍"
                    break

            # Always consider pip as available
            detected_managers["pip"] = "📝"

            if detected_managers:
                self._safe_log(
                    f"ℹ️ Gestionnaires détectés: {', '.join(detected_managers.keys())}"
                )

            # Select the first available manager from the priority list
            for manager in priority_list:
                if manager in detected_managers:
                    self._detected_manager = manager
                    emoji = detected_managers[manager]
                    self._safe_log(f"{emoji} Gestionnaire sélectionné: {manager}")
                    return manager

            # Fallback to pip if no preferred manager found
            if fallback_to_pip:
                self._detected_manager = "pip"
                self._safe_log("📝 Fallback vers Pip")
                return "pip"

            # If fallback disabled and no manager found, still use pip
            self._detected_manager = "pip"
            return "pip"
        except Exception as e:
            self._safe_log(f"⚠️ Erreur détection gestionnaire: {e}")
            self._detected_manager = "pip"
            return "pip"

    def _is_tool_available(self, tool: str) -> bool:
        """Check if a tool is available in the system PATH."""
        try:
            return shutil.which(tool) is not None
        except Exception:
            return False

    def _get_manager_command(self, manager: str, action: str) -> list[str] | None:
        """Get the command for a specific manager and action."""
        try:
            if manager in self._manager_commands:
                if action in self._manager_commands[manager]:
                    return self._manager_commands[manager][action]
        except Exception:
            pass
        return None

    def create_venv_with_manager(
        self, workspace_dir: str, venv_path: str | None = None
    ):
        """Create venv using the detected environment manager."""
        try:
            manager = self._detect_environment_manager(workspace_dir)

            if not venv_path:
                venv_path = os.path.join(workspace_dir, ".venv")

            self._safe_log(f"🔨 Création du venv avec {manager}...")

            # Check if manager is available
            if not self._is_tool_available(manager):
                self._safe_log(
                    f"⚠️ {manager} n'est pas disponible, utilisation de pip..."
                )
                self.create_venv_if_needed(workspace_dir)
                return

            # Get the appropriate command
            cmd = self._get_manager_command(manager, "create_venv")
            if not cmd:
                self._safe_log(f"⚠️ Commande de création non disponible pour {manager}")
                self.create_venv_if_needed(workspace_dir)
                return

            # Build full command
            if manager == "poetry":
                full_cmd = cmd + [sys.executable]
            elif manager == "conda":
                full_cmd = cmd + [os.path.basename(venv_path)]
            elif manager == "pipenv":
                full_cmd = cmd + [sys.executable]
            elif manager == "pdm":
                full_cmd = cmd + [os.path.basename(venv_path)]
            elif manager == "uv":
                full_cmd = cmd + [venv_path]
            else:
                full_cmd = cmd + [venv_path]

            self._safe_log(f"📋 Commande: {' '.join(full_cmd)}")

            # Execute command
            self.venv_progress_dialog = ProgressDialog(
                f"Création du venv avec {manager}", self.parent
            )
            self.venv_progress_dialog.set_message(f"Création du venv avec {manager}...")

            process = QProcess(self.parent)
            self._venv_create_process = process
            process.setProgram(full_cmd[0])
            process.setArguments(full_cmd[1:])
            process.setWorkingDirectory(workspace_dir)
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
            # Safety timeout (15 min for manager-based creation)
            self._arm_process_timeout(process, 900_000, f"{manager} venv creation")
        except Exception as e:
            self._safe_log(f"❌ Erreur création venv avec manager: {e}")
            self.create_venv_if_needed(workspace_dir)

    def install_dependencies_with_manager(
        self, workspace_dir: str, venv_path: str | None = None
    ):
        """Install dependencies using the detected environment manager."""
        try:
            manager = self._detect_environment_manager(workspace_dir)

            if not venv_path:
                venv_path = os.path.join(workspace_dir, ".venv")

            self._safe_log(f"📦 Installation des dépendances avec {manager}...")

            # Check if manager is available
            if not self._is_tool_available(manager):
                self._safe_log(
                    f"⚠️ {manager} n'est pas disponible, utilisation de pip..."
                )
                self.install_requirements_if_needed(workspace_dir)
                return

            # Get the appropriate command
            cmd = self._get_manager_command(manager, "install")
            if not cmd:
                self._safe_log(
                    f"⚠️ Commande d'installation non disponible pour {manager}"
                )
                self.install_requirements_if_needed(workspace_dir)
                return

            # Build full command
            if manager == "poetry":
                full_cmd = cmd  # poetry install
            elif manager == "conda":
                # conda install -y -r environment.yml
                full_cmd = cmd + ["-r", os.path.join(workspace_dir, "environment.yml")]
            elif manager == "pipenv":
                full_cmd = cmd  # pipenv install
            elif manager == "pdm":
                full_cmd = cmd  # pdm install
            elif manager == "uv":
                req_file = os.path.join(workspace_dir, "requirements.txt")
                full_cmd = cmd + [req_file]
            else:
                req_file = os.path.join(workspace_dir, "requirements.txt")
                full_cmd = cmd + [req_file]

            self._safe_log(f"📋 Commande: {' '.join(full_cmd)}")

            # Execute command
            self.progress_dialog = ProgressDialog(
                f"Installation avec {manager}", self.parent
            )
            self.progress_dialog.set_message(
                f"Installation des dépendances avec {manager}..."
            )

            process = QProcess(self.parent)
            self._req_install_process = process
            process.setProgram(full_cmd[0])
            process.setArguments(full_cmd[1:])
            process.setWorkingDirectory(workspace_dir)
            process.readyReadStandardOutput.connect(
                lambda: self._on_pip_output(process)
            )
            process.readyReadStandardError.connect(
                lambda: self._on_pip_output(process, error=True)
            )
            process.finished.connect(
                lambda code, status: self._on_manager_install_finished(
                    process, code, status, manager
                )
            )
            self._pip_progress_lines = 0
            self.progress_dialog.show()
            process.start()
            # Safety timeout (20 min for dependency installation)
            self._arm_process_timeout(process, 1200_000, f"{manager} install")
        except Exception as e:
            self._safe_log(f"❌ Erreur installation avec manager: {e}")
            self.install_requirements_if_needed(workspace_dir)

    def _on_manager_install_finished(self, process, code, status, manager):
        """Callback after manager-based installation."""
        if getattr(self.parent, "_closing", False):
            return

        if code == 0:
            self._safe_log(f"✅ Installation avec {manager} réussie.")
        else:
            self._safe_log(f"❌ Erreur installation avec {manager} (code {code})")

        try:
            if self.progress_dialog:
                self.progress_dialog.set_message("Installation terminée.")
                self.progress_dialog.close()
        except Exception:
            pass

        QApplication.processEvents()

    def get_manager_info(self, workspace_dir: str) -> dict:
        """Get detailed information about the detected environment manager."""
        try:
            manager = self._detect_environment_manager(workspace_dir)

            info = {
                "manager": manager,
                "available": self._is_tool_available(manager),
                "commands": self._manager_commands.get(manager, {}),
            }

            # Add manager-specific info
            if manager == "poetry":
                info["config_file"] = "pyproject.toml"
                info["lock_file"] = "poetry.lock"
            elif manager == "conda":
                info["config_file"] = "environment.yml"
                info["lock_file"] = "conda.lock"
            elif manager == "pipenv":
                info["config_file"] = "Pipfile"
                info["lock_file"] = "Pipfile.lock"
            elif manager == "pdm":
                info["config_file"] = "pyproject.toml"
                info["lock_file"] = "pdm.lock"
            elif manager == "uv":
                info["config_file"] = "pyproject.toml"
                info["lock_file"] = "uv.lock"
            else:
                info["config_file"] = "requirements.txt"
                info["lock_file"] = None

            return info
        except Exception as e:
            self._safe_log(f"⚠️ Erreur récupération info manager: {e}")
            return {"manager": "pip", "available": True, "commands": {}}
