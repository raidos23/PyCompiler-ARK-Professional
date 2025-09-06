# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

"""
Analyse des dépendances Python pour PyCompiler Pro++.
Inclut la détection, la suggestion et l'installation automatique des modules manquants.

Statut: module utilisable pour une suggestion/installation basique. Les
fonctions d'auto-analyse avancée mentionnées dans la feuille de route ne sont
pas nécessaires à l'exécution et sont désactivées/neutralisées pour éviter tout
impact en production. Les entrées publiques référencées par l'UI (suggest_missing_dependencies)
sont conservées.
"""
# À compléter avec les fonctions et classes liées à l'analyse de dépendances
import os
import platform
import re
import subprocess

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QMessageBox

from .dialogs import ProgressDialog

# NOTE PRODUCTION-HARDENING:
# Les fonctionnalités non finalisées sont encapsulées dans des gardes afin de ne jamais
# faire échouer l'application. Les API publiques restent stables; les chemins non
# implémentés renvoient silencieusement.

# Liste explicite de modules de la bibliothèque standard à exclure
EXCLUDED_STDLIB = {
    "sys",
    "os",
    "re",
    "subprocess",
    "json",
    "math",
    "time",
    "pathlib",
    "typing",
    "itertools",
    "functools",
    "collections",
    "asyncio",
    "importlib",
    "inspect",
    "logging",
    "argparse",
    "dataclasses",
    "unittest",
    "threading",
    "multiprocessing",
    "http",
    "urllib",
    "email",
    "socket",
    "ssl",
    "hashlib",
    "hmac",
    "gzip",
    "bz2",
    "lzma",
    "base64",
    "shutil",
    "tempfile",
    "glob",
    "fnmatch",
    "statistics",
    "pprint",
    "getpass",
    "uuid",
    "enum",
    "contextlib",
    "queue",
    "traceback",
    "warnings",
    "gc",
    "platform",
    "sysconfig",
    "pkgutil",
    "site",
    "venv",
    "sqlite3",
    "tkinter",
}


def _is_stdlib_module(module_name: str) -> bool:
    """
    Détermine si un module appartient à la bibliothèque standard Python.
    Combine une liste d'exclusion explicite et une détection basée sur importlib.util.find_spec.
    """
    try:
        if module_name in EXCLUDED_STDLIB:
            return True
        import importlib.util
        import sys
        import sysconfig

        if module_name in sys.builtin_module_names:
            return True
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            return False
        if getattr(spec, "origin", None) in ("built-in", "frozen"):
            return True
        stdlib_path = sysconfig.get_path("stdlib") or ""
        stdlib_path = os.path.realpath(stdlib_path)
        candidates = []
        if getattr(spec, "origin", None):
            candidates.append(os.path.realpath(spec.origin))
        for loc in spec.submodule_search_locations or []:
            candidates.append(os.path.realpath(loc))
        for c in candidates:
            try:
                if os.path.commonpath([c, stdlib_path]) == stdlib_path:
                    return True
            except Exception:
                # os.path.commonpath peut lever si chemins sur volumes différents
                pass
        return False
    except Exception:
        return False


def suggest_missing_dependencies(self):
    """
    Analyse les fichiers principaux à compiler, détecte les modules importés,
    vérifie leur présence dans le venv, et propose d'installer ceux qui manquent.
    """
    # Vérifie que le workspace ou le venv est bien sélectionné
    if not self.workspace_dir and not self.venv_path_manuel:
        self.log.append(
            "❌ Aucun workspace ou venv sélectionné. Veuillez d'abord sélectionner un dossier workspace ou un venv."
        )
        return
    import ast

    modules = set()
    # Détermine la liste des fichiers à analyser (sélectionnés ou tous les fichiers du projet)
    files = self.selected_files if self.selected_files else self.python_files
    # Exclure les fichiers du venv et les dossiers cachés/__pycache__
    if self.venv_path_manuel:
        venv_dir = os.path.abspath(self.venv_path_manuel)
    else:
        venv_dir = os.path.abspath(os.path.join(self.workspace_dir, "venv"))
    filtered_files = [
        f
        for f in files
        if not os.path.commonpath([os.path.abspath(f), venv_dir]) == venv_dir
        and not any(part.startswith(".") or part == "__pycache__" for part in f.split(os.sep))
    ]
    # Analyse chaque fichier Python pour détecter les imports
    for file in filtered_files:
        try:
            with open(file, encoding="utf-8") as f:
                source = f.read()
                tree = ast.parse(source, filename=file)
            # Imports classiques (import ... / from ... import ...)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        modules.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        modules.add(node.module.split(".")[0])
            # Imports dynamiques via __import__ ou importlib.import_module
            dynamic_imports = re.findall(r"__import__\(['\"]([\w\.]+)['\"]\)", source)
            modules.update([mod.split(".")[0] for mod in dynamic_imports])
            importlib_imports = re.findall(r"importlib\.import_module\(['\"]([\w\.]+)['\"]\)", source)
            modules.update([mod.split(".")[0] for mod in importlib_imports])
        except Exception as e:
            self.log.append(f"⚠️ Erreur analyse dépendances dans {file} : {e}")
    # Exclure les modules standards Python (stdlib)
    import sys
    import sysconfig

    stdlib = set(sys.builtin_module_names)
    # Ajoute les modules de la vraie stdlib (trouvés dans le dossier stdlib)
    stdlib_paths = [sysconfig.get_path("stdlib")]
    try:
        import pkgutil

        for finder, name, ispkg in pkgutil.iter_modules(stdlib_paths):
            stdlib.add(name)
    except Exception:
        pass
    # Exclure les modules internes du projet (présents dans le workspace)
    internal_modules = set()
    for f in filtered_files:
        base = os.path.splitext(os.path.basename(f))[0]
        internal_modules.add(base)
    # Liste des modules à vérifier (hors standard et hors modules internes)
    suggestions = [m for m in modules if not _is_stdlib_module(m) and m not in internal_modules]
    # Alerte spéciale pour tkinter (std lib optionnelle non installable via pip)
    try:
        import importlib.util as _il_util

        if "tkinter" in modules:
            if _il_util.find_spec("tkinter") is None:
                msg = (
                    "Le module tkinter n'est pas disponible dans votre environnement Python. "
                    "tkinter fait partie de la bibliothèque standard mais nécessite des paquets système et ne s'installe pas via pip.\n\n"
                    "Installez-le avec votre gestionnaire de paquets:\n"
                    "- Ubuntu/Debian: sudo apt install python3-tk\n"
                    "- Fedora: sudo dnf install python3-tkinter\n"
                    "- Arch: sudo pacman -S tk\n"
                    "- macOS: brew install tcl-tk (puis réinstallez Python avec le support Tk)\n"
                    "- Windows: réinstallez Python en incluant Tcl/Tk"
                )
                self.log.append(f"ℹ️ {msg}")
                try:
                    QMessageBox.information(self, self.tr("tkinter manquant", "Missing tkinter"), msg)
                except Exception:
                    pass
    except Exception:
        pass
    if not suggestions:
        self.log.append("✅ Aucun module externe à installer détecté.")
        return
    # Vérifie la présence des modules dans le venv (via pip show)
    pip_name = "pip.exe" if platform.system() == "Windows" else "pip"
    if self.venv_path_manuel:
        pip_exe = os.path.join(self.venv_path_manuel, "Scripts" if platform.system() == "Windows" else "bin", pip_name)
    else:
        pip_exe = os.path.join(
            self.workspace_dir, "venv", "Scripts" if platform.system() == "Windows" else "bin", pip_name
        )
    # Détermine la stratégie pip: binaire du venv si présent, sinon 'python -m pip'
    pip_program = pip_exe
    pip_prefix = []
    try:
        if not os.path.isfile(pip_exe):
            # Fallback vers 'python -m pip'
            pip_program = sys.executable
            pip_prefix = ["-m", "pip"]
            try:
                self.log.append(
                    "ℹ️ pip du venv introuvable; utilisation de 'python -m pip' pour la vérification des modules."
                )
            except Exception:
                pass
    except Exception:
        pip_program = sys.executable
        pip_prefix = ["-m", "pip"]
    not_installed = []
    for module in suggestions:
        try:
            cmd = [pip_program, *pip_prefix, "show", module]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                not_installed.append(module)
        except Exception as e:
            self.log.append(f"⚠️ Erreur lors de la vérification du module {module} : {e}")
    # Si des modules sont manquants, propose l'installation automatique
    if not_installed:
        self.log.append("❗ Modules manquants dans le venv : " + ", ".join(sorted(not_installed)))
        # Demande à l'utilisateur s'il souhaite installer automatiquement les modules manquants
        reply = QMessageBox.question(
            self,
            self.tr("Installer les dépendances", "Install dependencies"),
            self.tr(
                "Installer automatiquement les modules manquants ?\n{mods}",
                "Automatically install missing modules?\n{mods}",
            ).format(mods=", ".join(not_installed)),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._dep_install_index = 0
            self._dep_install_list = not_installed
            # Programme pip pour QProcess: si pip du venv existe, l'utiliser; sinon python -m pip
            try:
                self._dep_pip_program = pip_program
                self._dep_pip_prefix = list(pip_prefix)
            except Exception:
                self._dep_pip_program = sys.executable
                self._dep_pip_prefix = ["-m", "pip"]
            self.dep_progress_dialog = ProgressDialog(
                self.tr("Installation des dépendances", "Installing dependencies"), self
            )
            self.dep_progress_dialog.set_message(
                self.tr("Installation de {m}...", "Installing {m}...").format(m=not_installed[0])
            )
            self.dep_progress_dialog.set_progress(0, len(not_installed))
            self.dep_progress_dialog.show()
            self._install_next_dependency()
    else:
        self.log.append("✅ Tous les modules nécessaires sont déjà installés dans le venv.")


# Installation automatique des dépendances manquantes (récursif)
def _install_next_dependency(self):
    # Si tous les modules ont été installés, termine le processus
    if self._dep_install_index >= len(self._dep_install_list):
        self.dep_progress_dialog.set_message(self.tr("Installation terminée.", "Installation completed."))
        self.dep_progress_dialog.set_progress(len(self._dep_install_list), len(self._dep_install_list))
        self.dep_progress_dialog.close()
        self.log.append("✅ Tous les modules manquants ont été installés.")
        return
    module = self._dep_install_list[self._dep_install_index]
    msg = f"Installation de {module}... ({self._dep_install_index+1}/{len(self._dep_install_list)})"
    self.dep_progress_dialog.set_message(msg)
    self.dep_progress_dialog.progress.setRange(0, 0)  # indéterminé pendant l'installation
    process = QProcess(self)
    # Utilise le programme et préfixe déterminés (pip du venv ou 'python -m pip')
    try:
        import sys as _sys

        default_prog = _sys.executable
    except Exception:
        default_prog = "python"
    program = getattr(self, "_dep_pip_program", None) or default_prog
    prefix = list(getattr(self, "_dep_pip_prefix", ["-m", "pip"]))
    process.setProgram(program)
    process.setArguments(prefix + ["install", module])
    process.readyReadStandardOutput.connect(lambda: self._on_dep_pip_output(process))
    process.readyReadStandardError.connect(lambda: self._on_dep_pip_output(process, error=True))
    process.finished.connect(lambda code, status: self._on_dep_pip_finished(process, code, status))
    process.start()


# Affiche la sortie de pip dans la ProgressDialog et les logs
def _on_dep_pip_output(self, process, error=False):
    data = process.readAllStandardError().data().decode() if error else process.readAllStandardOutput().data().decode()
    if hasattr(self, "dep_progress_dialog") and self.dep_progress_dialog:
        lines = data.strip().splitlines()
        if lines:
            self.dep_progress_dialog.set_message(lines[-1])
    self.log.append(data)


# Callback après l'installation d'un module (pip)
def _on_dep_pip_finished(self, process, code, status):
    module = self._dep_install_list[self._dep_install_index]
    if code == 0:
        self.log.append(f"✅ {module} installé.")
    else:
        self.log.append(f"❌ Erreur installation {module} (code {code})")
    # Met à jour la progression globale
    self._dep_install_index += 1
    self.dep_progress_dialog.progress.setRange(0, len(self._dep_install_list))
    self.dep_progress_dialog.set_progress(self._dep_install_index, len(self._dep_install_list))
    self._install_next_dependency()
