

from PySide6.QtWidgets import QMessageBox
import os

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
                if (
                    "if __name__ == '__main__'" in content
                    or 'if __name__ == "__main__"' in content
                ):
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
        self.compiler_tabs.setEnabled(
            False
        )  # Désactive les onglets au début de la compilation
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
            files = [
                f
                for f in self.python_files
                if os.path.basename(f) in ("main.py", "app.py")
            ]
            files_ok = [f for f in files if is_executable_script(f)]
            self.queue = [(f, True) for f in files_ok]
            total_files = len(files_ok)
            if not files_ok:
                self.log.append(
                    "⚠️ Aucun main.py ou app.py exécutable trouvé dans le workspace.\n"
                )
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


def compile_all(self):
    import os

    # Garde-fous avant toute opération
    if self.processes:
        QMessageBox.warning(
            self,
            self.tr("Attention", "Warning"),
            self.tr(
                "Des compilations sont déjà en cours.", "Builds are already running."
            ),
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
        from bcasl.Loader import run_pre_compile_async as _run_bcasl_async

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

                    self.log.append(
                        f"⚠️ Exception _after_bcasl: {_e}\n{_tb.format_exc()}\n"
                    )
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
                if (
                    "if __name__ == '__main__'" in content
                    or 'if __name__ == "__main__"' in content
                ):
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
        self.compiler_tabs.setEnabled(
            False
        )  # Désactive les onglets au début de la compilation
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
            files = [
                f
                for f in self.python_files
                if os.path.basename(f) in ("main.py", "app.py")
            ]
            files_ok = [f for f in files if is_executable_script(f)]
            self.queue = [(f, True) for f in files_ok]
            total_files = len(files_ok)
            if not files_ok:
                self.log.append(
                    "⚠️ Aucun main.py ou app.py exécutable trouvé dans le workspace.\n"
                )
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