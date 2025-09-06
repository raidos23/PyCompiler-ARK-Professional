# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

"""
Logique de compilation pour PyCompiler Pro++.
Inclut la construction des commandes PyInstaller/Nuitka et la gestion des processus de compilation.
"""
import json
import os
import platform
import re
import subprocess

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QCheckBox, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QWidget

import utils.engines_loader as engines_loader
from engine_sdk.utils import clamp_text, redact_secrets

from .auto_plugins import compute_for_all
from .preferences import MAX_PARALLEL


# Helper to terminate a whole process tree robustly, with OS fallbacks
# Attempts: psutil terminate/kill -> OS-specific commands (taskkill/pkill+killpg)
# Returns True if the routine executed (not a guarantee the OS reaped every zombie)
def _kill_process_tree(pid: int, *, timeout: float = 5.0, log=None) -> bool:
    def _log(msg: str):
        try:
            if log:
                log(msg)
        except Exception:
            pass

    import platform as _plat
    import subprocess as _sp
    import time

    try:
        import signal as _sig
    except Exception:
        _sig = None
    # First, try using psutil if available
    try:
        import psutil  # type: ignore

        try:
            proc = psutil.Process(int(pid))
        except Exception:
            return False
        try:
            children = proc.children(recursive=True)
        except Exception:
            children = []
        # 1) Polite terminate to children then parent
        for c in children:
            try:
                c.terminate()
            except Exception:
                pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            _ = psutil.wait_procs(children + [proc], timeout=max(0.1, timeout / 2))
            # collect alive after first wait
            alive = [p for p in [proc] + children if p.is_running()]
        except Exception:
            alive = [proc] + children
        # 2) Kill remaining
        for a in alive:
            try:
                a.kill()
            except Exception:
                pass
        try:
            psutil.wait_procs(alive, timeout=max(0.1, timeout / 2))
        except Exception:
            pass
        # Refresh liveness
        try:
            alive = [p for p in [proc] + children if p.is_running()]
        except Exception:
            alive = []
        # 3) OS-level fallback if still alive
        if alive:
            system = _plat.system()
            if system == "Windows":
                try:
                    _sp.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=10
                    )
                except Exception:
                    pass
            else:
                # Try kill process group
                try:
                    import os as _os

                    try:
                        pgrp = _os.getpgid(pid)
                    except Exception:
                        pgrp = None
                    if pgrp and _sig is not None:
                        try:
                            _os.killpg(pgrp, _sig.SIGTERM)
                            time.sleep(0.2)
                        except Exception:
                            pass
                except Exception:
                    pass
                # pkill children by parent
                try:
                    _sp.run(["pkill", "-TERM", "-P", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=5)
                except Exception:
                    pass
                time.sleep(0.2)
                try:
                    _sp.run(["pkill", "-KILL", "-P", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=5)
                except Exception:
                    pass
                # Hard kill parent last
                if _sig is not None:
                    try:
                        _sp.run(["kill", "-TERM", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=3)
                    except Exception:
                        pass
                    time.sleep(0.2)
                    try:
                        _sp.run(["kill", "-KILL", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=3)
                    except Exception:
                        pass
        # Final check
        try:
            alive2 = [p for p in [proc] + children if p.is_running()]
        except Exception:
            alive2 = []
        _log(
            f"✅ Process tree terminated (pid={pid})"
            if not alive2
            else f"🛑 Process tree forced killed (pid={pid}, remaining={len(alive2)})"
        )
        return True
    except Exception:
        # psutil not available or failed badly: use OS-level fallbacks only
        system = _plat.system()
        try:
            if system == "Windows":
                _sp.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=10)
                _log(f"🪓 taskkill issued for pid={pid}")
            else:
                try:
                    import os as _os

                    if _sig is not None:
                        try:
                            pgrp = _os.getpgid(pid)
                            _os.killpg(pgrp, _sig.SIGTERM)
                        except Exception:
                            pass
                    _sp.run(["pkill", "-TERM", "-P", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=5)
                    time.sleep(0.2)
                    _sp.run(["pkill", "-KILL", "-P", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=5)
                    if _sig is not None:
                        _sp.run(["kill", "-TERM", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=3)
                        time.sleep(0.2)
                        _sp.run(["kill", "-KILL", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=3)
                    _log(f"🪓 pkill/kill issued for pid={pid}")
                except Exception:
                    pass
        except Exception:
            pass
        return True


def _kill_all_descendants(timeout: float = 2.0, log=None) -> None:
    """Kill every descendant process of the current GUI process (best-effort)."""
    try:
        import os as _os

        import psutil  # type: ignore

        me = psutil.Process(_os.getpid())
        # Snapshot children to avoid races while killing
        kids = []
        try:
            kids = me.children(recursive=True)
        except Exception:
            kids = []
        # Use our robust killer on each child tree
        for ch in kids:
            try:
                _kill_process_tree(int(ch.pid), timeout=timeout, log=log)
            except Exception:
                pass
    except Exception:
        # Fallback: OS-level broad attempts (risk-limited as last resort)
        try:
            import os as _os
            import subprocess as _sp

            _sp.run(["pkill", "-KILL", "-P", str(_os.getpid())], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=2)
        except Exception:
            pass


def compile_all(self):
    import os

    # Garde-fous avant toute opération
    if self.processes:
        QMessageBox.warning(
            self,
            self.tr("Attention", "Warning"),
            self.tr("Des compilations sont déjà en cours.", "Builds are already running."),
        )
        return
    if not self.workspace_dir or (not self.python_files and not self.selected_files):
        self.log.append("❌ Aucun fichier à compiler.\n")
        return

    # Réinitialise les statistiques de compilation pour ce run
    try:
        self._compilation_times = {}
    except Exception:
        pass

    # Désactiver immédiatement les contrôles sensibles (sauf Annuler) et les onglets pendant toute la (pré)compilation
    try:
        self.set_controls_enabled(False)
    except Exception:
        pass
    try:
        if hasattr(self, "compiler_tabs") and self.compiler_tabs:
            self.compiler_tabs.setEnabled(False)
    except Exception:
        pass

    # BCASL: exécution des plugins API avant compilation, sans bloquer l'UI
    try:
        from bcasl.bcasl_loader import run_pre_compile_async as _run_bcasl_async

        # Drapeau de poursuite pour éviter le double déclenchement
        try:
            self._compile_continued = False
        except Exception:
            pass

        # Gating strict: pas de fallback; la compilation ne démarre qu'après la fin de BCASL
        # Continuer la préparation de la compilation une fois BCASL terminé
        def _after_bcasl(_report):
            try:
                # Stop fallback timer if any
                try:
                    tmr2 = getattr(self, "_compile_phase_timer", None)
                    if tmr2:
                        tmr2.stop()
                except Exception:
                    pass
                if not getattr(self, "_compile_continued", False):
                    self._compile_continued = True
                    try:
                        self.log.append("⏭️ Démarrage compilation après BCASL.\n")
                    except Exception:
                        pass
                    _continue_compile_all(self)
            except Exception as _e:
                try:
                    import traceback as _tb

                    self.log.append(f"⚠️ Exception _after_bcasl: {_e}\n{_tb.format_exc()}\n")
                except Exception:
                    pass

        _run_bcasl_async(self, _after_bcasl)
        return  # différer la suite dans le callback pour ne pas bloquer
    except Exception as e:
        try:
            self.log.append(
                f"❌ BCASL non exécuté: {e}\nLa compilation est annulée car les API BCASL doivent terminer avant de compiler.\n"
            )
        except Exception:
            pass
        # Réactiver l'UI et sortir
        try:
            if hasattr(self, "compiler_tabs") and self.compiler_tabs:
                self.compiler_tabs.setEnabled(True)
        except Exception:
            pass
        try:
            self.set_controls_enabled(True)
        except Exception:
            pass
        return

    def is_executable_script(path):
        # Vérifie que le fichier existe, n'est pas dans site-packages, et contient un point d'entrée
        if not os.path.exists(path):
            self.log.append(f"❌ Fichier inexistant : {path}")
            return False
        if "site-packages" in path:
            self.log.append(f"⏩ Ignoré (site-packages) : {path}")
            return False
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
                if "if __name__ == '__main__'" in content or 'if __name__ == "__main__"' in content:
                    return True
                else:
                    self.log.append(f"⏩ Ignoré (pas de point d'entrée) : {path}")
                    return False
        except Exception as e:
            self.log.append(f"⏩ Ignoré (erreur lecture) : {path} ({e})")
            return False

    # Détection du compilateur actif
    use_nuitka = False
    if hasattr(self, "compiler_tabs") and self.compiler_tabs:
        self.compiler_tabs.setEnabled(False)  # Désactive les onglets au début de la compilation
        if self.compiler_tabs.currentIndex() == 1:  # 0 = PyInstaller, 1 = Nuitka
            use_nuitka = True

    # Sélection des fichiers à compiler selon le compilateur
    if use_nuitka:
        # Nuitka : compile tous les fichiers sélectionnés ou tous les fichiers du workspace
        if self.selected_files:
            files_ok = [f for f in self.selected_files if is_executable_script(f)]
        else:
            files_ok = [f for f in self.python_files if is_executable_script(f)]
        self.queue = [(f, True) for f in files_ok]
        total_files = len(files_ok)
    else:
        # PyInstaller : applique la logique main.py/app.py uniquement si l'option est cochée
        if self.selected_files:
            files_ok = [f for f in self.selected_files if is_executable_script(f)]
            self.queue = [(f, True) for f in files_ok]
            total_files = len(files_ok)
        elif self.opt_main_only.isChecked():
            files = [f for f in self.python_files if os.path.basename(f) in ("main.py", "app.py")]
            files_ok = [f for f in files if is_executable_script(f)]
            self.queue = [(f, True) for f in files_ok]
            total_files = len(files_ok)
            if not files_ok:
                self.log.append("⚠️ Aucun main.py ou app.py exécutable trouvé dans le workspace.\n")
                return
        else:
            files_ok = [f for f in self.python_files if is_executable_script(f)]
            self.queue = [(f, True) for f in files_ok]
            total_files = len(files_ok)

    self.current_compiling.clear()
    self.processes.clear()
    self.progress.setRange(0, 0)  # Mode indéterminé pendant toute la compilation
    self.log.append("🔨 Compilation parallèle démarrée...\n")

    self.set_controls_enabled(False)
    self.try_start_processes()


# Nouvelle version de try_start_processes pour gérer les fichiers ignorés dynamiquement


def _continue_compile_all(self):
    # Déplacé depuis compile_all pour poursuivre après BCASL sans bloquer l'UI
    def is_executable_script(path):
        # Vérifie que le fichier existe, n'est pas dans site-packages, et contient un point d'entrée
        if not os.path.exists(path):
            self.log.append(f"❌ Fichier inexistant : {path}")
            return False
        if "site-packages" in path:
            self.log.append(f"⏩ Ignoré (site-packages) : {path}")
            return False
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
                if "if __name__ == '__main__'" in content or 'if __name__ == "__main__"' in content:
                    return True
                else:
                    self.log.append(f"⏩ Ignoré (pas de point d'entrée) : {path}")
                    return False
        except Exception as e:
            self.log.append(f"⏩ Ignoré (erreur lecture) : {path} ({e})")
            return False

    # Détection du compilateur actif
    use_nuitka = False
    if hasattr(self, "compiler_tabs") and self.compiler_tabs:
        self.compiler_tabs.setEnabled(False)  # Désactive les onglets au début de la compilation
        if self.compiler_tabs.currentIndex() == 1:  # 0 = PyInstaller, 1 = Nuitka
            use_nuitka = True

    # Sélection des fichiers à compiler selon le compilateur
    if use_nuitka:
        # Nuitka : compile tous les fichiers sélectionnés ou tous les fichiers du workspace
        if self.selected_files:
            files_ok = [f for f in self.selected_files if is_executable_script(f)]
        else:
            files_ok = [f for f in self.python_files if is_executable_script(f)]
        self.queue = [(f, True) for f in files_ok]
        total_files = len(files_ok)
    else:
        # PyInstaller : applique la logique main.py/app.py uniquement si l'option est cochée
        if self.selected_files:
            files_ok = [f for f in self.selected_files if is_executable_script(f)]
            self.queue = [(f, True) for f in files_ok]
            total_files = len(files_ok)
        elif self.opt_main_only.isChecked():
            files = [f for f in self.python_files if os.path.basename(f) in ("main.py", "app.py")]
            files_ok = [f for f in files if is_executable_script(f)]
            self.queue = [(f, True) for f in files_ok]
            total_files = len(files_ok)
            if not files_ok:
                self.log.append("⚠️ Aucun main.py ou app.py exécutable trouvé dans le workspace.\n")
                return
        else:
            files_ok = [f for f in self.python_files if is_executable_script(f)]
            self.queue = [(f, True) for f in files_ok]
            total_files = len(files_ok)

    self.current_compiling.clear()
    self.processes.clear()
    self.progress.setRange(0, 0)  # Mode indéterminé pendant toute la compilation
    self.log.append("🔨 Compilation parallèle démarrée...\n")

    self.set_controls_enabled(False)
    self.try_start_processes()


def try_start_processes(self):
    from PySide6.QtWidgets import QApplication

    while len(self.processes) < MAX_PARALLEL and self.queue:
        file, to_compile = self.queue.pop(0)
        if to_compile:
            self.start_compilation_process(file)
        # Si le fichier est ignoré (to_compile == False), on ne touche pas à la barre de progression
        # et on passe simplement au suivant
    if not self.processes and not self.queue:
        # Toutes les compilations sont terminées : mettre la barre à 100%
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()
        self.log.append("✔️ Toutes les compilations sont terminées.\n")
        # Collecter les artefacts dès maintenant
        artifacts = []
        try:
            import os as _os

            ws = self.workspace_dir or os.getcwd()
            for d in ("dist", "build"):
                dp = os.path.join(ws, d)
                if os.path.isdir(dp):
                    for root, _dirs, files in os.walk(dp):
                        for f in files:
                            artifacts.append(os.path.join(root, f))
        except Exception:
            pass
        # Décider si ACASL doit s'exécuter; sinon restaurer l'UI immédiatement
        try:
            import os as _os

            no_hooks = _os.environ.get("PYCOMPILER_NO_POST_HOOKS") == "1"
        except Exception:
            no_hooks = False
        if no_hooks or not artifacts:
            if hasattr(self, "compiler_tabs") and self.compiler_tabs:
                self.compiler_tabs.setEnabled(True)
            self.set_controls_enabled(True)
            self.save_preferences()
        else:
            # Laisser l'UI désactivée jusqu'à la fin d'ACASL, puis restaurer dans le callback
            try:
                from acasl import run_post_compile_async

                def _after_acasl(_rep):
                    try:
                        if hasattr(self, "compiler_tabs") and self.compiler_tabs:
                            self.compiler_tabs.setEnabled(True)
                    except Exception:
                        pass
                    try:
                        self.set_controls_enabled(True)
                    except Exception:
                        pass
                    try:
                        self.save_preferences()
                    except Exception:
                        pass

                QTimer.singleShot(
                    0, lambda a=list(artifacts): run_post_compile_async(self, a, finished_cb=_after_acasl)
                )
            except Exception:
                # En cas d'échec de démarrage d'ACASL, restaurer l'UI immédiatement
                if hasattr(self, "compiler_tabs") and self.compiler_tabs:
                    self.compiler_tabs.setEnabled(True)
                self.set_controls_enabled(True)
                self.save_preferences()


def start_compilation_process(self, file):
    import time

    file_basename = os.path.basename(file)
    # Determine active engine from UI tab (via registry mapping)
    try:
        idx = self.compiler_tabs.currentIndex() if hasattr(self, "compiler_tabs") and self.compiler_tabs else 0
        engine_id = engines_loader.registry.get_engine_for_tab(idx) or ("pyinstaller" if idx == 0 else "nuitka")
    except Exception:
        engine_id = "pyinstaller"
    # Instantiate engine
    try:
        engine = engines_loader.registry.create(engine_id)
    except Exception as e:
        self.log.append(f"❌ Impossible d'instancier le moteur '{engine_id}': {e}")
        return
    # Preflight checks
    if not engine.preflight(self, file):
        return
    prog_args = engine.program_and_args(self, file)
    if not prog_args:
        return
    program, args = prog_args
    # Logging human-friendly and progress indeterminate
    from PySide6.QtWidgets import QApplication

    self.progress.setRange(0, 0)
    QApplication.processEvents()
    # Environnement processus (moteur peut surcharger)
    try:
        env = engine.environment(self, file)
    except Exception:
        env = None
    if env:
        try:
            from PySide6.QtCore import QProcessEnvironment

            penv = QProcessEnvironment()
            for k, v in env.items():
                penv.insert(str(k), str(v))
        except Exception:
            penv = None
    else:
        penv = None
    cmd_preview = " ".join([program] + args)
    try:
        cmd_preview_log = clamp_text(redact_secrets(cmd_preview), max_len=1000)
    except Exception:
        cmd_preview_log = cmd_preview
    if engine_id == "nuitka":
        self.log.append(f"▶️ Lancement compilation Nuitka : {file_basename}\nCommande : {cmd_preview_log}\n")
    else:
        self.log.append(f"▶️ Lancement compilation : {file_basename}\nCommande : {cmd_preview_log}\n")
    # Start QProcess
    # Cooperative cancellation sentinel path
    try:
        cancel_dir = os.path.join(self.workspace_dir or os.getcwd(), ".pycompiler", "cancel")
        os.makedirs(cancel_dir, exist_ok=True)
        cancel_file = os.path.join(cancel_dir, f"{engine_id}_{file_basename}.cancel")
        if os.path.isfile(cancel_file):
            os.remove(cancel_file)
    except Exception:
        cancel_file = None
    process = QProcess(self)
    if penv is not None:
        try:
            process.setProcessEnvironment(penv)
        except Exception:
            pass
    process.setProgram(program)
    process.setArguments(args)
    process.setWorkingDirectory(self.workspace_dir)
    process.file_path = file
    process.file_basename = file_basename
    process._start_time = time.time()
    process._engine_id = engine_id
    process._cancel_file = cancel_file
    process.readyReadStandardOutput.connect(lambda p=process: self.handle_stdout(p))
    process.readyReadStandardError.connect(lambda p=process: self.handle_stderr(p))
    process.finished.connect(lambda ec, es, p=process: self.handle_finished(p, ec, es))
    self.processes.append(process)
    self.current_compiling.add(file)
    # Optional: update dependent UI states
    if hasattr(self, "update_compiler_options_enabled"):
        try:
            self.update_compiler_options_enabled()
        except Exception:
            pass
    # Timeout configurable avec arrêt propre puis kill
    try:
        # Méthode engine.get_timeout_seconds si dispo; sinon env/défaut
        try:
            timeout_sec = int(
                getattr(
                    engine,
                    "get_timeout_seconds",
                    lambda _gui: int(os.environ.get("PYCOMPILER_PROCESS_TIMEOUT", "1800")),
                )(self)
            )
        except Exception:
            timeout_sec = int(os.environ.get("PYCOMPILER_PROCESS_TIMEOUT", "1800"))
        if timeout_sec and timeout_sec > 0:
            t = QTimer(self)
            t.setSingleShot(True)

            def _on_timeout(proc=process, seconds=timeout_sec):
                try:
                    self.log.append(
                        f"⏱️ Timeout ({seconds}s) pour {getattr(proc, 'file_basename', '?')}. Arrêt en cours…"
                    )
                except Exception:
                    pass
                try:
                    if proc.state() != QProcess.NotRunning:
                        proc.terminate()
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                # Délai de grâce puis kill forcé
                grace = QTimer(self)
                grace.setSingleShot(True)

                def _force_kill(p=proc):
                    if p.state() != QProcess.NotRunning:
                        try:
                            self.log.append(
                                f"🛑 Arrêt forcé du processus {getattr(p, 'file_basename', '?')} après délai de grâce."
                            )
                        except Exception:
                            pass
                        # Kill full process tree if possible
                        try:
                            pid2 = int(p.processId())
                        except Exception:
                            pid2 = None
                        if pid2:
                            _kill_process_tree(pid2, timeout=3.0, log=self.log.append)
                        try:
                            p.kill()
                        except Exception:
                            pass

                grace.timeout.connect(_force_kill)
                grace.start(10000)  # 10s grâce
                proc._grace_kill_timer = grace

            t.timeout.connect(_on_timeout)
            t.start(int(timeout_sec * 1000))
            process._timeout_timer = t

            def _cancel_timer(_ec, _es, timer=t):
                try:
                    timer.stop()
                except Exception:
                    pass

            process.finished.connect(_cancel_timer)
            # Ensure QProcess object is deleted later to avoid dangling C++ objects
            process.finished.connect(lambda _ec, _es, p=process: p.deleteLater())
    except Exception:
        pass
    process.start()


def handle_stdout(self, process):
    data = process.readAllStandardOutput().data().decode()
    # Tentative d'interprétation d'événements JSON Lines pour progression déterministe
    try:
        for line in data.splitlines():
            lt = line.strip()
            if lt.startswith("{") and lt.endswith("}"):
                try:
                    evt = json.loads(lt)
                    if isinstance(evt, dict):
                        prog = evt.get("progress")
                        if isinstance(prog, dict):
                            cur = prog.get("current")
                            total = prog.get("total")
                            if isinstance(cur, int) and isinstance(total, int) and total > 0:
                                self.progress.setRange(0, total)
                                self.progress.setValue(min(cur, total))
                        stage = evt.get("stage")
                        if isinstance(stage, str) and stage:
                            self.log.append(f"⏩ {stage}")
                        # UI bridge for external/binary engines: handle simple UI requests via JSON lines
                        ui_req = evt.get("ui")
                        if isinstance(ui_req, dict):
                            try:
                                # Helper to emit UI events back to the engine
                                def _emit_event(ev: str, wid: str, payload: dict | None = None):
                                    try:
                                        resp = {"ui": {"type": "event", "id": wid, "event": ev}}
                                        if payload:
                                            resp["ui"]["payload"] = payload
                                        payload_bytes = (json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8")
                                        process.write(payload_bytes)
                                        process.flush()
                                    except Exception:
                                        pass

                                # 1) Message boxes {type,title,text,default_yes,id}
                                msg = ui_req.get("msg_box")
                                if isinstance(msg, dict):
                                    from PySide6.QtWidgets import QMessageBox as _QMB

                                    mtype = str(msg.get("type", "info")).lower()
                                    title = str(msg.get("title", "Information"))
                                    text = str(msg.get("text", ""))
                                    default_yes = bool(msg.get("default_yes", True))
                                    box = _QMB(self)
                                    box.setText(text)
                                    box.setWindowTitle(title)
                                    if mtype in ("warn", "warning"):
                                        box.setIcon(_QMB.Warning)
                                    elif mtype in ("error", "critical"):
                                        box.setIcon(_QMB.Critical)
                                    elif mtype in ("question", "ask"):
                                        box.setIcon(_QMB.Question)
                                    else:
                                        box.setIcon(_QMB.Information)
                                    if mtype in ("question", "ask"):
                                        btns = _QMB.Yes | _QMB.No
                                        box.setStandardButtons(btns)
                                        box.setDefaultButton(_QMB.Yes if default_yes else _QMB.No)
                                    else:
                                        box.setStandardButtons(_QMB.Ok)
                                        box.setDefaultButton(_QMB.Ok)
                                    res = box.exec()
                                    result = (
                                        "yes"
                                        if (mtype in ("question", "ask") and res == _QMB.Yes)
                                        else ("no" if mtype in ("question", "ask") else "ok")
                                    )
                                    resp = {"ui": {"type": "msg_box", "id": msg.get("id"), "result": result}}
                                    try:
                                        payload = (json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8")
                                        process.write(payload)
                                        process.flush()
                                    except Exception:
                                        pass

                                # 2) Dynamic widgets {widget:{op,id,type?,props?}}
                                widget = ui_req.get("widget")
                                if isinstance(widget, dict):
                                    try:
                                        op = widget.get("op")
                                        wid = str(widget.get("id", ""))
                                        if not wid:
                                            raise ValueError("missing widget id")
                                        engine_id = getattr(process, "_engine_id", None)
                                        if not engine_id:
                                            raise RuntimeError("unknown engine id for process")
                                        # Find dynamic area container
                                        cont = None
                                        try:
                                            tabs = getattr(self, "compiler_tabs", None)
                                            if tabs:
                                                for i in range(tabs.count()):
                                                    tw = tabs.widget(i)
                                                    if not tw:
                                                        continue
                                                    c = tw.findChild(QWidget, f"engine_dynamic_area_{engine_id}")
                                                    if c:
                                                        cont = c
                                                        break
                                        except Exception:
                                            cont = None
                                        if cont is None:
                                            raise RuntimeError("dynamic area not found")
                                        if not hasattr(self, "_external_ui_widgets"):
                                            self._external_ui_widgets = {}
                                        widgets = self._external_ui_widgets.setdefault(engine_id, {})

                                        def _apply_props(_w, props: dict):
                                            try:
                                                if "text" in props:
                                                    if isinstance(_w, (QLabel, QPushButton)):
                                                        _w.setText(str(props["text"]))
                                                    elif isinstance(_w, QPlainTextEdit):
                                                        _w.setPlainText(str(props["text"]))
                                                if "placeholder" in props and hasattr(_w, "setPlaceholderText"):
                                                    _w.setPlaceholderText(str(props["placeholder"]))
                                                if "checked" in props and isinstance(_w, QCheckBox):
                                                    _w.setChecked(bool(props["checked"]))
                                                if "enabled" in props:
                                                    _w.setEnabled(bool(props["enabled"]))
                                                if "visible" in props:
                                                    _w.setVisible(bool(props["visible"]))
                                                if "tooltip" in props:
                                                    _w.setToolTip(str(props["tooltip"]))
                                            except Exception:
                                                pass

                                        lay = cont.layout()
                                        if op == "add":
                                            wtype = widget.get("type")
                                            props = widget.get("props") or {}
                                            w = None
                                            if wtype == "label":
                                                w = QLabel()
                                            elif wtype == "button":
                                                w = QPushButton()
                                            elif wtype == "checkbox":
                                                w = QCheckBox()
                                            elif wtype == "text":
                                                w = QPlainTextEdit()
                                            if w is not None:
                                                w.setObjectName(wid)
                                                _apply_props(w, props)
                                                if lay is not None:
                                                    lay.addWidget(w)
                                                widgets[wid] = w
                                                try:
                                                    if isinstance(w, QPushButton):
                                                        w.clicked.connect(
                                                            lambda checked=False, wid=wid: _emit_event("clicked", wid)
                                                        )
                                                    elif isinstance(w, QCheckBox):
                                                        w.stateChanged.connect(
                                                            lambda _s, wid=wid, w=w: _emit_event(
                                                                "changed", wid, {"checked": w.isChecked()}
                                                            )
                                                        )
                                                    elif isinstance(w, QPlainTextEdit):
                                                        w.textChanged.connect(
                                                            lambda wid=wid, w=w: _emit_event(
                                                                "changed", wid, {"text": w.toPlainText()[:5000]}
                                                            )
                                                        )
                                                except Exception:
                                                    pass
                                        elif op == "set":
                                            props = widget.get("props") or {}
                                            w = widgets.get(wid) or cont.findChild(QWidget, wid)
                                            if w is not None:
                                                _apply_props(w, props)
                                        elif op == "remove":
                                            w = widgets.pop(wid, None)
                                            if w is None:
                                                w = cont.findChild(QWidget, wid)
                                            if w is not None:
                                                try:
                                                    if lay is not None:
                                                        lay.removeWidget(w)
                                                except Exception:
                                                    pass
                                                w.deleteLater()
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                except Exception:
                    pass
    except Exception:
        pass
    self.log.append(data)

    # Détection de la fin Nuitka dans le log
    if "Successfully created" in data or "Nuitka: Successfully created" in data:
        # Forcer la barre à 100% et sortir du mode animation
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        # S'assurer que le message est à la fin du log
        lines = data.strip().splitlines()
        for line in lines:
            if "Nuitka: Successfully created" in line or "Successfully created" in line:
                self.log.append(f"<b style='color:green'>{line}</b>")
        # Forcer la terminaison du process si besoin
        if process.state() != QProcess.NotRunning:
            self.log.append(
                "<span style='color:orange;'>ℹ️ Nuitka a signalé la fin de compilation dans le log, mais le process n'est pas terminé. Forçage du kill (arbre) et nettoyage UI...</span>"
            )
            try:
                pidx = int(process.processId())
            except Exception:
                pidx = None
            if pidx:
                _kill_process_tree(pidx, timeout=3.0, log=self.log.append)
            try:
                process.kill()
            except Exception:
                pass
            process.waitForFinished(2000)
            # Nettoyage manuel si le signal finished ne se déclenche pas
            if process in self.processes:
                self.handle_finished(process, 0, QProcess.NormalExit)
    # --- Progression Nuitka (--show-progress) ---
    # Désormais, la barre reste indéterminée pendant toute la compilation
    # (aucune mise à jour de valeur ici)


def handle_stderr(self, process):
    data = process.readAllStandardError().data().decode()
    self.log.append(f"<span style='color:red;'>{data}</span>")


def handle_finished(self, process, exit_code, exit_status):
    # Suppression de la réactivation ici (gérée à la toute fin dans try_start_processes)
    import time

    import psutil

    file = process.file_path
    file_basename = process.file_basename

    # Stop and dispose any timers attached to the process to avoid late callbacks
    try:
        t = getattr(process, "_timeout_timer", None)
        if t:
            try:
                t.stop()
            except Exception:
                pass
            try:
                t.deleteLater()
            except Exception:
                pass
    except Exception:
        pass
    try:
        g = getattr(process, "_grace_kill_timer", None)
        if g:
            try:
                g.stop()
            except Exception:
                pass
            try:
                g.deleteLater()
            except Exception:
                pass
    except Exception:
        pass
    # Cleanup cooperative cancellation sentinel if present
    try:
        cfile = getattr(process, "_cancel_file", None)
        if cfile and os.path.isfile(cfile):
            os.remove(cfile)
    except Exception:
        pass

    # Mesure du temps de compilation
    elapsed = None
    if hasattr(process, "_start_time"):
        elapsed = time.time() - process._start_time
        if not hasattr(self, "_compilation_times"):
            self._compilation_times = {}
        self._compilation_times[file_basename] = elapsed

    # Mesure mémoire (si psutil dispo)
    mem_info = None
    try:
        p = psutil.Process()
        mem_info = p.memory_info().rss / (1024 * 1024)
    except Exception:
        mem_info = None

    if exit_code == 0:
        msg = f"✅ {file_basename} compilé avec succès."
        if elapsed:
            msg += f" Temps de compilation : {elapsed:.2f} secondes."
        if mem_info:
            msg += f" Mémoire utilisée (processus GUI) : {mem_info:.1f} Mo."
        # Suppression de la vérification stricte du dossier/fichier de sortie
        self.log.append(msg + "\n")
        self.log.append(
            "<span style='color:#7faaff;'>ℹ️ Certains messages d’erreur ou de warning peuvent apparaître dans les logs, mais si l’exécutable fonctionne, ils ne sont pas bloquants.</span>\n"
        )
        # Delegate to engine post-success (guarded by env to disable if unstable)
        try:
            import os as _os

            if _os.environ.get("PYCOMPILER_NO_POST_HOOKS") != "1":
                # Output folder opening is handled exclusively by ACASL.
                # Do not call engine.on_success here to avoid engines opening directories.
                pass
        except Exception:
            pass
        # Trace du dernier fichier réussi par moteur (utilisé par ACASL)
        try:
            if not hasattr(self, "_last_success_files"):
                self._last_success_files = {}
            eng_from_proc = getattr(process, "_engine_id", None)
            if eng_from_proc:
                self._last_success_files[eng_from_proc] = file
                self._last_success_engine_id = eng_from_proc
        except Exception:
            pass
    else:
        # Ajout d'un affichage détaillé pour les erreurs inattendues
        error_details = process.readAllStandardError().data().decode()
        self.log.append(
            f"<span style='color:red;'>❌ La compilation de {file_basename} ({file}) a échoué (code {exit_code}).</span>\n"
        )
        if error_details:
            self.log.append(f"<span style='color:red;'>Détails de l'erreur :<br><pre>{error_details}</pre></span>")
        self.show_error_dialog(file_basename, file, exit_code, error_details)

        # Auto-install modules manquants si activé
        if self.opt_auto_install.isChecked():
            self.try_install_missing_modules(process)

    if process in self.processes:
        self.processes.remove(process)
    if file in self.current_compiling:
        self.current_compiling.remove(file)

    # Ne pas toucher à la barre ici : elle sera gérée dans try_start_processes

    # Si toutes les compilations sont terminées, afficher un résumé
    if not self.processes and not self.queue and hasattr(self, "_compilation_times"):
        self.log.append("\n<b>Résum�� des performances :</b>")
        total = 0
        for fname, t in self._compilation_times.items():
            self.log.append(f"- {fname} : {t:.2f} secondes")
            total += t
        self.log.append(f"<b>Temps total de compilation :</b> {total:.2f} secondes\n")

    # Essaye de lancer d’autres compilations dans la file d’attente
    self.try_start_processes()


def try_install_missing_modules(self, process):
    output = process.readAllStandardError().data().decode()
    missing_modules = re.findall(r"No module named '([\w\d_]+)'", output)
    if not hasattr(self, "_already_tried_modules"):
        self._already_tried_modules = set()
    if not hasattr(self, "_install_report"):
        self._install_report = []
    if missing_modules:
        pip_exe = os.path.join(
            self.workspace_dir, "venv", "Scripts" if platform.system() == "Windows" else "bin", "pip"
        )
        all_installed = True
        new_modules = [m for m in missing_modules if m not in self._already_tried_modules]
        if not new_modules:
            self.log.append("❌ Boucle d'installation stoppée : mêmes modules manquants détectés à nouveau.")
            self.log.append("Rapport final :")
            for line in self._install_report:
                self.log.append(line)
            self._already_tried_modules.clear()
            self._install_report.clear()
            return
        for module in new_modules:
            self._already_tried_modules.add(module)
            self.log.append(f"📦 Tentative d'installation du module manquant : {module}")
            try:
                subprocess.run([pip_exe, "install", module], check=True)
                msg = f"✅ Module {module} installé avec succès."
                self.log.append(msg)
                self._install_report.append(msg)
            except Exception as e:
                msg = f"❌ Échec d'installation de {module} : {e}"
                self.log.append(msg)
                self._install_report.append(msg)
                all_installed = False
        # Relancer la compilation après installation, si tout s'est bien passé
        if all_installed:
            reply = QMessageBox.question(
                self,
                self.tr("Relancer la compilation", "Restart build"),
                self.tr(
                    "Des modules manquants ont été installés. Voulez-vous relancer la compilation de ce fichier ?",
                    "Missing modules were installed. Do you want to restart the build for this file?",
                ),
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.log.append("🔁 Relance de la compilation après installation des modules manquants...")
                self.queue.insert(0, process.file_path)
                self.try_start_processes()
            else:
                self.log.append("⏹️ Compilation non relancée après installation des modules. Rapport final :")
                for line in self._install_report:
                    self.log.append(line)
                self._already_tried_modules.clear()
                self._install_report.clear()
        else:
            self.log.append("❌ Certains modules n'ont pas pu être installés. Compilation non relancée.")
            self.log.append("Rapport final :")
            for line in self._install_report:
                self.log.append(line)
            self._already_tried_modules.clear()
            self._install_report.clear()
    else:
        # Si plus de modules manquants, afficher le rapport final
        if hasattr(self, "_install_report") and self._install_report:
            self.log.append("Rapport final :")
            for line in self._install_report:
                self.log.append(line)
            self._already_tried_modules.clear()
            self._install_report.clear()


def show_error_dialog(self, filename, filepath=None, exit_code=None, error_details=None):
    # Mode silencieux : ne rien afficher si la case est cochée
    if hasattr(self, "opt_silent_errors") and self.opt_silent_errors.isChecked():
        return
    dlg = QMessageBox(self)
    dlg.setWindowTitle(self.tr("Erreur de compilation", "Build error"))
    base = self.tr("La compilation de {filename} a échoué.", "Build of {filename} failed.")
    msg = base.format(filename=filename)
    if filepath:
        msg += f"\n{self.tr('Fichier', 'File')} : {filepath}"
    if exit_code is not None:
        msg += "\n{} : {}".format(self.tr("Code d'erreur", "Error code"), exit_code)
    if error_details:
        msg += f"\n\n{self.tr('Détails techniques', 'Technical details')} :\n{error_details}"
    dlg.setText(msg)
    dlg.setIcon(QMessageBox.Icon.Critical)
    dlg.exec()


def cancel_all_compilations(self):
    # Flag to prevent new spawns during hard cancel
    try:
        self._closing = True
    except Exception:
        pass
    # Stop background venv tasks if any
    try:
        if hasattr(self, "venv_manager") and self.venv_manager:
            self.venv_manager.terminate_tasks()
    except Exception:
        pass
    # Stop BCASL (pre-compile) threads/processes explicitly
    try:
        from bcasl.bcasl_loader import ensure_bcasl_thread_stopped

        ensure_bcasl_thread_stopped(self)
    except Exception:
        pass
    errors = []
    # Kill all known QProcesses immediately and their trees
    for process in self.processes[:]:
        try:
            # Cooperative cancel sentinel
            try:
                cfile = getattr(process, "_cancel_file", None)
                if cfile:
                    os.makedirs(os.path.dirname(cfile), exist_ok=True)
                    with open(cfile, "w", encoding="utf-8") as _f:
                        _f.write("1")
            except Exception:
                pass
            # Kill process tree fast
            try:
                pid = int(process.processId())
            except Exception:
                pid = None
            if pid:
                _kill_process_tree(pid, timeout=1.0, log=self.log.append)
            # Ensure QProcess object is stopped as well
            try:
                if process.state() != QProcess.NotRunning:
                    process.kill()
                    process.waitForFinished(1000)
            except Exception:
                pass
        except Exception as e:
            errors.append(str(e))
            self.log.append(f"❌ Erreur lors de l'arrêt d'un process : {e}")
        # Remove from list idempotently
        if process in self.processes:
            try:
                self.processes.remove(process)
            except ValueError:
                pass
    # Last resort: stop ACASL thread and nuke any remaining descendants of our GUI process
    try:
        from acasl import ensure_acasl_thread_stopped

        ensure_acasl_thread_stopped(self)
    except Exception:
        pass
    try:
        _kill_all_descendants(timeout=1.0, log=self.log.append)
    except Exception:
        pass
    # Clear any pending queue and UI state
    self.queue.clear()
    self.current_compiling.clear()
    try:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
    except Exception:
        pass
    self.set_controls_enabled(True)
    if errors:
        self.log.append("❌ Certains processus n'ont pas pu être arrêtés (voir erreurs ci-dessus).")
    else:
        self.log.append("⛔ Toutes les compilations ont été annulées et tous les processus enfants tués.\n")


def build_pyinstaller_command(self, file):
    cmd = ["pyinstaller"]
    if self.opt_onefile.isChecked():
        cmd.append("--onefile")
    if self.opt_windowed.isChecked():
        cmd.append("--windowed")
    if self.opt_noconfirm.isChecked():
        cmd.append("--noconfirm")
    if self.opt_clean.isChecked():
        cmd.append("--clean")
    if self.opt_noupx.isChecked():
        cmd.append("--noupx")
    if self.opt_debug.isChecked():
        cmd.append("--debug")
    if self.icon_path:
        cmd.append(f"--icon={self.icon_path}")
    # Ajout des fichiers/dossiers de données PyInstaller
    if hasattr(self, "pyinstaller_data"):
        for src, dest in self.pyinstaller_data:
            cmd.append(f"--add-data={src}:{dest}")
    # Auto ajout des hooks/plugins via détection
    try:
        auto_map = compute_for_all(self) or {}
        auto_args = auto_map.get("pyinstaller", [])
        if auto_args:
            cmd.extend(auto_args)
    except Exception as e:
        try:
            self.log.append(f"⚠️ Auto-détection PyInstaller: {e}")
        except Exception:
            pass
    cmd.append(file)

    custom_name = self.output_name_input.text().strip()
    if custom_name:
        output_name = custom_name + ".exe" if platform.system() == "Windows" else custom_name
    else:
        base_name = os.path.splitext(os.path.basename(file))[0]
        output_name = base_name + ".exe" if platform.system() == "Windows" else base_name
    cmd += ["--name", output_name]

    # Dossier de sortie
    output_dir = self.output_dir_input.text().strip()
    if output_dir:
        cmd += ["--distpath", output_dir]

    return cmd


def build_nuitka_command(self, file):
    cmd = ["python3", "-m", "nuitka"]
    if self.nuitka_onefile and self.nuitka_onefile.isChecked():
        cmd.append("--onefile")
    if self.nuitka_standalone and self.nuitka_standalone.isChecked():
        cmd.append("--standalone")
    import platform

    if self.nuitka_disable_console and self.nuitka_disable_console.isChecked() and platform.system() == "Windows":
        cmd.append("--windows-disable-console")
    if self.nuitka_show_progress and self.nuitka_show_progress.isChecked():
        cmd.append("--show-progress")
    # Ajout automatique du plugin PySide6 ou PyQt6 si utilisé, mais jamais les deux
    plugins = []
    # Champ nuitka_plugins supprimé: les plugins sont gérés automatiquement
    # Forcer l'ajout de pyside6 ou pyqt6 si importés dans le projet
    found_pyside6 = False
    found_pyqt6 = False
    try:
        with open(file, encoding="utf-8") as f:
            content = f.read()
            if "import PySide6" in content or "from PySide6" in content:
                found_pyside6 = True
            if "import PyQt6" in content or "from PyQt6" in content:
                found_pyqt6 = True
    except Exception:
        pass
    # Ne jamais activer les deux plugins Qt en même temps
    if found_pyside6:
        if "pyqt6" in plugins:
            plugins.remove("pyqt6")
        if "pyside6" not in plugins:
            plugins.append("pyside6")
    elif found_pyqt6:
        if "pyside6" in plugins:
            plugins.remove("pyside6")
        if "pyqt6" not in plugins:
            plugins.append("pyqt6")
    # Si les deux sont dans la liste, n'en garder qu'un (priorité à pyside6)
    if "pyside6" in plugins and "pyqt6" in plugins:
        plugins.remove("pyqt6")
    for plugin in plugins:
        cmd.append(f"--plugin-enable={plugin}")
    # Auto ajout des plugins Nuitka via détection
    try:
        auto_map = compute_for_all(self) or {}
        auto_nuitka_args = auto_map.get("nuitka", [])
        for a in auto_nuitka_args:
            if a not in cmd:
                cmd.append(a)
    except Exception as e:
        try:
            self.log.append(f"⚠️ Auto-détection Nuitka: {e}")
        except Exception:
            pass
    # Nuitka icon: priorité à self.nuitka_icon_path si défini, sinon self.icon_path
    import platform

    if platform.system() == "Windows":
        if hasattr(self, "nuitka_icon_path") and self.nuitka_icon_path:
            cmd.append(f"--windows-icon-from-ico={self.nuitka_icon_path}")
        elif self.icon_path:
            cmd.append(f"--windows-icon-from-ico={self.icon_path}")
    if self.nuitka_output_dir and self.nuitka_output_dir.text().strip():
        cmd.append(f"--output-dir={self.nuitka_output_dir.text().strip()}")
    # Ajout des fichiers de données Nuitka
    if hasattr(self, "nuitka_data_files"):
        for src, dest in self.nuitka_data_files:
            cmd.append(f"--include-data-files={src}={dest}")
    if hasattr(self, "nuitka_data_dirs"):
        for src, dest in self.nuitka_data_dirs:
            cmd.append(f"--include-data-dir={src}={dest}")
    cmd.append(file)
    return cmd
