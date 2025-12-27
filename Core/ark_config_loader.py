# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
ARK Configuration Loader
Charge la configuration depuis ARK_Main_Config.yml à la racine du workspace
"""

import os
from pathlib import Path
from typing import Any
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
    "auto_detect_entry_points": True,
    
    # PyInstaller options
    "pyinstaller": {
        "onefile": True,
        "windowed": False,
        "noconfirm": True,
        "clean": False,
        "noupx": False,
        "icon": None,
        "debug": False,
        "additional_options": [],
    },
    
    # Nuitka options
    "nuitka": {
        "onefile": True,
        "standalone": True,
        "disable_console": False,
        "show_progress": True,
        "output_dir": None,
        "icon": None,
        "additional_options": [],
    },
    
    # Output configuration
    "output": {
        "directory": "dist",
        "clean_before_build": False,
    },
    
    # Dependencies
    "dependencies": {
        "requirements_files": [
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
        "auto_generate_from_imports": True,
    },
    
    # Environment Manager Priorities
    "environment_manager": {
        "priority": ["poetry", "pipenv", "conda", "pdm", "uv", "pip"],
        "auto_detect": True,
        "fallback_to_pip": True,
    },
    
    # Plugins Configuration
    "plugins": {
        "bcasl_enabled": True,
        "plugin_timeout": 0.0,
    },

    # Engines UI state (persisted widget states per engine)
    "engines": {
        "pyinstaller": {
            "ui": {
                "widgets": {}
            }
        },
        "nuitka": {
            "ui": {
                "widgets": {}
            }
        }
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
    Charge la configuration ARK depuis ARK_Main_Config.yml (YAML ONLY)
    
    Cherche les fichiers dans cet ordre (priorité):
    1. ARK_Main_Config.yaml
    2. ARK_Main_Config.yml
    3. .ARK_Main_Config.yaml
    4. .ARK_Main_Config.yml
    
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
    
    # Chercher les fichiers YAML dans l'ordre de priorité
    # Priorité: ARK_Main_Config.yaml > ARK_Main_Config.yml > .ARK_Main_Config.yaml > .ARK_Main_Config.yml
    config_candidates = [
        workspace_path / "ARK_Main_Config.yaml",
        workspace_path / "ARK_Main_Config.yml",
        workspace_path / ".ARK_Main_Config.yaml",
        workspace_path / ".ARK_Main_Config.yml",
    ]
    
    config_file = None
    for candidate in config_candidates:
        if candidate.exists() and candidate.is_file():
            config_file = candidate
            break
    
    if not config_file:
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
        print(f"Warning: Failed to load ARK config from {config_file}: {e}")
        return config


def get_compiler_options(config: dict[str, Any], compiler: str) -> dict[str, Any]:
    """Récupère les options pour un compilateur spécifique"""
    compiler_lower = compiler.lower()
    return config.get(compiler_lower, {})


def get_output_options(config: dict[str, Any]) -> dict[str, Any]:
    """Récupère les options de sortie"""
    return config.get("output", {})


def get_dependency_options(config: dict[str, Any]) -> dict[str, Any]:
    """Récupère les options de dépendances"""
    return config.get("dependencies", {})


def get_environment_manager_options(config: dict[str, Any]) -> dict[str, Any]:
    """Récupère les options du gestionnaire d'environnement"""
    return config.get("environment_manager", {})


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
    try:
        file_path_obj = Path(file_path)
        workspace_path_obj = Path(workspace_dir)
        
        try:
            relative_path = file_path_obj.relative_to(workspace_path_obj)
        except ValueError:
            return True
        
        # Use Path.match() which properly handles ** glob patterns
        relative_str = relative_path.as_posix()
        for pattern in exclusion_patterns:
            # Try matching against the relative path
            if relative_path.match(pattern):
                return True
            # Also try matching just the filename for simple patterns like "*.pyc"
            if file_path_obj.match(pattern):
                return True
        
        return False
        
    except Exception:
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
    
    if config_file.exists():
        return False
    
    try:
        default_content = """# ══════════════════���════════════════════════════════════════════
# ARK Main Configuration File
# ═══════════════════════════════════════════════════════════════

# FILE PATTERNS
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

inclusion_patterns:
  - "**/*.py"

# COMPILATION BEHAVIOR
compile_only_main: false
main_file_names:
  - "main.py"
  - "app.py"
auto_detect_entry_points: true

# PYINSTALLER OPTIONS
pyinstaller:
  onefile: true
  windowed: false
  noconfirm: true
  clean: false
  noupx: false
  icon: null
  debug: false
  additional_options: []

# NUITKA OPTIONS
nuitka:
  onefile: true
  standalone: true
  disable_console: false
  show_progress: true
  output_dir: null
  icon: null
  additional_options: []

# OUTPUT CONFIGURATION
output:
  directory: "dist"
  clean_before_build: false

# DEPENDENCIES
dependencies:
  auto_generate_from_imports: true

# ENVIRONMENT MANAGER
environment_manager:
  priority:
    - "poetry"
    - "pipenv"
    - "conda"
    - "pdm"
    - "uv"
    - "pip"
  auto_detect: true
  fallback_to_pip: true

# ENGINES (UI state persistence)
engines:
  pyinstaller:
    ui:
      widgets: {}
  nuitka:
    ui:
      widgets: {}
"""
        
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(default_content)
        
        return True
        
    except Exception as e:
        print(f"Warning: Failed to create ARK_Main_Config.yml: {e}")
        return False


# --- Simple Engine UI state helpers (for non-dev friendly persistence) ---

def _read_yaml(path: Path) -> dict:
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_yaml_atomic(path: Path, data: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


essential_props = ("checked", "text", "enabled", "visible", "currentIndex")


def load_engine_ui_state(workspace_dir: str, engine_id: str) -> dict:
    """Load saved UI state for an engine from ARK_Main_Config.yml (YAML ONLY).
    Cherche les fichiers dans cet ordre:
    1. ARK_Main_Config.yaml
    2. ARK_Main_Config.yml
    3. .ARK_Main_Config.yaml
    4. .ARK_Main_Config.yml
    
    Returns a mapping {widgetName: {prop: value}} or {}.
    """
    try:
        if not workspace_dir:
            return {}
        
        workspace_path = Path(workspace_dir)
        
        # Chercher les fichiers YAML dans l'ordre de priorité
        config_candidates = [
            workspace_path / "ARK_Main_Config.yaml",
            workspace_path / "ARK_Main_Config.yml",
            workspace_path / ".ARK_Main_Config.yaml",
            workspace_path / ".ARK_Main_Config.yml",
        ]
        
        cfg = {}
        for candidate in config_candidates:
            if candidate.exists() and candidate.is_file():
                cfg = _read_yaml(candidate)
                break
        
        engines = cfg.get("engines", {}) if isinstance(cfg, dict) else {}
        e = engines.get(str(engine_id), {}) if isinstance(engines, dict) else {}
        ui = e.get("ui", {}) if isinstance(e, dict) else {}
        widgets = ui.get("widgets", {}) if isinstance(ui, dict) else {}
        return widgets if isinstance(widgets, dict) else {}
    except Exception:
        return {}


def save_engine_ui_state(workspace_dir: str, engine_id: str, updates: dict) -> bool:
    """Save UI state for an engine into ARK_Main_Config.yml (YAML ONLY).
    Cherche les fichiers existants dans cet ordre:
    1. ARK_Main_Config.yaml
    2. ARK_Main_Config.yml
    3. .ARK_Main_Config.yaml
    4. .ARK_Main_Config.yml
    
    Si aucun fichier n'existe, crée ARK_Main_Config.yml par défaut.
    
    - workspace_dir: project workspace path
    - engine_id: id string (e.g. 'pyinstaller')
    - updates: {widgetName: {prop: value}}
    Returns True on success, False otherwise.
    """
    if not workspace_dir:
        return False
    try:
        workspace_path = Path(workspace_dir)
        
        # Chercher les fichiers YAML existants dans l'ordre de priorité
        config_candidates = [
            workspace_path / "ARK_Main_Config.yaml",
            workspace_path / "ARK_Main_Config.yml",
            workspace_path / ".ARK_Main_Config.yaml",
            workspace_path / ".ARK_Main_Config.yml",
        ]
        
        cfg_path = None
        for candidate in config_candidates:
            if candidate.exists() and candidate.is_file():
                cfg_path = candidate
                break
        
        # Si aucun fichier n'existe, utiliser ARK_Main_Config.yml par défaut
        if cfg_path is None:
            cfg_path = workspace_path / "ARK_Main_Config.yml"
        
        cfg = _read_yaml(cfg_path)
        if not isinstance(cfg, dict):
            cfg = {}
        engines = cfg.get("engines")
        if not isinstance(engines, dict):
            engines = {}
            cfg["engines"] = engines
        e = engines.get(str(engine_id))
        if not isinstance(e, dict):
            e = {}
            engines[str(engine_id)] = e
        ui = e.get("ui")
        if not isinstance(ui, dict):
            ui = {}
            e["ui"] = ui
        widgets = ui.get("widgets")
        if not isinstance(widgets, dict):
            widgets = {}
            ui["widgets"] = widgets
        # Merge per widget
        for wname, props in (updates or {}).items():
            if not isinstance(wname, str) or not isinstance(props, dict):
                continue
            cur = widgets.get(wname)
            if not isinstance(cur, dict):
                cur = {}
                widgets[wname] = cur
            for k, v in props.items():
                if k in essential_props:
                    cur[k] = v
        return _write_yaml_atomic(cfg_path, cfg)
    except Exception:
        return False
