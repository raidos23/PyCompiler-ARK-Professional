# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2025 Samuel Amen Ague

"""
ARK Configuration Loader
Charge la configuration depuis ARK_Main_Config.yml à la racine du workspace
"""

import os
from pathlib import Path
from typing import Any, Optional
import yaml


DEFAULT_EXCLUSION_PATTERNS = [
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.pyd",
    ".git/**",
    ".svn/**",
    ".hg/**",
    "venv/**",
    ".venv/**",
    "env/**",
    ".env/**",
    "node_modules/**",
    "build/**",
    "dist/**",
    "*.egg-info/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".tox/**",
    "site-packages/**",
]

DEFAULT_CONFIG = {
    # File patterns
    "exclusion_patterns": DEFAULT_EXCLUSION_PATTERNS,
    "inclusion_patterns": ["**/*.py"],
    
    # Compilation behavior
    "compile_only_main": False,
    "main_file_names": ["main.py", "app.py"],
    "auto_detect_entry_points": True,  # Auto-detect files with if __name__ == '__main__'
    
    # PyInstaller options
    "pyinstaller": {
        "onefile": True,
        "windowed": False,
        "noconfirm": True,
        "clean": False,
        "noupx": False,
        "icon": None,  # Path to .ico file
        "debug": False,
        "additional_options": [],  # Extra command-line options
    },
    
    # Nuitka options
    "nuitka": {
        "onefile": True,
        "standalone": True,
        "disable_console": False,
        "show_progress": True,
        "output_dir": None,
        "icon": None,  # Path to .ico file
        "additional_options": [],  # Extra command-line options
    },
    
    # cx_Freeze options
    "cx_freeze": {
        "output_dir": None,
        "target_name": None,
        "icon": None,
        "additional_options": [],
    },
    
    # Output configuration
    "output": {
        "directory": "dist",  # Output directory name
        "clean_before_build": False,  # Clean output directory before build
        "organize_by_file": True,  # Create subdirectories for each compiled file
    },
    
    # Dependencies
    "dependencies": {
        "auto_install_missing": True,  # Auto-install missing modules
        "requirements_file": "requirements.txt",  # Path to requirements file
        "exclude_modules": [],  # Modules to exclude from compilation
        "include_modules": [],  # Modules to explicitly include
    },
    
    # Plugins (BCASL/ACASL)
    "plugins": {
        "bcasl_enabled": True,  # Enable pre-compilation plugins
        "acasl_enabled": True,  # Enable post-compilation plugins
        "plugin_timeout": 0,  # Plugin timeout in seconds (0 = unlimited)
    },
    
    # Advanced options
    "advanced": {
        "max_parallel_builds": 4,  # Maximum number of parallel compilations
        "silent_errors": False,  # Don't show error dialogs
        "log_level": "info",  # Logging level: debug, info, warning, error
        "preserve_temp_files": False,  # Keep temporary build files
    },
}


def _deep_merge_dict(base: dict, override: dict) -> dict:
    """Fusionne récursivement deux dictionnaires"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def load_ark_config(workspace_dir: str) -> dict[str, Any]:
    """
    Charge la configuration ARK depuis ARK_Main_Config.yml
    
    Args:
        workspace_dir: Chemin du workspace
        
    Returns:
        Dictionnaire de configuration complet avec toutes les options disponibles
    """
    import copy
    config = copy.deepcopy(DEFAULT_CONFIG)
    
    if not workspace_dir:
        return config
    
    workspace_path = Path(workspace_dir)
    config_file = workspace_path / "ARK_Main_Config.yml"
    
    if not config_file.exists():
        return config
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f) or {}
        
        if not isinstance(user_config, dict):
            return config
        
        # Fusionner la configuration utilisateur avec la configuration par défaut
        config = _deep_merge_dict(config, user_config)
        
        # Validation et normalisation des patterns d'exclusion
        if "exclusion_patterns" in config:
            if isinstance(config["exclusion_patterns"], list):
                # Combiner avec les patterns par défaut si l'utilisateur n'a pas tout redéfini
                user_patterns = [str(p) for p in config["exclusion_patterns"] if p]
                config["exclusion_patterns"] = list(set(DEFAULT_EXCLUSION_PATTERNS + user_patterns))
        
        # Validation des patterns d'inclusion
        if "inclusion_patterns" in config:
            if isinstance(config["inclusion_patterns"], list):
                config["inclusion_patterns"] = [str(p) for p in config["inclusion_patterns"] if p]
        
        # Validation des noms de fichiers principaux
        if "main_file_names" in config:
            if isinstance(config["main_file_names"], list):
                config["main_file_names"] = [str(n) for n in config["main_file_names"] if n]
        
        return config
        
    except Exception as e:
        # En cas d'erreur, retourner la config par défaut
        print(f"Warning: Failed to load ARK_Main_Config.yml: {e}")
        return config


def get_compiler_options(config: dict[str, Any], compiler: str) -> dict[str, Any]:
    """
    Récupère les options pour un compilateur spécifique
    
    Args:
        config: Configuration ARK complète
        compiler: Nom du compilateur ('pyinstaller', 'nuitka', 'cx_freeze')
        
    Returns:
        Dictionnaire des options du compilateur
    """
    compiler_lower = compiler.lower()
    return config.get(compiler_lower, {})


def get_output_options(config: dict[str, Any]) -> dict[str, Any]:
    """Récupère les options de sortie"""
    return config.get("output", {})


def get_dependency_options(config: dict[str, Any]) -> dict[str, Any]:
    """Récupère les options de dépendances"""
    return config.get("dependencies", {})


def get_plugin_options(config: dict[str, Any]) -> dict[str, Any]:
    """Récupère les options des plugins"""
    return config.get("plugins", {})


def get_advanced_options(config: dict[str, Any]) -> dict[str, Any]:
    """Récupère les options avancées"""
    return config.get("advanced", {})


def should_exclude_file(file_path: str, workspace_dir: str, exclusion_patterns: list[str]) -> bool:
    """
    Vérifie si un fichier doit être exclu selon les patterns
    
    Args:
        file_path: Chemin du fichier à vérifier
        workspace_dir: Chemin du workspace
        exclusion_patterns: Liste des patterns d'exclusion
        
    Returns:
        True si le fichier doit être exclu, False sinon
    """
    import fnmatch
    
    try:
        # Convertir en chemin relatif par rapport au workspace
        file_path_obj = Path(file_path)
        workspace_path_obj = Path(workspace_dir)
        
        try:
            relative_path = file_path_obj.relative_to(workspace_path_obj)
        except ValueError:
            # Le fichier n'est pas dans le workspace
            return True
        
        # Vérifier contre chaque pattern d'exclusion
        relative_str = relative_path.as_posix()
        for pattern in exclusion_patterns:
            if fnmatch.fnmatch(relative_str, pattern):
                return True
            # Vérifier aussi le nom du fichier seul
            if fnmatch.fnmatch(file_path_obj.name, pattern):
                return True
        
        return False
        
    except Exception:
        # En cas d'erreur, ne pas exclure par défaut
        return False


def create_default_ark_config(workspace_dir: str) -> bool:
    """
    Crée un fichier ARK_Main_Config.yml par défaut dans le workspace
    
    Args:
        workspace_dir: Chemin du workspace
        
    Returns:
        True si le fichier a été créé, False sinon
    """
    if not workspace_dir:
        return False
    
    workspace_path = Path(workspace_dir)
    config_file = workspace_path / "ARK_Main_Config.yml"
    
    # Ne pas écraser un fichier existant
    if config_file.exists():
        return False
    
    try:
        default_content = """# ═══════════════════════════════════════════════════════════════
# ARK Main Configuration File
# ═══════════════════════════════════════════════════════════════
# This file allows you to customize the compilation behavior
# for PyCompiler ARK++

# ───────────────────────────────────────────────────────────────
# FILE PATTERNS
# ───────────────────────────────────────────────────────────────

# Patterns of files/directories to EXCLUDE from compilation
# Use glob patterns (e.g., **/*.pyc, venv/**, .git/**)
exclusion_patterns:
  - "**/__pycache__/**"
  - "**/*.pyc"
  - "**/*.pyo"
  - "**/*.pyd"
  - ".git/**"
  - ".svn/**"
  - "venv/**"
  - ".venv/**"
  - "env/**"
  - "build/**"
  - "dist/**"
  - "*.egg-info/**"
  - ".pytest_cache/**"
  - ".mypy_cache/**"
  - "node_modules/**"
  # Add your custom exclusion patterns below:
  # - "tests/**"
  # - "docs/**"
  # - "examples/**"

# Patterns of files to INCLUDE for compilation
inclusion_patterns:
  - "**/*.py"

# ───────────────────────────────────────────────────────────────
# COMPILATION BEHAVIOR
# ───────────────────────────────────────────────────────────────

# Compile only main entry point files
compile_only_main: false

# Names of main entry point files
main_file_names:
  - "main.py"
  - "app.py"

# Auto-detect entry points (files with if __name__ == '__main__')
auto_detect_entry_points: true

# ───────────────────────────────────────────────────────────────
# PYINSTALLER OPTIONS
# ───────────────────────────────────────────────────────────────
pyinstaller:
  onefile: true
  windowed: false
  noconfirm: true
  clean: false
  noupx: false
  icon: null  # Path to .ico file (e.g., "assets/icon.ico")
  debug: false
  additional_options: []
    # - "--hidden-import=pkg_name"
    # - "--collect-data=pkg_name"

# ───────────────────────────────────────────────────────────────
# NUITKA OPTIONS
# ───────────────────────────────────────────────────────────────
nuitka:
  onefile: true
  standalone: true
  disable_console: false
  show_progress: true
  output_dir: null  # Output directory (e.g., "build/nuitka")
  icon: null  # Path to .ico file
  additional_options: []
    # - "--enable-plugin=numpy"
    # - "--include-package=pkg_name"

# ───────────────────────────────────────────────────────────────
# CX_FREEZE OPTIONS
# ───────────────────────────────────────────────────────────────
cx_freeze:
  output_dir: null
  target_name: null
  icon: null
  additional_options: []

# ───────────────────────────────────────────────────────────────
# OUTPUT CONFIGURATION
# ───────────────────────────────────────────────────────────────
output:
  directory: "dist"  # Output directory name
  clean_before_build: false  # Clean output directory before build
  organize_by_file: true  # Create subdirectories for each compiled file

# ───────────────────────────────────────────────────────────────
# DEPENDENCIES
# ───────────────────────────────────────────────────────────────
dependencies:
  auto_install_missing: true  # Auto-install missing modules
  requirements_file: "requirements.txt"
  exclude_modules: []  # Modules to exclude
    # - "test_module"
  include_modules: []  # Modules to explicitly include
    # - "hidden_module"

# ───────────────────────────────────────────────────────────────
# PLUGINS (BCASL/ACASL)
# ───────────────────────────────────────────────────────────────
plugins:
  bcasl_enabled: true  # Enable pre-compilation plugins
  acasl_enabled: true  # Enable post-compilation plugins
  plugin_timeout: 0  # Plugin timeout in seconds (0 = unlimited)

# ───────────────────────────────────────────────────────────────
# ADVANCED OPTIONS
# ───────────────────────────────────────────────────────────────
advanced:
  max_parallel_builds: 4  # Maximum number of parallel compilations
  silent_errors: false  # Don't show error dialogs
  log_level: "info"  # Logging level: debug, info, warning, error
  preserve_temp_files: false  # Keep temporary build files
"""
        
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(default_content)
        
        return True
        
    except Exception as e:
        print(f"Warning: Failed to create ARK_Main_Config.yml: {e}")
        return False