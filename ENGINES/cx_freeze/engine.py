# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import os
import platform
import sys
from typing import Optional

from engine_sdk import CompilerEngine, SysDependencyManager, pip_executable, pip_install, pip_show, resolve_project_venv


class CxFreezeEngine(CompilerEngine):
    id = "cx_freeze"
    name = "cx_Freeze"

    def _resolve_venv_root(self, gui) -> Optional[str]:
        try:
            return resolve_project_venv(gui)
        except Exception:
            return None

    def _pip_exe(self, vroot: str) -> str:
        return pip_executable(vroot)

    def _log(self, gui, fr: str, en: str) -> None:
        try:
            gui.log.append(gui.tr(fr, en))
        except Exception:
            pass

    def _norm_path(self, gui, p: str) -> str:
        try:
            s = str(p).strip()
        except Exception:
            s = p
        try:
            s = os.path.expanduser(s)
        except Exception:
            pass
        if not os.path.isabs(s):
            try:
                base = getattr(gui, "workspace_dir", None)
                if base:
                    s = os.path.join(base, s)
            except Exception:
                pass
        try:
            s = os.path.abspath(s)
        except Exception:
            pass
        return s

    def _dedupe_args(self, seq: list[str]) -> list[str]:
        seen = set()
        out: list[str] = []
        for x in seq:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    def _ensure_output_dir(self, gui, p: str) -> str:
        """Normalize and ensure the output directory exists. Fallback to workspace/dist when needed."""
        try:
            ws = getattr(gui, "workspace_dir", None) or os.getcwd()
        except Exception:
            ws = os.getcwd()
        try:
            target = self._norm_path(gui, p or "")
        except Exception:
            target = os.path.join(ws, "dist")
        # If path points to a file, use its parent
        try:
            if os.path.isfile(target):
                self._log(
                    gui,
                    f"⚠️ Le chemin de sortie pointe vers un fichier: {target}. Utilisation du dossier parent.",
                    f"⚠️ Output path points to a file: {target}. Using parent directory.",
                )
                target = os.path.dirname(target) or os.path.join(ws, "dist")
        except Exception:
            pass
        # Try to create
        try:
            os.makedirs(target, exist_ok=True)
            return target
        except Exception as e:
            self._log(
                gui,
                f"⚠️ Impossible de créer le dossier de sortie '{target}': {e}. Utilisation de workspace/dist.",
                f"⚠️ Failed to create output directory '{target}': {e}. Using workspace/dist.",
            )
            fallback = os.path.join(ws, "dist")
            try:
                os.makedirs(fallback, exist_ok=True)
                return fallback
            except Exception as e2:
                self._log(
                    gui,
                    f"❌ Échec de création du dossier fallback '{fallback}': {e2}",
                    f"❌ Failed to create fallback directory '{fallback}': {e2}",
                )
                last = os.path.join(os.getcwd(), "dist")
                try:
                    os.makedirs(last, exist_ok=True)
                except Exception:
                    pass
                return last

    def _ensure_tool_with_pip(self, gui, vroot: str, package: str) -> bool:
        pip = self._pip_exe(vroot)
        try:
            if pip_show(gui, pip, package) == 0:
                try:
                    gui.log.append(gui.tr(f"✅ {package} déjà installé", f"✅ {package} already installed"))
                except Exception:
                    pass
                return True
            try:
                gui.log.append(gui.tr(f"📦 Installation de {package}…", f"📦 Installing {package}…"))
            except Exception:
                pass
            ok = pip_install(gui, pip, package) == 0
            try:
                if ok:
                    gui.log.append(gui.tr("✅ Installation réussie", "✅ Installation successful"))
                else:
                    gui.log.append(
                        gui.tr(f"❌ Installation échouée ({package})", f"❌ Installation failed ({package})")
                    )
            except Exception:
                pass
            return ok
        except Exception:
            return False

    def preflight(self, gui, file: str) -> bool:
        # Dépendances système (Linux/Windows)
        try:
            import shutil as _shutil
            import subprocess as _subprocess

            def _tr(fr, en):
                try:
                    return gui.tr(fr, en)
                except Exception:
                    return fr

            os_name = platform.system()
            if os_name == "Linux":
                # Vérification complète des outils nécessaires
                required_cmds = {
                    "gcc": "gcc",
                    "g++": "g++",
                    "make": "make",
                    "pkg-config/pkgconf": "pkg-config",
                    "patchelf": "patchelf",
                    "python3-dev/python3-devel (headers)": "python3-config",
                }
                missing = []
                for label, cmd in required_cmds.items():
                    c = _shutil.which(cmd)
                    if not c:
                        if cmd == "pkg-config" and not (_shutil.which("pkg-config") or _shutil.which("pkgconf")):
                            missing.append("pkg-config/pkgconf")
                        elif cmd != "pkg-config":
                            missing.append(label)
                # 7z optionnel pour archives
                if not (_shutil.which("7z") or _shutil.which("7za")):
                    missing.append("p7zip (7z/7za)")
                # Python devel via config.h
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
                # Libs via pkg-config
                has_pkgconf = (_shutil.which("pkg-config") or _shutil.which("pkgconf")) is not None
                missing_libs = []
                if has_pkgconf:
                    for pc in ("openssl", "zlib"):
                        try:
                            rc = _subprocess.run(
                                ["pkg-config", "--exists", pc], stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL
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
                    needs_libxcrypt = not (
                        os.path.exists("/usr/lib/libcrypt.so.1")
                        or os.path.exists("/lib/x86_64-linux-gnu/libcrypt.so.1")
                    )
                if missing or missing_libs or needs_libxcrypt:
                    sdm = SysDependencyManager(parent_widget=gui)
                    pm = sdm.detect_linux_package_manager()
                    if not pm:
                        try:
                            from PySide6.QtWidgets import QMessageBox

                            QMessageBox.critical(
                                gui,
                                _tr("Gestionnaire de paquets non détecté", "Package manager not detected"),
                                _tr(
                                    "Impossible d'installer automatiquement les dépendances système (build tools, python3-dev, pkg-config, openssl, zlib, etc.).",
                                    "Unable to auto-install system dependencies (build tools, python3-dev, pkg-config, openssl, zlib, etc.).",
                                ),
                            )
                        except Exception:
                            pass
                        return False
                    if pm == "apt":
                        packages = [
                            "build-essential",
                            "python3",
                            "python3-dev",
                            "python3-pip",
                            "pkg-config",
                            "libssl-dev",
                            "zlib1g-dev",
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
                            gui.log.append("🔧 Dépendances système manquantes détectées (" + "; ".join(details) + ").")
                    except Exception:
                        pass
                    proc = sdm.install_packages_linux(packages, pm=pm)
                    if not proc:
                        try:
                            gui.log.append("⛔ Compilation cx_Freeze annulée ou installation non démarrée.\n")
                        except Exception:
                            pass
                        return False
                    try:
                        gui.log.append(
                            "⏳ Installation des dépendances système en arrière‑plan… Relancez la compilation après l'installation."
                        )
                    except Exception:
                        pass
                    # Ne pas bloquer l'UI; arrêter le préflight et relancer plus tard
                    return False
            elif os_name == "Windows":
                sdm = SysDependencyManager(parent_widget=gui)
                pkgs = [
                    {
                        "id": "Microsoft.VisualStudio.2022.BuildTools",
                        "override": "--add Microsoft.VisualStudio.Workload.VCTools --passive --norestart",
                    }
                ]
                p = sdm.install_packages_windows(pkgs)
                if p is not None:
                    try:
                        gui.log.append(
                            _tr(
                                "⏳ Installation des dépendances Windows en arrière‑plan… Relancez la compilation après l'installation.",
                                "⏳ Installing Windows dependencies in background… Relaunch the build after installation.",
                            )
                        )
                    except Exception:
                        pass
                    # Ne pas bloquer l'UI; arrêter le préflight et relancer plus tard
                    return False
                if p is None:
                    import webbrowser

                    from PySide6.QtWidgets import QMessageBox

                    msg = QMessageBox(gui)
                    msg.setIcon(QMessageBox.Question)
                    msg.setWindowTitle(_tr("Installer MinGW-w64 (mhw)", "Install MinGW-w64 (mhw)"))
                    msg.setText(
                        _tr(
                            "Pour compiler avec cx_Freeze sous Windows, il faut un compilateur C/C++.\n\nWinget indisponible. Voulez-vous ouvrir la page MinGW-w64 (winlibs.com) ?\n\nAprès installation, relancez la compilation.",
                            "To build with cx_Freeze on Windows, a C/C++ compiler is required.\n\nWinget unavailable. Do you want to open the MinGW-w64 page (winlibs.com)?\n\nAfter installation, restart the build.",
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
        try:
            vroot = self._resolve_venv_root(gui)
            if not vroot:
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
            # With VenvManager
            vm = getattr(gui, "venv_manager", None)
            if vm:
                if vm.is_tool_installed(vroot, "cx_Freeze") or vm.is_tool_installed(vroot, "cxfreeze"):
                    return True
                try:
                    gui.log.append(
                        gui.tr(
                            "🔎 Vérification de cx_Freeze dans le venv (asynchrone)…",
                            "🔎 Verifying cx_Freeze in venv (async)…",
                        )
                    )
                except Exception:
                    pass

                def _on_check(ok: bool):
                    try:
                        if ok:
                            gui.log.append(gui.tr("✅ cx_Freeze déjà installé", "✅ cx_Freeze already installed"))
                        else:
                            gui.log.append(
                                gui.tr(
                                    "📦 Installation de cx_Freeze dans le venv (asynchrone)…",
                                    "📦 Installing cx_Freeze in venv (async)…",
                                )
                            )
                            vm.ensure_tools_installed(vroot, ["cx_Freeze"])
                    except Exception:
                        pass

                try:
                    vm.is_tool_installed_async(vroot, "cx_Freeze", _on_check)
                except Exception:
                    try:
                        gui.log.append(
                            gui.tr(
                                "📦 Installation de cx_Freeze dans le venv (asynchrone)…",
                                "📦 Installing cx_Freeze in venv (async)…",
                            )
                        )
                    except Exception:
                        pass
                    vm.ensure_tools_installed(vroot, ["cx_Freeze"])
                return False
            else:
                # pip install cx-Freeze
                return self._ensure_tool_with_pip(gui, vroot, "cx-Freeze")
        except Exception:
            return True

    def build_command(self, gui, file: str) -> list[str]:
        # Basic cx_Freeze: python -m cx_Freeze <script> --target-dir <dist>
        out_dir = None
        # Prefer engine tab field if present
        try:
            if getattr(self, "_output_dir_input", None) is not None:
                v = self._output_dir_input.text().strip()
                if v:
                    out_dir = v
        except Exception:
            pass
        if not out_dir:
            try:
                out_dir = gui.output_dir_input.text().strip() if getattr(gui, "output_dir_input", None) else None
                if not out_dir:
                    base = getattr(gui, "workspace_dir", None) or os.getcwd()
                    out_dir = os.path.join(base, "dist")
            except Exception:
                base = getattr(gui, "workspace_dir", None) or os.getcwd()
                out_dir = os.path.join(base, "dist")
        out_dir = self._ensure_output_dir(gui, out_dir)
        try:
            if getattr(self, "_output_dir_input", None) is not None:
                self._output_dir_input.setText(out_dir)
            if hasattr(gui, "output_dir_input") and getattr(gui, "output_dir_input", None):
                gui.output_dir_input.setText(out_dir)
        except Exception:
            pass
        cmd = [sys.executable, "-m", "cx_Freeze", file, "--target-dir", out_dir]
        extra: list[str] = []
        # Apply base (Windows only for Win32GUI)
        try:
            if hasattr(self, "_base_combo") and self._base_combo:
                base_val = self._base_combo.currentText().strip()
                if platform.system() == "Windows" and base_val and base_val != "Console":
                    extra += ["--base-name", base_val]
        except Exception:
            pass
        # Backward compatibility with old GUI checkbox
        try:
            if (
                hasattr(self, "_cb_gui")
                and self._cb_gui
                and self._cb_gui.isChecked()
                and platform.system() == "Windows"
            ):
                extra += ["--base-name", "Win32GUI"]
        except Exception:
            pass
        # Include dependencies toggle
        try:
            if (
                hasattr(self, "_cb_include_deps")
                and self._cb_include_deps is not None
                and not self._cb_include_deps.isChecked()
            ):
                extra += ["--no-include-deps"]
        except Exception:
            pass
        # Include encodings
        try:
            if hasattr(self, "_cb_enc") and self._cb_enc and self._cb_enc.isChecked():
                extra += ["--include-modules", "encodings"]
        except Exception:
            pass
        # Icon
        try:
            p = self._icon_edit.text().strip() if hasattr(self, "_icon_edit") and self._icon_edit else ""
            if p:
                try:
                    p_norm = self._norm_path(gui, p)
                except Exception:
                    p_norm = p
                if os.path.isfile(p_norm):
                    extra += ["--icon", p_norm]
                else:
                    self._log(gui, f"⚠️ Icône introuvable: {p_norm}", f"⚠️ Icon not found: {p_norm}")
        except Exception:
            pass
        # Target name
        try:
            if hasattr(self, "_target_name_input") and self._target_name_input:
                tn = self._target_name_input.text().strip()
                if tn:
                    extra += ["--target-name", tn]
        except Exception:
            pass
        # Packages
        try:
            if hasattr(self, "_pkg_list") and self._pkg_list:
                for i in range(self._pkg_list.count()):
                    t = self._pkg_list.item(i).text().strip()
                    if t:
                        extra += ["--packages", t]
        except Exception:
            pass
        # Modules
        try:
            if hasattr(self, "_mod_list") and self._mod_list:
                for i in range(self._mod_list.count()):
                    t = self._mod_list.item(i).text().strip()
                    if t:
                        extra += ["--include-modules", t]
        except Exception:
            pass
        # Excludes
        try:
            if hasattr(self, "_ex_list") and self._ex_list:
                for i in range(self._ex_list.count()):
                    t = self._ex_list.item(i).text().strip()
                    if t:
                        extra += ["--exclude-modules", t]
        except Exception:
            pass
        # Data files
        try:
            if hasattr(self, "_data_list") and self._data_list:
                for i in range(self._data_list.count()):
                    it = self._data_list.item(i).text()
                    if "->" in it:
                        src, dst = (x.strip() for x in it.split("->", 1))
                    else:
                        src, dst = it, ""
                    pair = src if not dst else f"{src}{os.pathsep}{dst}"
                    extra += ["--include-files", pair]
        except Exception:
            pass
        # Zip include/exclude
        try:
            if hasattr(self, "_zip_include_list") and self._zip_include_list:
                for i in range(self._zip_include_list.count()):
                    t = self._zip_include_list.item(i).text().strip()
                    if t:
                        extra += ["--zip-include", t]
        except Exception:
            pass
        try:
            if hasattr(self, "_zip_exclude_list") and self._zip_exclude_list:
                for i in range(self._zip_exclude_list.count()):
                    t = self._zip_exclude_list.item(i).text().strip()
                    if t:
                        extra += ["--zip-exclude", t]
        except Exception:
            pass
        # Replace paths
        try:
            if hasattr(self, "_replace_paths_edit") and self._replace_paths_edit:
                rp = self._replace_paths_edit.text().strip()
                if rp:
                    extra += ["--replace-paths", rp]
        except Exception:
            pass
        # Constants
        try:
            if hasattr(self, "_constants_edit") and self._constants_edit:
                ct = self._constants_edit.text().strip()
                if ct:
                    extra += ["--constants", ct]
        except Exception:
            pass
            # Optimize level
        try:
            if hasattr(self, "_opt_combo") and self._opt_combo:
                lvl = int(self._opt_combo.currentText().strip() or "0")
                if lvl > 0:
                    extra += ["--optimize", str(lvl)]
        except Exception:
            pass
        # Auto-plugins mapping for cx_Freeze
        try:
            from engine_sdk import auto_plugins as _ap  # type: ignore

            auto_args = _ap.compute_auto_for_engine(gui, "cx_freeze") or []
        except Exception:
            auto_args = []
        try:
            extra = self._dedupe_args(extra)
        except Exception:
            pass
        return cmd + extra + auto_args

    def program_and_args(self, gui, file: str) -> Optional[tuple[str, list[str]]]:
        # Resolve cxfreeze (or python -m cx_Freeze) in venv; we'll prefer module form using python from venv
        try:
            # Validate script path
            try:
                if not os.path.isfile(file):
                    try:
                        gui.log.append(gui.tr("❌ Script introuvable: ", "❌ Script not found: ") + str(file))
                        gui.show_error_dialog(os.path.basename(file))
                    except Exception:
                        pass
                    return None
            except Exception:
                pass
            vm = getattr(gui, "venv_manager", None)
            vroot = vm.resolve_project_venv() if vm else None
            if not vroot:
                gui.log.append(
                    gui.tr("❌ Venv introuvable pour résoudre cx_Freeze.", "❌ Venv not found to resolve cx_Freeze.")
                )
                gui.show_error_dialog(os.path.basename(file))
                return None
            vbin = os.path.join(vroot, "Scripts" if platform.system() == "Windows" else "bin")
            python_exe = os.path.join(vbin, "python.exe" if platform.system() == "Windows" else "python")
            if not os.path.isfile(python_exe):
                gui.log.append(
                    gui.tr("❌ python non trouvé dans le venv : ", "❌ python not found in venv: ") + str(python_exe)
                )
                gui.show_error_dialog(os.path.basename(file))
                return None
            cmd = self.build_command(gui, file)
            # Replace sys.executable with python_exe from venv
            if cmd and (cmd[0].endswith("python") or cmd[0].endswith("python.exe")):
                cmd[0] = python_exe
            # Ensure target directory exists and normalize it
            try:
                if "--target-dir" in cmd:
                    idx = cmd.index("--target-dir")
                    if idx + 1 < len(cmd):
                        td = cmd[idx + 1]
                        td_norm = self._ensure_output_dir(gui, td)
                        cmd[idx + 1] = td_norm
            except Exception:
                pass
            return python_exe, cmd[1:]
        except Exception:
            return None

    def get_output_directory(self, gui) -> Optional[str]:
        """Return the cx_Freeze output directory for ACASL.
        ACASL-only method: engines define their output directory but never open it themselves.
        """
        try:
            # Try engine-specific output field first (cx_output_dir objectName)
            try:
                from PySide6.QtWidgets import QWidget

                if hasattr(gui, "findChild") and callable(gui.findChild):
                    le = gui.findChild(QWidget, "cx_output_dir")
                    if le and hasattr(le, "text") and callable(le.text):
                        v = str(le.text()).strip()
                        if v:
                            return v
            except Exception:
                pass

            # Try engine tab field if present
            try:
                if getattr(self, "_output_dir_input", None) is not None:
                    v = self._output_dir_input.text().strip()
                    if v:
                        return v
            except Exception:
                pass

            # Fallback to global output_dir_input
            w = getattr(gui, "output_dir_input", None)
            if w and hasattr(w, "text") and callable(w.text):
                v = str(w.text()).strip()
                if v:
                    return v

            # Final fallback to workspace/dist
            ws = getattr(gui, "workspace_dir", None) or os.getcwd()
            return os.path.join(ws, "dist")
        except Exception:
            # Ultimate fallback
            return os.path.join(os.getcwd(), "dist")

    def on_success(self, gui, file: str) -> None:
        # ACASL-only policy: engines must not open output directories. Use this hook only for lightweight metadata/logging if needed.
        try:
            return
        except Exception:
            pass

    def environment(self, gui, file: str) -> Optional[dict[str, str]]:
        return None

    def create_tab(self, gui):
        # Create a compact cx_Freeze options tab with only essential settings
        try:
            from PySide6.QtWidgets import (
                QCheckBox,
                QComboBox,
                QFileDialog,
                QHBoxLayout,
                QLabel,
                QLineEdit,
                QPushButton,
                QVBoxLayout,
                QWidget,
            )
        except Exception:
            return None
        tab = QWidget()
        layout = QVBoxLayout(tab)
        # Title
        try:
            title = QLabel(gui.tr("Options cx_Freeze", "cx_Freeze Options"))
            layout.addWidget(title)
            self._cx_title = title
        except Exception:
            self._cx_title = None
        # Output dir row
        row = QHBoxLayout()
        out_edit = QLineEdit()
        out_edit.setObjectName("cx_output_dir")
        try:
            out_edit.setPlaceholderText(gui.tr("Dossier de sortie (--target-dir)", "Output directory (--target-dir)"))
        except Exception:
            pass
        browse_btn = QPushButton(gui.tr("Parcourir…", "Browse…"))
        self._cx_out_browse_btn = browse_btn

        def _browse():
            # Open dialog with a sensible default directory and sync global output dir
            try:
                start_dir = ""
                try:
                    cur = out_edit.text().strip()
                    if cur:
                        start_dir = cur
                    else:
                        ws = getattr(gui, "workspace_dir", None)
                        if ws:
                            start_dir = ws
                except Exception:
                    start_dir = ""
                d = QFileDialog.getExistingDirectory(
                    tab, gui.tr("Choisir le dossier de sortie", "Choose output directory"), start_dir
                )
            except Exception:
                d = QFileDialog.getExistingDirectory(tab, "Choose output directory", start_dir if 'start_dir' in locals() else "")
            if d:
                out_edit.setText(d)
                try:
                    if hasattr(gui, "output_dir_input") and gui.output_dir_input:
                        gui.output_dir_input.setText(d)
                except Exception:
                    pass

        try:
            browse_btn.clicked.connect(_browse)
        except Exception:
            pass
        row.addWidget(out_edit)
        row.addWidget(browse_btn)
        layout.addLayout(row)
        # Target name
        row_tn = QHBoxLayout()
        try:
            tn_label = QLabel(gui.tr("Nom de la cible", "Target name"))
            row_tn.addWidget(tn_label)
            self._cx_tn_label = tn_label
        except Exception:
            self._cx_tn_label = None
        tn_edit = QLineEdit()
        tn_edit.setObjectName("cx_target_name")
        try:
            tn_edit.setPlaceholderText(gui.tr("Nom de l'exécutable (--target-name)", "Executable name (--target-name)"))
        except Exception:
            pass
        row_tn.addWidget(tn_edit)
        layout.addLayout(row_tn)
        self._target_name_input = tn_edit
        # Base selection and include-deps
        row2 = QHBoxLayout()
        base_label = QLabel(gui.tr("Base", "Base"))
        base_combo = QComboBox()
        try:
            if platform.system() == "Windows":
                base_combo.addItems(["Console", "Win32GUI"])
            else:
                base_combo.addItems(["Console"])
        except Exception:
            pass
        cb_deps = QCheckBox(gui.tr("Inclure dépendances", "Include dependencies"))
        try:
            cb_deps.setChecked(True)
        except Exception:
            pass
        cb_enc = QCheckBox(gui.tr("Inclure encodings", "Include encodings"))
        row2.addWidget(base_label)
        row2.addWidget(base_combo)
        row2.addStretch(1)
        row2.addWidget(cb_deps)
        row2.addWidget(cb_enc)
        row2.addStretch(1)
        layout.addLayout(row2)
        self._base_label = base_label
        self._base_combo = base_combo
        self._cb_include_deps = cb_deps
        self._cb_enc = cb_enc
        # Icon picker
        row3 = QHBoxLayout()
        try:
            _icon_title = QLabel(gui.tr("Icône", "Icon"))
            row3.addWidget(_icon_title)
            self._cx_icon_title = _icon_title
        except Exception:
            self._cx_icon_title = None
        icon_edit = QLineEdit()
        icon_btn = QPushButton(gui.tr("Parcourir…", "Browse…"))
        self._cx_icon_browse_btn = icon_btn

        def _browse_icon():
            try:
                if platform.system() == "Windows":
                    filt = "Icon (*.ico);;All files (*)"
                elif platform.system() == "Darwin":
                    filt = "Icon (*.icns);;All files (*)"
                else:
                    filt = "Icon (*.ico *.icns);;All files (*)"
                p, _ = QFileDialog.getOpenFileName(tab, gui.tr("Choisir une icône", "Choose an icon"), "", filt)
            except Exception:
                p, _ = QFileDialog.getOpenFileName(tab, "Choose an icon", "", "*.ico *.icns *.*")
            if p:
                icon_edit.setText(p)

        try:
            icon_btn.clicked.connect(_browse_icon)
        except Exception:
            pass
        row3.addWidget(icon_edit)
        row3.addWidget(icon_btn)
        layout.addLayout(row3)
        # Optimize level
        opt_row = QHBoxLayout()
        try:
            _opt_title = QLabel(gui.tr("Optimisation", "Optimize"))
            opt_row.addWidget(_opt_title)
            self._cx_optimize_title = _opt_title
        except Exception:
            self._cx_optimize_title = None
        opt_combo = QComboBox()
        opt_combo.addItems(["0", "1", "2"])  # python -O / -OO equivalent
        opt_row.addWidget(opt_combo)
        opt_row.addStretch(1)
        layout.addLayout(opt_row)
        # Keep references for build_command/on_success
        self._output_dir_input = out_edit
        self._target_name_input = tn_edit
        self._base_combo = base_combo
        self._cb_include_deps = cb_deps
        self._icon_edit = icon_edit
        self._opt_combo = opt_combo
        # Apply engine-local i18n immediately (independent from app languages)
        try:
            self.apply_i18n(gui, {})
        except Exception:
            pass
        return tab, gui.tr("cx_Freeze", "cx_Freeze")

    def apply_i18n(self, gui, tr: dict[str, str]) -> None:
        """Apply engine-local i18n from ENGINES/cx_freeze/languages/*.json independent of app languages."""
        try:
            # Resolve language code preference
            code = None
            try:
                if isinstance(tr, dict):
                    meta = tr.get("_meta", {})
                    code = meta.get("code") if isinstance(meta, dict) else None
            except Exception:
                code = None
            if not code:
                try:
                    # Try GUI preferences
                    pref = getattr(gui, "language_pref", getattr(gui, "language", "System"))
                    if isinstance(pref, str) and pref != "System":
                        code = pref
                except Exception:
                    pass
            # Fallback
            if not code:
                code = "en"
            # Normalize codes and build robust fallback candidates
            raw = str(code)
            low = raw.lower().replace("_", "-")
            aliases = {
                "en-us": "en",
                "en_gb": "en",
                "en-uk": "en",
                "fr-fr": "fr",
                "fr_ca": "fr",
                "fr-ca": "fr",
                "pt-br": "pt-BR",
                "pt_br": "pt-BR",
                "zh": "zh-CN",
                "zh_cn": "zh-CN",
                "zh-cn": "zh-CN",
            }
            mapped = aliases.get(low, raw)
            # Candidate order: mapped -> base (before '-') -> exact lower -> exact raw -> 'en'
            candidates = []
            if mapped not in candidates:
                candidates.append(mapped)
            base = None
            try:
                if "-" in mapped:
                    base = mapped.split("-", 1)[0]
                elif "_" in mapped:
                    base = mapped.split("_", 1)[0]
            except Exception:
                base = None
            if base and base not in candidates:
                candidates.append(base)
            if low not in candidates:
                candidates.append(low)
            if raw not in candidates:
                candidates.append(raw)
            if "en" not in candidates:
                candidates.append("en")
            # Load engine-local JSON using the first existing candidate
            import importlib.resources as ilr
            import json as _json

            pkg = __package__
            lang_data = {}

            def _load_lang(c: str) -> bool:
                nonlocal lang_data
                try:
                    with ilr.as_file(ilr.files(pkg).joinpath("languages", f"{c}.json")) as p:
                        if os.path.isfile(str(p)):
                            with open(str(p), encoding="utf-8") as f:
                                lang_data = _json.load(f) or {}
                            return True
                except Exception:
                    pass
                return False

            for cand in candidates:
                if _load_lang(cand):
                    break

            # Helper to fetch engine keys
            def g(key: str) -> Optional[str]:
                try:
                    v = lang_data.get(key)
                    return v if isinstance(v, str) and v.strip() else None
                except Exception:
                    return None

            # Apply title text
            try:
                if getattr(self, "_cx_title", None):
                    self._cx_title.setText(g("cx_freeze_title") or gui.tr("Options cx_Freeze", "cx_Freeze Options"))
            except Exception:
                pass
            # Output dir
            try:
                if getattr(self, "_output_dir_input", None):
                    ph = g("cx_output_dir_ph") or gui.tr(
                        "Dossier de sortie (--target-dir)", "Output directory (--target-dir)"
                    )
                    try:
                        self._output_dir_input.setPlaceholderText(ph)
                    except Exception:
                        pass
                    tt = g("tt_cx_output_dir")
                    if tt:
                        self._output_dir_input.setToolTip(tt)
                if getattr(self, "_cx_out_browse_btn", None):
                    self._cx_out_browse_btn.setText(g("browse") or gui.tr("Parcourir…", "Browse…"))
            except Exception:
                pass
            # Target name i18n
            try:
                if getattr(self, "_cx_tn_label", None):
                    self._cx_tn_label.setText(g("target_name_title") or gui.tr("Nom de la cible", "Target name"))
                if getattr(self, "_target_name_input", None):
                    ph = g("cx_target_name_ph") or gui.tr(
                        "Nom de l'exécutable (--target-name)", "Executable name (--target-name)"
                    )
                    try:
                        self._target_name_input.setPlaceholderText(ph)
                    except Exception:
                        pass
                    tt = g("tt_cx_target_name")
                    if tt:
                        self._target_name_input.setToolTip(tt)
            except Exception:
                pass
            # Base + include-deps + encodings
            try:
                if getattr(self, "_base_label", None):
                    self._base_label.setText(g("base_title") or gui.tr("Base", "Base"))
                if getattr(self, "_base_combo", None):
                    tt = g("tt_cx_base")
                    if tt:
                        self._base_combo.setToolTip(tt)
                if getattr(self, "_cb_include_deps", None):
                    txt = g("include_deps") or gui.tr("Inclure dépendances", "Include dependencies")
                    self._cb_include_deps.setText(txt)
                    tt = g("tt_cx_include_deps")
                    if tt:
                        self._cb_include_deps.setToolTip(tt)
                if getattr(self, "_cb_enc", None):
                    txt = g("include_encodings") or gui.tr("Inclure encodings", "Include encodings")
                    self._cb_enc.setText(txt)
                    tt = g("tt_cx_include_encodings")
                    if tt:
                        self._cb_enc.setToolTip(tt)
            except Exception:
                pass
            # Icon edit
            try:
                if getattr(self, "_cx_icon_title", None):
                    self._cx_icon_title.setText(g("icon") or gui.tr("Icône", "Icon"))
                if getattr(self, "_icon_edit", None):
                    tt = g("tt_cx_icon")
                    if tt:
                        self._icon_edit.setToolTip(tt)
                if getattr(self, "_cx_icon_browse_btn", None):
                    self._cx_icon_browse_btn.setText(g("browse") or gui.tr("Parcourir…", "Browse…"))
            except Exception:
                pass
            # Lists
            try:
                if getattr(self, "_cx_packages_title", None):
                    self._cx_packages_title.setText(
                        g("packages_title") or gui.tr("Paquets à inclure", "Packages to include")
                    )
                if getattr(self, "_pkg_list", None):
                    tt = g("tt_cx_packages")
                    if tt:
                        self._pkg_list.setToolTip(tt)
                if getattr(self, "_cx_pkg_add_btn", None):
                    self._cx_pkg_add_btn.setText(g("add") or gui.tr("Ajouter", "Add"))
                if getattr(self, "_cx_pkg_rm_btn", None):
                    self._cx_pkg_rm_btn.setText(g("remove") or gui.tr("Supprimer", "Remove"))
            except Exception:
                pass
            try:
                if getattr(self, "_cx_modules_title", None):
                    self._cx_modules_title.setText(
                        g("modules_title") or gui.tr("Modules à inclure", "Modules to include")
                    )
                if getattr(self, "_mod_list", None):
                    tt = g("tt_cx_modules")
                    if tt:
                        self._mod_list.setToolTip(tt)
                if getattr(self, "_cx_mod_add_btn", None):
                    self._cx_mod_add_btn.setText(g("add") or gui.tr("Ajouter", "Add"))
                if getattr(self, "_cx_mod_rm_btn", None):
                    self._cx_mod_rm_btn.setText(g("remove") or gui.tr("Supprimer", "Remove"))
            except Exception:
                pass
            # Excludes i18n
            try:
                if getattr(self, "_cx_excludes_title", None):
                    self._cx_excludes_title.setText(
                        g("excludes_title") or gui.tr("Exclusions (modules/paquets)", "Modules/packages to exclude")
                    )
                if getattr(self, "_ex_list", None):
                    tt = g("tt_cx_excludes")
                    if tt:
                        self._ex_list.setToolTip(tt)
                if getattr(self, "_cx_ex_add_btn", None):
                    self._cx_ex_add_btn.setText(g("add") or gui.tr("Ajouter", "Add"))
                if getattr(self, "_cx_ex_rm_btn", None):
                    self._cx_ex_rm_btn.setText(g("remove") or gui.tr("Supprimer", "Remove"))
            except Exception:
                pass
            try:
                if getattr(self, "_cx_data_title", None):
                    self._cx_data_title.setText(
                        g("data_title")
                        or gui.tr("Fichiers/Dossiers à inclure (données)", "Data files/directories to include")
                    )
                if getattr(self, "_data_list", None):
                    tt = g("tt_cx_data")
                    if tt:
                        self._data_list.setToolTip(tt)
                if getattr(self, "_cx_data_add_file_btn", None):
                    self._cx_data_add_file_btn.setText(g("add_file") or gui.tr("Ajouter fichier", "Add file"))
                if getattr(self, "_cx_data_add_dir_btn", None):
                    self._cx_data_add_dir_btn.setText(g("add_directory") or gui.tr("Ajouter dossier", "Add directory"))
                if getattr(self, "_cx_data_rm_btn", None):
                    self._cx_data_rm_btn.setText(g("remove") or gui.tr("Supprimer", "Remove"))
            except Exception:
                pass
            # Zip include/exclude i18n
            try:
                if getattr(self, "_cx_zip_include_title", None):
                    self._cx_zip_include_title.setText(
                        g("zip_include_title") or gui.tr("Patterns d'inclusion ZIP", "Zip include patterns")
                    )
                if getattr(self, "_zip_include_list", None):
                    tt = g("tt_cx_zip_include")
                    if tt:
                        self._zip_include_list.setToolTip(tt)
                if getattr(self, "_cx_zi_add_btn", None):
                    self._cx_zi_add_btn.setText(g("add") or gui.tr("Ajouter", "Add"))
                if getattr(self, "_cx_zi_rm_btn", None):
                    self._cx_zi_rm_btn.setText(g("remove") or gui.tr("Supprimer", "Remove"))
            except Exception:
                pass
            try:
                if getattr(self, "_cx_zip_exclude_title", None):
                    self._cx_zip_exclude_title.setText(
                        g("zip_exclude_title") or gui.tr("Patterns d'exclusion ZIP", "Zip exclude patterns")
                    )
                if getattr(self, "_zip_exclude_list", None):
                    tt = g("tt_cx_zip_exclude")
                    if tt:
                        self._zip_exclude_list.setToolTip(tt)
                if getattr(self, "_cx_ze_add_btn", None):
                    self._cx_ze_add_btn.setText(g("add") or gui.tr("Ajouter", "Add"))
                if getattr(self, "_cx_ze_rm_btn", None):
                    self._cx_ze_rm_btn.setText(g("remove") or gui.tr("Supprimer", "Remove"))
            except Exception:
                pass
            # Replace paths / Constants i18n
            try:
                if getattr(self, "_cx_replace_title", None):
                    self._cx_replace_title.setText(
                        g("replace_paths_title") or gui.tr("Remplacer chemins", "Replace paths")
                    )
                if getattr(self, "_replace_paths_edit", None):
                    ph = g("cx_replace_paths_ph") or gui.tr(
                        "pattern=>replacement, séparés par des virgules", "pattern=>replacement, comma-separated"
                    )
                    try:
                        self._replace_paths_edit.setPlaceholderText(ph)
                    except Exception:
                        pass
                    tt = g("tt_cx_replace_paths")
                    if tt:
                        self._replace_paths_edit.setToolTip(tt)
            except Exception:
                pass
            try:
                if getattr(self, "_cx_constants_title", None):
                    self._cx_constants_title.setText(g("constants_title") or gui.tr("Constantes", "Constants"))
                if getattr(self, "_constants_edit", None):
                    ph = g("cx_constants_ph") or gui.tr(
                        "NAME=VALUE, séparés par des virgules", "NAME=VALUE, comma-separated"
                    )
                    try:
                        self._constants_edit.setPlaceholderText(ph)
                    except Exception:
                        pass
                    tt = g("tt_cx_constants")
                    if tt:
                        self._constants_edit.setToolTip(tt)
            except Exception:
                pass
            try:
                if getattr(self, "_cx_optimize_title", None):
                    self._cx_optimize_title.setText(g("optimize") or gui.tr("Optimisation", "Optimize"))
                if getattr(self, "_opt_combo", None):
                    tt = g("tt_cx_optimize")
                    if tt:
                        self._opt_combo.setToolTip(tt)
            except Exception:
                pass
        except Exception:
            pass
