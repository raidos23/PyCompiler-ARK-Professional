# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

import asyncio
import os
import sys

from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from Core import i18n as _i18n


def _detect_system_color_scheme() -> str:
    """
    Retourne "dark" ou "light" selon le thème système détecté.
    - Windows: registre AppsUseLightTheme (0 = dark, 1 = light)
    - macOS: defaults read -g AppleInterfaceStyle (Dark = dark)
    - Linux (GNOME/KDE): gsettings ou kdeglobals, repli sur GTK_THEME
    En cas d'échec, renvoie "light".
    """
    try:
        import os as _os
        import platform
        import subprocess

        sysname = platform.system()
        # Windows
        if sysname == "Windows":
            try:
                out = subprocess.run(
                    [
                        "reg",
                        "query",
                        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                        "/v",
                        "AppsUseLightTheme",
                    ],
                    capture_output=True,
                    text=True,
                )
                if out.returncode == 0 and out.stdout:
                    # Value like: REG_DWORD    0x1 (light) or 0x0 (dark)
                    val = out.stdout.lower()
                    if "0x0" in val or " 0x0\n" in val:
                        return "dark"
                    return "light"
            except Exception:
                pass
            return "light"
        # macOS
        if sysname == "Darwin":
            try:
                out = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True,
                    text=True,
                )
                if out.returncode == 0 and "dark" in out.stdout.strip().lower():
                    return "dark"
            except Exception:
                pass
            return "light"
        # Linux (GNOME/KDE)
        if sysname == "Linux":
            # GNOME 42+: color-scheme
            try:
                out = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                    capture_output=True,
                    text=True,
                )
                if out.returncode == 0 and "prefer-dark" in out.stdout:
                    return "dark"
            except Exception:
                pass
            # GNOME: gtk-theme contains "dark"
            try:
                out = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                    capture_output=True,
                    text=True,
                )
                if out.returncode == 0 and "dark" in out.stdout.lower():
                    return "dark"
            except Exception:
                pass
            # KDE: kdeglobals
            try:
                kdeglobals = _os.path.expanduser("~/.config/kdeglobals")
                if _os.path.isfile(kdeglobals):
                    with open(kdeglobals, encoding="utf-8", errors="ignore") as f:
                        txt = f.read().lower()
                    if "colorscheme" in txt and "dark" in txt:
                        return "dark"
            except Exception:
                pass
            # Env GTK_THEME
            try:
                gtk_theme = _os.environ.get("GTK_THEME", "").lower()
                if gtk_theme and "dark" in gtk_theme:
                    return "dark"
            except Exception:
                pass
            return "light"
        # Autres systèmes
        return "light"
    except Exception:
        return "light"


def init_ui(self):
    loader = QUiLoader()
    ui_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "ui", "ui_design.ui"
    )
    ui_file = QFile(os.path.abspath(ui_path))
    ui_file.open(QFile.ReadOnly)
    self.ui = loader.load(ui_file, self)
    ui_file.close()

    # Supprimer tous les styles inline du .ui pour laisser le style global s'appliquer
    try:
        from PySide6.QtWidgets import QWidget

        widgets = [self.ui] + self.ui.findChildren(QWidget)
        for w in widgets:
            if hasattr(w, "styleSheet") and w.styleSheet():
                w.setStyleSheet("")
    except Exception:
        pass

    # Charger le thème (light/dark) selon préférence ou système, avec repli
    try:
        pref = getattr(self, "theme", "System")
        apply_theme(self, pref)
        # Après application, sauvegarder la préférence pour persistance immédiate
        try:
            if hasattr(self, "save_preferences"):
                self.save_preferences()
        except Exception:
            pass
    except Exception as _e:
        # En cas d'échec de chargement du style, on loggue sans casser l'UI
        try:
            if hasattr(self, "log") and self.log:
                self.log.append(f"⚠️ Échec application du thème: {_e}")
        except Exception:
            pass

    # Remplacer le layout principal par celui du .ui
    layout = QVBoxLayout(self)
    layout.addWidget(self.ui)
    self.setLayout(layout)

    # Récupérer les widgets depuis l'UI chargée
    self.sidebar_logo = self.ui.findChild(QLabel, "sidebar_logo")
    # Forcer la suppression de toute bordure sur le logo, quel que soit le thème
    try:
        if self.sidebar_logo:
            self.sidebar_logo.setStyleSheet("border: none; background: transparent;")
    except Exception:
        pass
    self.btn_select_folder = self.ui.findChild(QPushButton, "btn_select_folder")
    self.venv_button = self.ui.findChild(QPushButton, "venv_button")
    self.venv_label = self.ui.findChild(QLabel, "venv_label")
    self.label_folder = self.ui.findChild(QLabel, "label_folder")
    self.label_workspace_section = self.ui.findChild(QLabel, "label_workspace_section")
    self.label_files_section = self.ui.findChild(QLabel, "label_files_section")
    self.label_logs_section = self.ui.findChild(QLabel, "label_logs_section")
    self.file_list = self.ui.findChild(QListWidget, "file_list")
    # Afficher le logo dans la sidebar (chemin absolu depuis le dossier projet)
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication

    project_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    # Choose logo based on effective theme from QSS when available; fallback to system scheme
    try:
        app = QApplication.instance()
        css = app.styleSheet() if app else ""
        if css:
            eff_mode = "dark" if _is_qss_dark(css) else "light"
        else:
            eff_mode = _detect_system_color_scheme()
    except Exception:
        eff_mode = "light"
    candidates = [
        (
            os.path.join(project_dir, "logo", "sidebar_logo2.png")
            if eff_mode == "dark"
            else os.path.join(project_dir, "logo", "sidebar_logo.png")
        ),
        os.path.join(project_dir, "logo", "sidebar_logo.png"),
        os.path.join(project_dir, "logo", "sidebar_logo2.png"),
    ]
    logo_path = None
    for p in candidates:
        if os.path.exists(p):
            logo_path = p
            break
    if logo_path:
        pixmap = QPixmap(logo_path)
        target_size = 200
        self.sidebar_logo.setPixmap(
            pixmap.scaled(
                target_size,
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.sidebar_logo.setToolTip("PyCompiler")
        try:
            self.sidebar_logo.setContentsMargins(13, 0, 0, 0)
        except Exception:
            pass
    else:
        self.sidebar_logo.setText("PyCompiler")
        try:
            self.sidebar_logo.setContentsMargins(12, 0, 0, 0)
        except Exception:
            pass
    self.btn_select_files = self.ui.findChild(QPushButton, "btn_select_files")
    self.btn_remove_file = self.ui.findChild(QPushButton, "btn_remove_file")
    self.btn_build_all = self.ui.findChild(QPushButton, "btn_build_all")
    self.btn_cancel_all = self.ui.findChild(QPushButton, "btn_cancel_all")
    self.btn_export_config = self.ui.findChild(QPushButton, "btn_export_config")
    self.btn_import_config = self.ui.findChild(QPushButton, "btn_import_config")
    self.btn_help = self.ui.findChild(QPushButton, "btn_help")
    self.btn_suggest_deps = self.ui.findChild(QPushButton, "btn_suggest_deps")
    self.btn_api_loader = self.ui.findChild(QPushButton, "btn_api_loader")
    self.btn_acasl_loader = self.ui.findChild(QPushButton, "btn_acasl_loader")
    self.btn_select_icon = self.ui.findChild(QPushButton, "btn_select_icon")
    self.btn_show_stats = self.ui.findChild(QPushButton, "btn_show_stats")
    self.select_lang = self.ui.findChild(QPushButton, "select_lang")
    self.select_theme = self.ui.findChild(QPushButton, "select_theme")
    if self.select_theme:
        try:
            self.select_theme.clicked.connect(lambda: show_theme_dialog(self))
        except Exception:
            pass
    # Tooltips pour les boutons principaux (après initialisation)
    if self.btn_select_folder:
        self.btn_select_folder.setToolTip(
            "Sélectionner le dossier de travail (workspace) contenant vos scripts Python."
        )
    if self.btn_select_files:
        self.btn_select_files.setToolTip(
            "Ajouter manuellement des fichiers Python à compiler dans le workspace."
        )
    if self.btn_build_all:
        self.btn_build_all.setToolTip(
            "Lancer la compilation de tous les fichiers sélectionnés."
        )
    if self.btn_export_config:
        self.btn_export_config.setToolTip(
            "Exporter la configuration actuelle dans un fichier JSON."
        )
    if self.btn_import_config:
        self.btn_import_config.setToolTip(
            "Importer une configuration depuis un fichier JSON."
        )
    if self.btn_cancel_all:
        self.btn_cancel_all.setToolTip("Annuler toutes les compilations en cours.")
    if self.btn_remove_file:
        self.btn_remove_file.setToolTip(
            "Supprimer le ou les fichiers sélectionnés de la liste."
        )
        self.btn_remove_file.clicked.connect(self.remove_selected_file)
    if self.btn_select_icon:
        self.btn_select_icon.setToolTip(
            "Choisir une icône (.ico) pour l'exécutable généré (Windows uniquement)."
        )
        import platform

        self.btn_select_icon.setEnabled(platform.system() == "Windows")
    if self.btn_help:
        self.btn_help.setToolTip("Afficher l'aide et les informations sur le logiciel.")
    if self.btn_api_loader:
        self.btn_api_loader.setToolTip(
            "Configurer les plugins API (BCASL) à exécuter avant la compilation."
        )
    if self.btn_acasl_loader:
        self.btn_acasl_loader.setToolTip(
            "Configurer les plugins ACASL (post‑compilation) à exécuter après la compilation."
        )
    if self.venv_button:
        self.venv_button.setToolTip(
            "Sélectionner manuellement un dossier venv à utiliser pour la compilation."
        )
    if self.btn_suggest_deps:
        self.btn_suggest_deps.setToolTip(
            "Analyser les dépendances Python manquantes dans le projet."
        )
    self.opt_onefile = self.ui.findChild(QCheckBox, "opt_onefile")
    self.opt_windowed = self.ui.findChild(QCheckBox, "opt_windowed")
    self.opt_noconfirm = self.ui.findChild(QCheckBox, "opt_noconfirm")
    self.opt_clean = self.ui.findChild(QCheckBox, "opt_clean")
    self.opt_noupx = self.ui.findChild(QCheckBox, "opt_noupx")
    self.opt_main_only = self.ui.findChild(QCheckBox, "opt_main_only")
    self.btn_select_icon = self.ui.findChild(QPushButton, "btn_select_icon")
    self.opt_debug = self.ui.findChild(QCheckBox, "opt_debug")
    self.opt_auto_install = self.ui.findChild(QCheckBox, "opt_auto_install")
    if self.opt_auto_install is None:
        try:
            from PySide6.QtWidgets import QCheckBox as _QCB

            self.opt_auto_install = _QCB()
            self.opt_auto_install.setObjectName("opt_auto_install")
        except Exception:
            self.opt_auto_install = None
    self.opt_silent_errors = self.ui.findChild(QCheckBox, "opt_silent_errors")
    if self.opt_silent_errors is None:
        try:
            from PySide6.QtWidgets import QCheckBox as _QCB

            self.opt_silent_errors = _QCB()
            self.opt_silent_errors.setObjectName("opt_silent_errors")
        except Exception:
            self.opt_silent_errors = None
    # Onglets compilateur (correction robuste)
    from PySide6.QtWidgets import QTabWidget, QWidget

    # Ensure engines package is imported to register engines dynamically
    try:
        pass  # triggers discovery
    except Exception:
        pass
    self.compiler_tabs = self.ui.findChild(QTabWidget, "compiler_tabs")
    self.tab_pyinstaller = self.ui.findChild(QWidget, "tab_pyinstaller")
    self.tab_nuitka = self.ui.findChild(QWidget, "tab_nuitka")
    # Lier dynamiquement les onglets des moteurs plug-and-play
    try:
        import Core.engines_loader as engines_loader

        engines_loader.registry.bind_tabs(self)
    except Exception:
        pass
    # Widgets Nuitka (doit être AVANT update_compiler_options_enabled)
    self.nuitka_onefile = (
        self.tab_nuitka.findChild(QCheckBox, "nuitka_onefile")
        if self.tab_nuitka
        else None
    )
    self.nuitka_standalone = (
        self.tab_nuitka.findChild(QCheckBox, "nuitka_standalone")
        if self.tab_nuitka
        else None
    )
    self.nuitka_disable_console = (
        self.tab_nuitka.findChild(QCheckBox, "nuitka_disable_console")
        if self.tab_nuitka
        else None
    )
    if self.nuitka_disable_console:
        self.nuitka_disable_console.setToolTip(
            "Désactiver la console Windows (--windows-disable-console). Option Windows uniquement."
        )
        import platform

        _is_win = platform.system() == "Windows"
        self.nuitka_disable_console.setEnabled(_is_win)
        if not _is_win:
            self.nuitka_disable_console.setChecked(False)
    self.nuitka_show_progress = (
        self.tab_nuitka.findChild(QCheckBox, "nuitka_show_progress")
        if self.tab_nuitka
        else None
    )
    if self.nuitka_show_progress:
        self.nuitka_show_progress.setChecked(True)
    self.nuitka_plugins = None  # Champ supprimé de l'UI; plugins gérés automatiquement
    self.nuitka_output_dir = (
        self.tab_nuitka.findChild(QLineEdit, "nuitka_output_dir")
        if self.tab_nuitka
        else None
    )
    self.nuitka_add_data = (
        self.tab_nuitka.findChild(QPushButton, "nuitka_add_data")
        if self.tab_nuitka
        else None
    )
    self.nuitka_data_files = []  # Liste des tuples (source, dest)
    if self.nuitka_add_data:
        self.nuitka_add_data.clicked.connect(self.add_nuitka_data_file)
    self.btn_nuitka_icon = (
        self.tab_nuitka.findChild(QPushButton, "btn_nuitka_icon")
        if self.tab_nuitka
        else None
    )
    import platform

    if self.btn_nuitka_icon:
        self.btn_nuitka_icon.setToolTip(
            "Choisir une icône (.ico) pour l'exécutable Nuitka (Windows uniquement)."
        )
        self.btn_nuitka_icon.setEnabled(platform.system() == "Windows")
        self.btn_nuitka_icon.clicked.connect(self.select_nuitka_icon)
    # Tooltips pour les cases à cocher principales
    if self.opt_onefile:
        self.opt_onefile.setToolTip("Générer un exécutable unique (mode onefile).")
    if self.opt_windowed:
        self.opt_windowed.setToolTip(
            "Ne pas ouvrir de console lors de l'exécution (mode fenêtré, --windowed)."
        )
        import platform

        is_win = platform.system() == "Windows"
        self.opt_windowed.setEnabled(is_win)
        if not is_win:
            self.opt_windowed.setChecked(False)
    if self.opt_noconfirm:
        self.opt_noconfirm.setToolTip(
            "Ne pas demander de confirmation pour écraser les fichiers existants (--noconfirm)."
        )
    if self.opt_clean:
        self.opt_clean.setToolTip(
            "Nettoyer les fichiers temporaires avant compilation (--clean)."
        )
    if self.opt_noupx:
        self.opt_noupx.setToolTip(
            "Ne pas utiliser UPX pour compresser l'exécutable (--noupx)."
        )
    if self.opt_main_only:
        self.opt_main_only.setToolTip(
            "Compiler uniquement les fichiers main.py ou app.py du projet."
        )
    if self.opt_debug:
        self.opt_debug.setToolTip(
            "Activer le mode debug (--debug) pour obtenir plus de logs."
        )
    if self.opt_auto_install:
        self.opt_auto_install.setToolTip(
            "Installer automatiquement les modules Python manquants détectés."
        )
    if self.opt_silent_errors:
        self.opt_silent_errors.setToolTip(
            "Ne pas afficher de boîte d'erreur graphique (mode silencieux)."
        )
    # self.custom_args supprimé (widget inutilisé)
    # self.custom_args supprimé (widget inutilisé)
    self.btn_build_all = self.ui.findChild(QPushButton, "btn_build_all")
    self.btn_cancel_all = self.ui.findChild(QPushButton, "btn_cancel_all")
    self.progress = self.ui.findChild(QProgressBar, "progress")
    self.log = self.ui.findChild(QTextEdit, "log")
    self.pyinstaller_add_data = (
        self.tab_pyinstaller.findChild(QPushButton, "pyinstaller_add_data")
        if self.tab_pyinstaller
        else None
    )
    self.pyinstaller_data = []  # Liste des tuples (source, dest)
    if self.pyinstaller_add_data:
        self.pyinstaller_add_data.clicked.connect(self.add_pyinstaller_data)
    self.output_dir_input = (
        self.tab_pyinstaller.findChild(QLineEdit, "output_dir_input")
        if self.tab_pyinstaller
        else None
    )

    def find_widget_recursive(parent, widget_type, name):
        for child in parent.findChildren(widget_type):
            if child.objectName() == name:
                return child
        for child in parent.children():
            if hasattr(child, "findChildren"):
                result = find_widget_recursive(child, widget_type, name)
                if result:
                    return result
        return None

    self.btn_browse_output_dir = (
        find_widget_recursive(
            self.tab_pyinstaller, QPushButton, "btn_browse_output_dir"
        )
        if self.tab_pyinstaller
        else None
    )
    if self.output_dir_input:
        self.output_dir_input.setToolTip(
            "Dossier de sortie pour les exécutables générés (option --distpath de PyInstaller). Laisser vide pour utiliser le dossier par défaut 'dist'."
        )
    if self.btn_browse_output_dir and self.output_dir_input:

        def browse_output_dir():
            from PySide6.QtWidgets import QFileDialog

            # Utilise self comme parent pour garantir l'affichage du dialog
            dir_path = QFileDialog.getExistingDirectory(
                self, "Choisir le dossier de sortie", ""
            )
            if dir_path:
                self.output_dir_input.setText(dir_path)

        self.btn_browse_output_dir.clicked.connect(browse_output_dir)
    if self.output_dir_input:
        try:
            self.output_dir_input.textChanged.connect(self.update_command_preview)
            self.output_dir_input.textChanged.connect(self.save_preferences)
        except Exception:
            pass
    self.btn_export_config = self.ui.findChild(QPushButton, "btn_export_config")
    self.btn_import_config = self.ui.findChild(QPushButton, "btn_import_config")
    self.btn_help = self.ui.findChild(QPushButton, "btn_help")
    self.output_name_input = (
        QLineEdit()
    )  # Si non présent dans le .ui, à ajouter dans le .ui pour conformité

    # Connecter les signaux
    self.btn_select_folder.clicked.connect(self.select_workspace)
    self.venv_button.clicked.connect(self.select_venv_manually)
    self.btn_select_files.clicked.connect(self.select_files_manually)
    self.btn_remove_file.clicked.connect(self.remove_selected_file)
    self.opt_main_only.stateChanged.connect(self.on_main_only_changed)
    self.btn_select_icon.clicked.connect(self.select_icon)
    self.btn_build_all.clicked.connect(self.compile_all)
    self.btn_cancel_all.clicked.connect(self.cancel_all_compilations)
    self.btn_export_config.clicked.connect(self.export_config)
    self.btn_import_config.clicked.connect(self.import_config)

    from acasl import open_ac_loader_dialog
    from bcasl import open_bc_loader_dialog

    self.btn_api_loader.clicked.connect(lambda: open_bc_loader_dialog(self))
    self.btn_acasl_loader.clicked.connect(lambda: open_ac_loader_dialog(self))

    if self.btn_help:
        self.btn_help.clicked.connect(self.show_help_dialog)
    if self.btn_show_stats:
        self.btn_show_stats.setToolTip(
            "Afficher les statistiques de compilation (temps, nombre de fichiers, mémoire)"
        )
        self.btn_show_stats.clicked.connect(self.show_statistics)
    for checkbox in [
        self.opt_onefile,
        self.opt_windowed,
        self.opt_noconfirm,
        self.opt_clean,
        self.opt_noupx,
        self.opt_main_only,
        self.opt_debug,
        self.opt_auto_install,
        self.opt_silent_errors,
    ]:
        if not checkbox:
            continue
        checkbox.stateChanged.connect(self.update_command_preview)
        try:
            checkbox.stateChanged.connect(self.save_preferences)
        except Exception:
            pass
    # self.custom_args supprimé (widget inutilisé)
    if self.select_lang:
        self.select_lang.setToolTip("Choisir la langue de l'interface utilisateur.")
        try:
            self.select_lang.clicked.connect(lambda: show_language_dialog(self))
        except Exception:
            pass

    # Désactivation croisée des options selon le moteur actif
    import platform

    def update_compiler_options_enabled():
        try:
            import Core.engines_loader as engines_loader

            idx = self.compiler_tabs.currentIndex()
            engine_id = engines_loader.registry.get_engine_for_tab(idx) or (
                "pyinstaller" if idx == 0 else "nuitka"
            )
        except Exception:
            engine_id = (
                "pyinstaller" if self.compiler_tabs.currentIndex() == 0 else "nuitka"
            )
        if engine_id == "pyinstaller":
            for w in [
                self.opt_onefile,
                self.opt_windowed,
                self.opt_noconfirm,
                self.opt_clean,
                self.opt_noupx,
                self.opt_main_only,
                self.opt_debug,
                self.opt_auto_install,
                self.opt_silent_errors,
            ]:
                if not w:
                    continue
                if w is self.opt_windowed:
                    is_win = platform.system() == "Windows"
                    w.setEnabled(is_win)
                    if not is_win:
                        w.setChecked(False)
                else:
                    w.setEnabled(True)
            if self.btn_select_icon:
                self.btn_select_icon.setEnabled(platform.system() == "Windows")
            for w in [
                self.nuitka_onefile,
                self.nuitka_standalone,
                self.nuitka_disable_console,
                self.nuitka_show_progress,
                self.nuitka_output_dir,
            ]:
                if w:
                    w.setEnabled(False)
        elif engine_id == "nuitka":
            for w in [
                self.opt_onefile,
                self.opt_windowed,
                self.opt_noconfirm,
                self.opt_clean,
                self.opt_noupx,
                self.opt_main_only,
                self.opt_debug,
                self.opt_auto_install,
                self.opt_silent_errors,
                self.btn_select_icon,
            ]:
                if w:
                    w.setEnabled(False)
            for w in [
                self.nuitka_onefile,
                self.nuitka_standalone,
                self.nuitka_disable_console,
                self.nuitka_show_progress,
                self.nuitka_output_dir,
            ]:
                if not w:
                    continue
                if w is self.nuitka_disable_console:
                    is_win = platform.system() == "Windows"
                    w.setEnabled(is_win)
                    if not is_win:
                        w.setChecked(False)
                else:
                    w.setEnabled(True)
        else:
            # Tout autre moteur (ex: binaire externe): désactiver options spécifiques et laisser la compilation gérée par le moteur
            for w in [
                self.opt_onefile,
                self.opt_windowed,
                self.opt_noconfirm,
                self.opt_clean,
                self.opt_noupx,
                self.opt_main_only,
                self.opt_debug,
                self.opt_auto_install,
                self.opt_silent_errors,
                self.btn_select_icon,
            ]:
                if w:
                    w.setEnabled(False)
            for w in [
                self.nuitka_onefile,
                self.nuitka_standalone,
                self.nuitka_disable_console,
                self.nuitka_show_progress,
                self.nuitka_output_dir,
            ]:
                if w:
                    w.setEnabled(False)

    self.compiler_tabs.currentChanged.connect(update_compiler_options_enabled)
    update_compiler_options_enabled()

    # Exclusivité onefile/standalone pour Nuitka
    if self.nuitka_onefile and self.nuitka_standalone:

        def nuitka_onefile_changed(state):
            if state:
                self.nuitka_standalone.setChecked(False)
                self.nuitka_standalone.setEnabled(False)
            else:
                self.nuitka_standalone.setEnabled(True)

        def nuitka_standalone_changed(state):
            if state:
                self.nuitka_onefile.setChecked(False)
                self.nuitka_onefile.setEnabled(False)
            else:
                self.nuitka_onefile.setEnabled(True)

        self.nuitka_onefile.stateChanged.connect(nuitka_onefile_changed)
        self.nuitka_standalone.stateChanged.connect(nuitka_standalone_changed)

    # Message d'aide contextuel à la première utilisation
    if not self.workspace_dir:
        self.log.append(
            "Astuce : Commencez par sélectionner un dossier workspace, puis ajoutez vos fichiers Python à compiler. Configurez les options selon vos besoins et cliquez sur Compiler."
        )

    self.btn_suggest_deps = self.ui.findChild(QPushButton, "btn_suggest_deps")
    if self.btn_suggest_deps:
        self.btn_suggest_deps.clicked.connect(self.suggest_missing_dependencies)

    # Mode silencieux actif par défaut (forcer activé même si le widget n'existe pas)
    try:
        if self.opt_silent_errors:
            self.opt_silent_errors.setChecked(True)
    except Exception:
        pass
    # Auto-install actif par défaut (forcer activé même si le widget n'existe pas)
    try:
        if self.opt_auto_install:
            self.opt_auto_install.setChecked(True)
    except Exception:
        pass
    # Apply initial language from preference using async i18n
    try:
        lang_pref = getattr(self, "language", "System")
        tr = asyncio.run(_i18n.get_translations(lang_pref))
        _apply_translations(self, tr)
        try:
            setattr(self, "_tr", tr)
        except Exception:
            pass
    except Exception:
        pass


def add_pyinstaller_data(self):
    import os

    from PySide6.QtCore import QDir
    from PySide6.QtWidgets import QFileDialog, QInputDialog

    choix, ok = QInputDialog.getItem(
        self,
        "Type d'inclusion",
        "Inclure un fichier ou un dossier ?",
        ["Fichier", "Dossier"],
        0,
        False,
    )
    if not ok:
        return
    if choix == "Fichier":
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier à inclure avec PyInstaller"
        )
        if file_path:
            dest, ok = QInputDialog.getText(
                self,
                "Chemin de destination",
                "Chemin de destination dans l'exécutable :",
                text=os.path.basename(file_path),
            )
            if ok and dest:
                self.pyinstaller_data.append((file_path, dest))
                if hasattr(self, "log"):
                    self.log.append(
                        f"Fichier ajouté à PyInstaller : {file_path} => {dest}"
                    )
    elif choix == "Dossier":
        dir_path = QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier à inclure avec PyInstaller", QDir.homePath()
        )
        if dir_path:
            dest, ok = QInputDialog.getText(
                self,
                "Chemin de destination",
                "Chemin de destination dans l'exécutable :",
                text=os.path.basename(dir_path),
            )
            if ok and dest:
                self.pyinstaller_data.append((dir_path, dest))
                if hasattr(self, "log"):
                    self.log.append(
                        f"Dossier ajouté à PyInstaller : {dir_path} => {dest}"
                    )


def add_nuitka_data_file(self):
    import os

    from PySide6.QtCore import QDir
    from PySide6.QtWidgets import QFileDialog, QInputDialog

    # Demander à l'utilisateur s'il veut ajouter un fichier ou un dossier
    choix, ok = QInputDialog.getItem(
        self,
        "Type d'inclusion",
        "Inclure un fichier ou un dossier ?",
        ["Fichier", "Dossier"],
        0,
        False,
    )
    if not ok:
        return
    if not hasattr(self, "nuitka_data_files"):
        self.nuitka_data_files = []
    if not hasattr(self, "nuitka_data_dirs"):
        self.nuitka_data_dirs = []
    if choix == "Fichier":
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier à inclure avec Nuitka"
        )
        if file_path:
            dest, ok = QInputDialog.getText(
                self,
                "Chemin de destination",
                "Chemin de destination dans l'exécutable :",
                text=os.path.basename(file_path),
            )
            if ok and dest:
                self.nuitka_data_files.append((file_path, dest))
                if hasattr(self, "log"):
                    self.log.append(f"Fichier ajouté à Nuitka : {file_path} => {dest}")
    elif choix == "Dossier":
        dir_path = QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier à inclure avec Nuitka", QDir.homePath()
        )
        if dir_path:
            dest, ok = QInputDialog.getText(
                self,
                "Chemin de destination",
                "Chemin de destination dans l'exécutable :",
                text=os.path.basename(dir_path),
            )
            if ok and dest:
                self.nuitka_data_dirs.append((dir_path, dest))
                if hasattr(self, "log"):
                    self.log.append(f"Dossier ajouté à Nuitka : {dir_path} => {dest}")


def show_language_dialog(self):
    from PySide6.QtWidgets import QInputDialog

    try:
        langs = asyncio.run(_i18n.available_languages())
    except Exception:
        langs = [{"code": "en", "name": "English"}, {"code": "fr", "name": "Français"}]
    # Build options list with 'System' at top
    options = ["System"] + [str(x.get("name", x.get("code", ""))) for x in langs]
    # Determine current index
    current_pref = getattr(self, "language", "System")
    try:
        if current_pref == "System":
            start_index = 0
        else:
            # map code->index
            codes = [str(x.get("code", "")) for x in langs]
            try:
                start_index = 1 + codes.index(current_pref)
            except Exception:
                start_index = 0
    except Exception:
        start_index = 0
    title = "Choisir la langue"
    label = "Langue :"
    choice, ok = QInputDialog.getItem(self, title, label, options, start_index, False)
    if ok and choice:
        lang_pref = (
            "System"
            if choice == "System"
            else next(
                (
                    str(x.get("code", "en"))
                    for x in langs
                    if str(x.get("name", "")) == choice
                ),
                "en",
            )
        )
        try:
            tr = asyncio.run(_i18n.get_translations(lang_pref))
            _apply_translations(self, tr)
            try:
                setattr(self, "_tr", tr)
            except Exception:
                pass
            # Propagate translations to all engines so their UI matches the app language immediately
            try:
                import Core.engines_loader as engines_loader

                engines_loader.registry.apply_translations(self, tr)
            except Exception:
                pass
            # Update language preference markers
            try:
                self.language_pref = lang_pref
            except Exception:
                pass
            self.language = lang_pref
            try:
                if hasattr(self, "save_preferences"):
                    self.save_preferences()
            except Exception:
                pass
            if hasattr(self, "log") and self.log:
                meta = tr.get("_meta", {}) if isinstance(tr, dict) else {}
                self.log.append(
                    f"Langue appliquée: {getattr(meta, 'get', lambda k, d=None: d)('name', lang_pref) if isinstance(meta, dict) else lang_pref}"
                )
        except Exception as e:
            if hasattr(self, "log") and self.log:
                self.log.append(f"⚠️ Échec application de la langue: {e}")
    else:
        if hasattr(self, "log") and self.log:
            self.log.append("Sélection de la langue annulée.")


def _themes_dir() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes")
    )


def _list_available_themes() -> list[tuple[str, str]]:
    """
    Retourne une liste (display_name, absolute_path) pour tous les fichiers .qss
    présents dans themes. display_name est dérivé du nom de fichier.
    """
    themes: list[tuple[str, str]] = []
    try:
        tdir = _themes_dir()
        if os.path.isdir(tdir):
            for fname in sorted(os.listdir(tdir)):
                if not fname.lower().endswith(".qss"):
                    continue
                name = os.path.splitext(fname)[0]
                disp = name.replace("_", " ").replace("-", " ").strip().title()
                themes.append((disp, os.path.join(tdir, fname)))
    except Exception:
        pass
    return themes


def _is_qss_dark(css: str) -> bool:
    """Heuristic to determine if a QSS stylesheet is dark or light.
    - Prefer background/background-color/window/base declarations when present
    - Fallback to all color tokens found
    - Compute average luminance; return True if dark
    """
    try:
        import re

        if not css or not isinstance(css, str):
            return False
        # Collect likely background colors first
        bg_matches = [
            m.group(2).strip()
            for m in re.finditer(
                r"(?i)(background(?:-color)?|window|base)\s*:\s*([^;]+);", css
            )
        ]
        tokens = (
            bg_matches
            if bg_matches
            else re.findall(r"#[0-9a-fA-F]{3,6}|rgba?\([^\)]+\)", css)
        )
        if not tokens:
            return False

        def _to_rgb(val: str):
            try:
                v = val.strip()
                if v.startswith("#"):
                    h = v[1:]
                    if len(h) == 3:
                        r = int(h[0] * 2, 16)
                        g = int(h[1] * 2, 16)
                        b = int(h[2] * 2, 16)
                    elif len(h) >= 6:
                        r = int(h[0:2], 16)
                        g = int(h[2:4], 16)
                        b = int(h[4:6], 16)
                    else:
                        return None
                    return (r, g, b)
                if v.lower().startswith("rgb"):
                    # Support rgb/rgba with optional percentages
                    nums_str = re.findall(r"([0-9.]+%?)", v)[:3]
                    if any(s.endswith("%") for s in nums_str):
                        vals = []
                        for s in nums_str:
                            if s.endswith("%"):
                                vals.append(
                                    int(max(0.0, min(100.0, float(s[:-1]))) * 2.55)
                                )
                            else:
                                vals.append(int(max(0.0, min(255.0, float(s)))))
                        return tuple(vals)
                    nums = [
                        int(max(0.0, min(255.0, float(x))))
                        for x in re.findall(r"([0-9.]+)", v)[:3]
                    ]
                    if len(nums) == 3:
                        return tuple(nums)
            except Exception:
                return None
            return None

        rgbs = []
        for t in tokens:
            rgb = _to_rgb(t)
            if rgb:
                rgbs.append(rgb)
        if not rgbs:
            return False
        avg = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in rgbs) / len(rgbs)
        return avg < 128.0
    except Exception:
        return False


def _apply_translations(self, tr: dict[str, object]) -> None:
    try:
        # Buttons
        if getattr(self, "btn_select_folder", None):
            self.btn_select_folder.setText(
                str(tr.get("select_folder", self.btn_select_folder.text()))
            )
        if getattr(self, "btn_select_files", None):
            self.btn_select_files.setText(
                str(tr.get("select_files", self.btn_select_files.text()))
            )
        if getattr(self, "btn_build_all", None):
            self.btn_build_all.setText(
                str(tr.get("build_all", self.btn_build_all.text()))
            )
        if getattr(self, "btn_export_config", None):
            self.btn_export_config.setText(
                str(tr.get("export_config", self.btn_export_config.text()))
            )
        if getattr(self, "btn_import_config", None):
            self.btn_import_config.setText(
                str(tr.get("import_config", self.btn_import_config.text()))
            )
        if getattr(self, "btn_cancel_all", None):
            self.btn_cancel_all.setText(
                str(tr.get("cancel_all", self.btn_cancel_all.text()))
            )
        if getattr(self, "btn_suggest_deps", None):
            self.btn_suggest_deps.setText(
                str(tr.get("suggest_deps", self.btn_suggest_deps.text()))
            )

        if getattr(self, "btn_remove_file", None):
            self.btn_remove_file.setText(
                str(tr.get("btn_remove_file", self.btn_remove_file.text()))
            )

        if getattr(self, "btn_help", None):
            self.btn_help.setText(str(tr.get("help", self.btn_help.text())))
        if getattr(self, "btn_show_stats", None):
            self.btn_show_stats.setText(
                str(tr.get("show_stats", self.btn_show_stats.text()))
            )
        if getattr(self, "select_lang", None):
            self.select_lang.setText(
                str(tr.get("select_lang", self.select_lang.text()))
            )
        if getattr(self, "select_theme", None):
            try:
                # Prefer dynamic label keys; fallback to generic key
                if getattr(self, "theme", "System") == "System":
                    val = (
                        tr.get("choose_theme_system_button")
                        or tr.get("choose_theme_button")
                        or tr.get("select_theme")
                    )
                else:
                    val = tr.get("choose_theme_button") or tr.get("select_theme")
                self.select_theme.setText(str(val or self.select_theme.text()))
            except Exception:
                self.select_theme.setText(
                    str(tr.get("select_theme", self.select_theme.text()))
                )
        if getattr(self, "venv_button", None):
            self.venv_button.setText(
                str(tr.get("venv_button", self.venv_button.text()))
            )
        if getattr(self, "btn_select_icon", None):
            self.btn_select_icon.setText(
                str(tr.get("btn_select_icon", self.btn_select_icon.text()))
            )
        if getattr(self, "btn_nuitka_icon", None):
            self.btn_nuitka_icon.setText(
                str(tr.get("btn_nuitka_icon", self.btn_nuitka_icon.text()))
            )
        # Labels
        if getattr(self, "label_workspace_section", None):
            self.label_workspace_section.setText(
                str(
                    tr.get(
                        "label_workspace_section", self.label_workspace_section.text()
                    )
                )
            )
        if getattr(self, "venv_label", None):
            self.venv_label.setText(str(tr.get("venv_label", self.venv_label.text())))
        if getattr(self, "label_folder", None):
            self.label_folder.setText(
                str(tr.get("label_folder", self.label_folder.text()))
            )
        if getattr(self, "label_files_section", None):
            self.label_files_section.setText(
                str(tr.get("label_files_section", self.label_files_section.text()))
            )
        if getattr(self, "label_logs_section", None):
            self.label_logs_section.setText(
                str(tr.get("label_logs_section", self.label_logs_section.text()))
            )
        # Tabs
        if getattr(self, "compiler_tabs", None):
            try:
                if getattr(self, "tab_pyinstaller", None):
                    idx = self.compiler_tabs.indexOf(self.tab_pyinstaller)
                    if idx >= 0:
                        self.compiler_tabs.setTabText(
                            idx,
                            str(
                                tr.get(
                                    "tab_pyinstaller", self.compiler_tabs.tabText(idx)
                                )
                            ),
                        )
                if getattr(self, "tab_nuitka", None):
                    idx2 = self.compiler_tabs.indexOf(self.tab_nuitka)
                    if idx2 >= 0:
                        self.compiler_tabs.setTabText(
                            idx2,
                            str(tr.get("tab_nuitka", self.compiler_tabs.tabText(idx2))),
                        )
            except Exception:
                pass
        # Checkboxes/options
        if getattr(self, "opt_onefile", None):
            self.opt_onefile.setText(
                str(tr.get("opt_onefile", self.opt_onefile.text()))
            )
        if getattr(self, "opt_windowed", None):
            self.opt_windowed.setText(
                str(tr.get("opt_windowed", self.opt_windowed.text()))
            )
        if getattr(self, "opt_noconfirm", None):
            self.opt_noconfirm.setText(
                str(tr.get("opt_noconfirm", self.opt_noconfirm.text()))
            )
        if getattr(self, "opt_clean", None):
            self.opt_clean.setText(str(tr.get("opt_clean", self.opt_clean.text())))
        if getattr(self, "opt_noupx", None):
            self.opt_noupx.setText(str(tr.get("opt_noupx", self.opt_noupx.text())))
        if getattr(self, "opt_main_only", None):
            self.opt_main_only.setText(
                str(tr.get("opt_main_only", self.opt_main_only.text()))
            )
        if getattr(self, "opt_debug", None):
            self.opt_debug.setText(str(tr.get("opt_debug", self.opt_debug.text())))
        if getattr(self, "opt_auto_install", None):
            self.opt_auto_install.setText(
                str(tr.get("opt_auto_install", self.opt_auto_install.text()))
            )
        if getattr(self, "opt_silent_errors", None):
            self.opt_silent_errors.setText(
                str(tr.get("opt_silent_errors", self.opt_silent_errors.text()))
            )
        # Nuitka checkboxes
        if getattr(self, "nuitka_onefile", None):
            self.nuitka_onefile.setText(
                str(tr.get("nuitka_onefile", self.nuitka_onefile.text()))
            )
        if getattr(self, "nuitka_standalone", None):
            self.nuitka_standalone.setText(
                str(tr.get("nuitka_standalone", self.nuitka_standalone.text()))
            )
        if getattr(self, "nuitka_disable_console", None):
            self.nuitka_disable_console.setText(
                str(
                    tr.get("nuitka_disable_console", self.nuitka_disable_console.text())
                )
            )
        if getattr(self, "nuitka_show_progress", None):
            self.nuitka_show_progress.setText(
                str(tr.get("nuitka_show_progress", self.nuitka_show_progress.text()))
            )
        if getattr(self, "nuitka_output_dir", None):
            try:
                self.nuitka_output_dir.setPlaceholderText(
                    str(
                        tr.get(
                            "nuitka_output_dir",
                            self.nuitka_output_dir.placeholderText(),
                        )
                    )
                )
            except Exception:
                pass
        # Tooltips (apply i18n when keys are present; fallback to current tooltip text)
        try:

            def _tt(key: str, current: str) -> str:
                try:
                    val = tr.get(key)
                    if isinstance(val, str) and val.strip():
                        return val
                except Exception:
                    pass
                return current

            if getattr(self, "btn_select_folder", None):
                self.btn_select_folder.setToolTip(
                    _tt("tt_select_folder", self.btn_select_folder.toolTip())
                )
            if getattr(self, "btn_select_files", None):
                self.btn_select_files.setToolTip(
                    _tt("tt_select_files", self.btn_select_files.toolTip())
                )
            if getattr(self, "btn_build_all", None):
                self.btn_build_all.setToolTip(
                    _tt("tt_build_all", self.btn_build_all.toolTip())
                )
            if getattr(self, "btn_export_config", None):
                self.btn_export_config.setToolTip(
                    _tt("tt_export_config", self.btn_export_config.toolTip())
                )
            if getattr(self, "btn_import_config", None):
                self.btn_import_config.setToolTip(
                    _tt("tt_import_config", self.btn_import_config.toolTip())
                )
            if getattr(self, "btn_cancel_all", None):
                self.btn_cancel_all.setToolTip(
                    _tt("tt_cancel_all", self.btn_cancel_all.toolTip())
                )
            if getattr(self, "btn_remove_file", None):
                self.btn_remove_file.setToolTip(
                    _tt("tt_remove_file", self.btn_remove_file.toolTip())
                )
            if getattr(self, "btn_select_icon", None):
                self.btn_select_icon.setToolTip(
                    _tt("tt_select_icon", self.btn_select_icon.toolTip())
                )
            if getattr(self, "btn_help", None):
                self.btn_help.setToolTip(_tt("tt_help", self.btn_help.toolTip()))
            if getattr(self, "btn_api_loader", None):
                self.btn_api_loader.setToolTip(
                    _tt("tt_api_loader", self.btn_api_loader.toolTip())
                )
            if getattr(self, "btn_acasl_loader", None):
                self.btn_acasl_loader.setToolTip(
                    _tt("tt_acasl_loader", self.btn_acasl_loader.toolTip())
                )
            if getattr(self, "venv_button", None):
                self.venv_button.setToolTip(
                    _tt("tt_venv_button", self.venv_button.toolTip())
                )
            if getattr(self, "btn_suggest_deps", None):
                self.btn_suggest_deps.setToolTip(
                    _tt("tt_suggest_deps", self.btn_suggest_deps.toolTip())
                )
            if getattr(self, "btn_show_stats", None):
                self.btn_show_stats.setToolTip(
                    _tt("tt_show_stats", self.btn_show_stats.toolTip())
                )
            if getattr(self, "output_dir_input", None):
                self.output_dir_input.setToolTip(
                    _tt("tt_output_dir", self.output_dir_input.toolTip())
                )
            # PyInstaller/Nuitka specific tooltips
            if getattr(self, "nuitka_disable_console", None):
                self.nuitka_disable_console.setToolTip(
                    _tt(
                        "tt_nuitka_disable_console",
                        self.nuitka_disable_console.toolTip(),
                    )
                )
            if getattr(self, "btn_nuitka_icon", None):
                self.btn_nuitka_icon.setToolTip(
                    _tt("tt_nuitka_icon", self.btn_nuitka_icon.toolTip())
                )
            # Options checkboxes
            if getattr(self, "opt_onefile", None):
                self.opt_onefile.setToolTip(
                    _tt("tt_opt_onefile", self.opt_onefile.toolTip())
                )
            if getattr(self, "opt_windowed", None):
                self.opt_windowed.setToolTip(
                    _tt("tt_opt_windowed", self.opt_windowed.toolTip())
                )
            if getattr(self, "opt_noconfirm", None):
                self.opt_noconfirm.setToolTip(
                    _tt("tt_opt_noconfirm", self.opt_noconfirm.toolTip())
                )
            if getattr(self, "opt_clean", None):
                self.opt_clean.setToolTip(_tt("tt_opt_clean", self.opt_clean.toolTip()))
            if getattr(self, "opt_noupx", None):
                self.opt_noupx.setToolTip(_tt("tt_opt_noupx", self.opt_noupx.toolTip()))
            if getattr(self, "opt_main_only", None):
                self.opt_main_only.setToolTip(
                    _tt("tt_opt_main_only", self.opt_main_only.toolTip())
                )
            if getattr(self, "opt_debug", None):
                self.opt_debug.setToolTip(_tt("tt_opt_debug", self.opt_debug.toolTip()))
            if getattr(self, "opt_auto_install", None):
                self.opt_auto_install.setToolTip(
                    _tt("tt_opt_auto_install", self.opt_auto_install.toolTip())
                )
            if getattr(self, "opt_silent_errors", None):
                self.opt_silent_errors.setToolTip(
                    _tt("tt_opt_silent_errors", self.opt_silent_errors.toolTip())
                )
        except Exception:
            pass
    except Exception:
        pass


def apply_theme(self, pref: str):
    """Applique un thème depuis themes.
    - 'System': détection (dark/light) et sélection d'un .qss correspondant si possible
    - Sinon: appliquer le .qss dont le nom correspond (insensible à la casse/espaces)
    - Repli: pas de stylesheet si aucun thème trouvé
    """
    try:
        from PySide6.QtWidgets import QApplication

        candidates = _list_available_themes()
        chosen_path = None
        chosen_name = None

        if not pref or pref == "System":
            mode = _detect_system_color_scheme()  # 'dark'/'light'
            # préférer un fichier contenant le mot-clé
            key = "dark" if mode == "dark" else "light"
            for disp, path in candidates:
                if key in os.path.basename(path).lower():
                    chosen_path = path
                    chosen_name = disp
                    break
            # repli: premier disponible
            if not chosen_path and candidates:
                chosen_name, chosen_path = candidates[0]
        else:
            norm = pref.lower().replace(" ", "").replace("-", "").replace("_", "")
            # correspondance exacte sur le stem
            for disp, path in candidates:
                stem = os.path.splitext(os.path.basename(path))[0]
                stem_n = stem.lower().replace(" ", "").replace("-", "").replace("_", "")
                if stem_n == norm:
                    chosen_name = disp
                    chosen_path = path
                    break
            # sinon, contient
            if not chosen_path:
                for disp, path in candidates:
                    if norm in os.path.basename(path).lower().replace(" ", ""):
                        chosen_name = disp
                        chosen_path = path
                        break

        css = ""
        if chosen_path and os.path.isfile(chosen_path):
            with open(chosen_path, encoding="utf-8") as f:
                css = f.read()
        app = QApplication.instance()
        if app:
            app.setStyleSheet(css)
        self.theme = pref or "System"
        # Met à jour le texte du bouton (ne pas recharger i18n; utiliser la traduction active)
        if hasattr(self, "select_theme") and self.select_theme:
            try:
                tr = getattr(self, "_tr", None)
                if isinstance(tr, dict):
                    if self.theme == "System":
                        val = (
                            tr.get("choose_theme_system_button")
                            or tr.get("choose_theme_button")
                            or tr.get("select_theme")
                        )
                    else:
                        val = tr.get("choose_theme_button") or tr.get("select_theme")
                    if isinstance(val, str) and val:
                        self.select_theme.setText(val)
            except Exception:
                pass
        # Update sidebar logo according to effective theme (dark/light)
        try:
            # Determine effective theme mode from applied QSS when available
            if css:
                effective_mode = "dark" if _is_qss_dark(css) else "light"
            elif not pref or pref == "System":
                effective_mode = _detect_system_color_scheme()
            else:
                base = os.path.basename(chosen_path) if chosen_path else ""
                effective_mode = "dark" if "dark" in base.lower() else "light"
            if getattr(self, "sidebar_logo", None) is not None:
                from PySide6.QtGui import QPixmap

                project_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
                candidates = [
                    (
                        os.path.join(project_dir, "logo", "sidebar_logo2.png")
                        if effective_mode == "dark"
                        else os.path.join(project_dir, "logo", "sidebar_logo.png")
                    ),
                    os.path.join(project_dir, "logo", "sidebar_logo.png"),
                    os.path.join(project_dir, "logo", "sidebar_logo2.png"),
                ]
                logo_path = None
                for p in candidates:
                    if os.path.exists(p):
                        logo_path = p
                        break
                if logo_path:
                    pixmap = QPixmap(logo_path)
                    target_size = 200
                    self.sidebar_logo.setPixmap(
                        pixmap.scaled(
                            target_size,
                            target_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    self.sidebar_logo.setToolTip("PyCompiler")
        except Exception:
            pass
        # Log
        if hasattr(self, "log") and self.log:
            if chosen_path:
                self.log.append(
                    f"🎨 Thème appliqué : {chosen_name} ({os.path.basename(chosen_path)})"
                )
            else:
                self.log.append(
                    "🎨 Aucun thème appliqué (aucun fichier .qss trouvé dans themes)"
                )
    except Exception as e:
        try:
            if hasattr(self, "log") and self.log:
                self.log.append(f"⚠️ Échec d'application du thème: {e}")
        except Exception:
            pass


def show_theme_dialog(self):
    from PySide6.QtWidgets import QInputDialog

    themes = _list_available_themes()
    options = ["System"] + [name for name, _ in themes]
    current = getattr(self, "theme", "System")
    # Trouver l'index initial
    try:
        start_index = options.index(current) if current in options else 0
    except Exception:
        start_index = 0
    title = self.tr("Choisir un thème", "Choose theme")
    label = self.tr("Thème :", "Theme:")
    choice, ok = QInputDialog.getItem(self, title, label, options, start_index, False)
    if ok and choice:
        self.theme = choice
        apply_theme(self, choice)
        # Sauvegarde si possible
        try:
            if hasattr(self, "save_preferences"):
                self.save_preferences()
        except Exception:
            pass
    else:
        if hasattr(self, "log") and self.log:
            self.log.append("Sélection du thème annulée.")
