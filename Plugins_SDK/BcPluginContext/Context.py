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

from __future__ import annotations

import ast
import fnmatch
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Optional,
    Union,
    List,
    Iterator,
    Dict,
    Set,
    Tuple,
    Callable,
    Pattern,
)


# -----------------------------
# Plugin base (BCASL) and decorator
# -----------------------------
# Reuse BCASL types to guarantee compatibility with the host
try:  # noqa: E402
    from bcasl import (
        BCASL as BCASL,
        ExecutionReport as ExecutionReport,
        BcPluginBase as BcPluginBase,
        PluginMeta as PluginMeta,
        PreCompileContext as PreCompileContext,
    )

    try:
        from bcasl import (
            BCASL_PLUGIN_REGISTER_FUNC as BCASL_PLUGIN_REGISTER_FUNC,
            register_plugin as register_plugin,
        )
    except Exception:  # pragma: no cover

        def register_plugin(cls: Any) -> Any:  # type: ignore
            setattr(cls, "__bcasl_plugin__", True)
            return cls

        BCASL_PLUGIN_REGISTER_FUNC = "bcasl_register"
except Exception:  # pragma: no cover — dev fallback when BCASL is not importable

    class BcPluginBase:  # type: ignore
        pass

    class PluginMeta:  # type: ignore
        pass

    class PreCompileContext:
        pass


def register_plugin(cls: Any) -> Any:  # type: ignore
    setattr(cls, "__bcasl_plugin__", True)
    return cls

    BCASL_PLUGIN_REGISTER_FUNC = "bcasl_register"


# -----------------------------
# Version information
# -----------------------------
__version__ = "1.0.0"


# -----------------------------
# Type aliases
# -----------------------------
Pathish = Union[str, Path]


# -----------------------------
# Data classes for structured information
# -----------------------------


@dataclass
class DependencyInfo:
    """Information about project dependencies."""

    requirements_txt: List[str] = field(default_factory=list)
    pyproject_toml: Dict[str, Any] = field(default_factory=dict)
    setup_py: Dict[str, Any] = field(default_factory=dict)
    pipfile: Dict[str, Any] = field(default_factory=dict)
    conda_yaml: Dict[str, Any] = field(default_factory=dict)
    all_dependencies: Set[str] = field(default_factory=set)


@dataclass
class PythonFileInfo:
    """Information extracted from a Python file."""

    path: Path
    imports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    line_count: int = 0
    is_valid_syntax: bool = True
    syntax_error: Optional[str] = None


@dataclass
class VenvInfo:
    """Information about a virtual environment."""

    path: Path
    exists: bool = False
    python_version: Optional[str] = None
    pip_version: Optional[str] = None
    installed_packages: Dict[str, str] = field(default_factory=dict)
    is_active: bool = False


@dataclass
class GitInfo:
    """Git repository information."""

    is_repo: bool = False
    branch: Optional[str] = None
    has_uncommitted: bool = False
    staged_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    untracked_files: List[str] = field(default_factory=list)
    last_commit: Optional[str] = None


@dataclass
class ProjectStructureInfo:
    """Information about project structure."""

    root: Path
    python_files: List[Path] = field(default_factory=list)
    test_files: List[Path] = field(default_factory=list)
    config_files: List[Path] = field(default_factory=list)
    documentation_files: List[Path] = field(default_factory=list)
    has_tests: bool = False
    has_docs: bool = False
    has_src_layout: bool = False
    has_flat_layout: bool = False
    entry_points: List[Path] = field(default_factory=list)


@dataclass
class CodeMetrics:
    """Métriques de code pour un fichier ou projet."""

    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    functions_count: int = 0
    classes_count: int = 0
    imports_count: int = 0
    complexity_score: int = 0


@dataclass
class SecurityIssue:
    """Issue de sécurité détecté."""

    severity: str  # "high", "medium", "low"
    issue_type: str  # "hardcoded_secret", "sql_injection", "command_injection", etc.
    file_path: Path
    line_number: int
    description: str
    recommendation: str


@dataclass
class PackageInfo:
    """Information sur un package Python."""

    name: str
    version: str
    latest_version: Optional[str] = None
    is_outdated: bool = False
    license: Optional[str] = None
    homepage: Optional[str] = None
    has_vulnerabilities: bool = False
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TestResults:
    """Résultats d'exécution de tests."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    coverage_percent: Optional[float] = None
    failures: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class DockerInfo:
    """Information sur Docker dans le projet."""

    has_dockerfile: bool = False
    has_docker_compose: bool = False
    dockerfile_path: Optional[Path] = None
    compose_path: Optional[Path] = None
    base_images: List[str] = field(default_factory=list)
    exposed_ports: List[int] = field(default_factory=list)
    volumes: List[str] = field(default_factory=list)


@dataclass
class CIInfo:
    """Information sur l'intégration continue."""

    has_ci: bool = False
    ci_type: Optional[str] = None  # "github_actions", "gitlab_ci", "circle_ci", etc.
    config_path: Optional[Path] = None
    python_versions: List[str] = field(default_factory=list)
    has_tests: bool = False
    has_linting: bool = False
    has_coverage: bool = False


# -----------------------------
# Workspace management utilities
# -----------------------------


def set_selected_workspace(path: Pathish) -> bool:
    """Request workspace change from BC plugin.

    This function allows BC plugins to request a workspace directory change.
    The request is always accepted at the SDK level, with best-effort directory creation.

    Args:
        path: Target workspace directory path (str or Path object)

    Returns:
        bool: Always returns True (acceptance guaranteed by SDK contract)

    Behavior:
        - Auto-creates the target directory if missing
        - Invokes the GUI-side bridge when available (non-blocking)
        - Works in both GUI and headless environments

    Example:
        >>> from Plugins_SDK.BcPluginContext import set_selected_workspace
        >>> set_selected_workspace("/path/to/new/workspace")
        True
    """
    # Best-effort ensure the path exists
    try:
        p = Path(path)
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
    except Exception:
        pass
    # Try to inform the GUI when running with UI; ignore result and accept by contract
    try:
        from Core.MainWindow import request_workspace_change_from_BcPlugin  # type: ignore

        try:
            request_workspace_change_from_BcPlugin(str(path))
        except Exception:
            pass
    except Exception:
        # No GUI or bridge available — still accept
        pass
    return True


def get_workspace_info(workspace_path: Pathish) -> dict[str, Any]:
    """Get information about a workspace directory.

    Args:
        workspace_path: Path to the workspace directory

    Returns:
        dict: Information about the workspace including:
            - exists (bool): Whether directory exists
            - is_writable (bool): Whether directory is writable
            - python_files_count (int): Number of Python files
            - has_requirements (bool): Whether requirements.txt exists
            - has_pyproject (bool): Whether pyproject.toml exists
            - has_venv (bool): Whether virtual environment exists
            - size_bytes (int): Total size in bytes

    Example:
        >>> info = get_workspace_info("/path/to/workspace")
        >>> if info['exists'] and info['is_writable']:
        ...     print(f"Found {info['python_files_count']} Python files")
    """
    path = Path(workspace_path)
    info = {
        "exists": path.exists(),
        "is_writable": False,
        "python_files_count": 0,
        "has_requirements": False,
        "has_pyproject": False,
        "has_venv": False,
        "size_bytes": 0,
    }

    if not path.exists():
        return info

    try:
        info["is_writable"] = os.access(path, os.W_OK)
    except Exception:
        pass

    try:
        info["python_files_count"] = len(list(path.rglob("*.py")))
    except Exception:
        pass

    try:
        info["has_requirements"] = (path / "requirements.txt").exists()
    except Exception:
        pass

    try:
        info["has_pyproject"] = (path / "pyproject.toml").exists()
    except Exception:
        pass

    try:
        info["has_venv"] = (path / "venv").exists() or (path / ".venv").exists()
    except Exception:
        pass

    try:
        total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        info["size_bytes"] = total_size
    except Exception:
        pass

    return info


# -----------------------------
# File pattern utilities
# -----------------------------


def match_patterns(file_path: Pathish, patterns: List[str]) -> bool:
    """Check if a file matches any of the given glob patterns.

    Args:
        file_path: Path to check
        patterns: List of glob patterns (e.g., ["**/*.py", "*.txt"])

    Returns:
        bool: True if file matches any pattern, False otherwise

    Example:
        >>> match_patterns("src/main.py", ["**/*.py"])
        True
        >>> match_patterns("README.md", ["**/*.py"])
        False
    """
    try:
        path = Path(file_path)
        path_str = path.as_posix()

        for pattern in patterns:
            if fnmatch.fnmatch(path_str, pattern):
                return True
            if path.match(pattern):
                return True

        return False
    except Exception:
        return False


def find_files(
    root: Pathish,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
) -> Iterator[Path]:
    """Find files matching include patterns while excluding others.

    Args:
        root: Root directory to search
        include: Patterns to include (default: all files)
        exclude: Patterns to exclude (default: common cache/build dirs)
        max_depth: Maximum directory depth (None for unlimited)

    Yields:
        Path: Matching file paths

    Example:
        >>> for py_file in find_files(".", include=["**/*.py"], exclude=["**/test_*.py"]):
        ...     print(py_file)
    """
    root_path = Path(root)
    if not root_path.exists():
        return

    if include is None:
        include = ["**/*"]

    if exclude is None:
        exclude = [
            "**/__pycache__/**",
            "**/*.pyc",
            "**/venv/**",
            "**/.venv/**",
            "**/.git/**",
        ]

    def should_exclude(path: Path) -> bool:
        path_str = path.as_posix()
        for pattern in exclude:
            if fnmatch.fnmatch(path_str, pattern):
                return True
            if path.match(pattern):
                return True
        return False

    def get_depth(path: Path) -> int:
        try:
            return len(path.relative_to(root_path).parts)
        except ValueError:
            return 0

    for pattern in include:
        for file_path in root_path.glob(pattern):
            if not file_path.is_file():
                continue
            if should_exclude(file_path):
                continue
            if max_depth is not None and get_depth(file_path) > max_depth:
                continue
            yield file_path


def count_files_by_extension(
    root: Pathish, extensions: Optional[List[str]] = None
) -> dict[str, int]:
    """Count files by extension in a directory tree.

    Args:
        root: Root directory to search
        extensions: List of extensions to count (e.g., [".py", ".txt"])
                   If None, counts all extensions

    Returns:
        dict: Mapping of extension to count

    Example:
        >>> counts = count_files_by_extension(".", extensions=[".py", ".txt"])
        >>> print(f"Found {counts.get('.py', 0)} Python files")
    """
    root_path = Path(root)
    counts: dict[str, int] = {}

    if not root_path.exists():
        return counts

    try:
        for file_path in root_path.rglob("*"):
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()

            if extensions is not None and ext not in extensions:
                continue

            counts[ext] = counts.get(ext, 0) + 1
    except Exception:
        pass

    return counts


# -----------------------------
# Path utilities
# -----------------------------


def ensure_directory(path: Pathish) -> bool:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure exists

    Returns:
        bool: True if directory exists or was created successfully

    Example:
        >>> ensure_directory("build/output")
        True
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def is_python_project(path: Pathish) -> bool:
    """Check if a directory appears to be a Python project.

    Checks for common Python project indicators:
    - Python files (*.py)
    - requirements.txt
    - pyproject.toml
    - setup.py
    - setup.cfg

    Args:
        path: Directory path to check

    Returns:
        bool: True if directory appears to be a Python project

    Example:
        >>> if is_python_project("."):
        ...     print("This is a Python project")
    """
    path_obj = Path(path)

    if not path_obj.exists():
        return False

    # Check for Python files
    try:
        if next(path_obj.glob("*.py"), None) is not None:
            return True
    except Exception:
        pass

    # Check for common Python project files
    indicators = [
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "poetry.lock",
    ]

    for indicator in indicators:
        if (path_obj / indicator).exists():
            return True

    return False


def get_relative_path(path: Pathish, relative_to: Pathish) -> Optional[str]:
    """Get relative path string safely.

    Args:
        path: Path to convert
        relative_to: Base path

    Returns:
        str: Relative path string, or None if conversion fails

    Example:
        >>> get_relative_path("/home/user/project/src/main.py", "/home/user/project")
        'src/main.py'
    """
    try:
        return str(Path(path).relative_to(Path(relative_to)))
    except Exception:
        return None


# -----------------------------
# Gestionnaire d'environnements avancé
# -----------------------------


def detect_environment_manager(root: Pathish) -> Optional[str]:
    """Détecte le gestionnaire d'environnement utilisé dans le projet.

    Args:
        root: Répertoire racine du projet

    Returns:
        str: Type de gestionnaire ("poetry", "pipenv", "conda", "venv", "pip") ou None

    Example:
        >>> manager = detect_environment_manager(".")
        >>> if manager == "poetry":
        ...     print("Projet utilise Poetry")
    """
    root_path = Path(root)

    # Vérifier Poetry
    if (root_path / "poetry.lock").exists() or (root_path / "pyproject.toml").exists():
        try:
            with open(root_path / "pyproject.toml", "r") as f:
                content = f.read()
                if "[tool.poetry]" in content:
                    return "poetry"
        except Exception:
            pass

    # Vérifier Pipenv
    if (root_path / "Pipfile").exists():
        return "pipenv"

    # Vérifier Conda
    if (root_path / "environment.yml").exists() or (root_path / "conda.yml").exists():
        return "conda"

    # Vérifier venv
    if detect_venv(root_path):
        return "venv"

    # Vérifier pip simple
    if (root_path / "requirements.txt").exists():
        return "pip"

    return None


def get_python_version_from_project(root: Pathish) -> Optional[str]:
    """Extrait la version Python requise depuis les fichiers de configuration.

    Args:
        root: Répertoire racine du projet

    Returns:
        str: Version Python (ex: "3.9", ">=3.8") ou None

    Example:
        >>> version = get_python_version_from_project(".")
        >>> print(f"Requires Python {version}")
    """
    root_path = Path(root)

    # Vérifier pyproject.toml
    pyproject = root_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = parse_pyproject_toml(pyproject)
            # Poetry
            if "tool" in content and "poetry" in content["tool"]:
                python_ver = (
                    content["tool"]["poetry"].get("dependencies", {}).get("python")
                )
                if python_ver:
                    return str(python_ver)
            # PEP 621
            if "project" in content:
                requires_python = content["project"].get("requires-python")
                if requires_python:
                    return str(requires_python)
        except Exception:
            pass

    # Vérifier setup.py
    setup_py = root_path / "setup.py"
    if setup_py.exists():
        try:
            with open(setup_py, "r") as f:
                content = f.read()
                match = re.search(r'python_requires\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        except Exception:
            pass

    return None


def install_dependencies(
    root: Pathish, dev: bool = False, upgrade: bool = False
) -> Tuple[bool, str]:
    """Installe les dépendances du projet.

    Args:
        root: Répertoire racine du projet
        dev: Installer aussi les dépendances de développement
        upgrade: Mettre à jour les packages

    Returns:
        Tuple (succès, message)

    Example:
        >>> success, msg = install_dependencies(".", dev=True)
        >>> if success:
        ...     print("Dependencies installed")
    """
    root_path = Path(root)
    manager = detect_environment_manager(root_path)

    if not manager:
        return False, "Aucun gestionnaire d'environnement détecté"

    try:
        if manager == "poetry":
            cmd = ["poetry", "install"]
            if not dev:
                cmd.append("--no-dev")
            if upgrade:
                cmd = ["poetry", "update"]

        elif manager == "pipenv":
            cmd = ["pipenv", "install"]
            if dev:
                cmd.append("--dev")

        elif manager == "conda":
            cmd = ["conda", "env", "update", "-f", "environment.yml"]

        else:  # pip ou venv
            venv = detect_venv(root_path)
            if venv:
                if sys.platform == "win32":
                    pip_exe = venv / "Scripts" / "pip.exe"
                else:
                    pip_exe = venv / "bin" / "pip"
            else:
                pip_exe = "pip"

            cmd = [str(pip_exe), "install", "-r", "requirements.txt"]
            if upgrade:
                cmd.insert(2, "--upgrade")

        code, out, err = run_command(cmd, cwd=root_path, timeout=300)

        if code == 0:
            return True, f"Dépendances installées avec succès via {manager}"
        else:
            return False, f"Erreur lors de l'installation: {err}"

    except Exception as e:
        return False, f"Erreur: {str(e)}"


# -----------------------------
# Dependency analysis utilities
# -----------------------------


def parse_requirements_txt(path: Pathish) -> List[str]:
    """Parse requirements.txt file and extract package names.

    Args:
        path: Path to requirements.txt file

    Returns:
        List of package names (without version specifiers)

    Example:
        >>> deps = parse_requirements_txt("requirements.txt")
        >>> print(deps)  # ['numpy', 'pandas', 'requests']
    """
    requirements = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                # Skip options like -e, -r
                if line.startswith("-"):
                    continue
                # Extract package name (remove version specifiers)
                pkg = re.split(r"[=<>!]", line)[0].strip()
                if pkg:
                    requirements.append(pkg)
    except Exception:
        pass
    return requirements


def parse_pyproject_toml(path: Pathish) -> Dict[str, Any]:
    """Parse pyproject.toml file.

    Args:
        path: Path to pyproject.toml file

    Returns:
        Dictionary with parsed content

    Example:
        >>> info = parse_pyproject_toml("pyproject.toml")
        >>> print(info.get('project', {}).get('name'))
    """
    try:
        # Try tomli first (Python < 3.11)
        try:
            import tomli as tomllib #type:ignore
        except ImportError:
            import tomllib  # Python 3.11+

        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def get_project_dependencies(root: Pathish) -> DependencyInfo:
    """Get comprehensive dependency information from a project.

    Args:
        root: Project root directory

    Returns:
        DependencyInfo object with all found dependencies

    Example:
        >>> deps = get_project_dependencies(".")
        >>> print(f"Found {len(deps.all_dependencies)} unique dependencies")
    """
    root_path = Path(root)
    info = DependencyInfo()

    # Parse requirements.txt
    req_file = root_path / "requirements.txt"
    if req_file.exists():
        info.requirements_txt = parse_requirements_txt(req_file)
        info.all_dependencies.update(info.requirements_txt)

    # Parse pyproject.toml
    pyproject_file = root_path / "pyproject.toml"
    if pyproject_file.exists():
        info.pyproject_toml = parse_pyproject_toml(pyproject_file)
        # Extract dependencies from pyproject.toml
        try:
            project_deps = info.pyproject_toml.get("project", {}).get(
                "dependencies", []
            )
            for dep in project_deps:
                pkg = re.split(r"[=<>!]", dep)[0].strip()
                if pkg:
                    info.all_dependencies.add(pkg)
        except Exception:
            pass

    # Parse setup.py (basic extraction)
    setup_file = root_path / "setup.py"
    if setup_file.exists():
        try:
            with open(setup_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Try to extract install_requires
                match = re.search(
                    r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL
                )
                if match:
                    deps_str = match.group(1)
                    for dep in re.findall(r'["\']([^"\']+)["\']', deps_str):
                        pkg = re.split(r"[=<>!]", dep)[0].strip()
                        if pkg:
                            info.all_dependencies.add(pkg)
        except Exception:
            pass

    return info


def extract_imports_from_code(code: str) -> List[str]:
    """Extract import statements from Python code.

    Args:
        code: Python source code

    Returns:
        List of imported module names

    Example:
        >>> code = "import os\\nfrom pathlib import Path"
        >>> imports = extract_imports_from_code(code)
        >>> print(imports)  # ['os', 'pathlib']
    """
    imports = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])
    except Exception:
        pass
    return list(set(imports))

    # -----------------------------
    # Python file analysis utilities
    # -----------------------------


def analyze_python_file(path: Pathish) -> PythonFileInfo:
    """Analyze a Python file and extract information.

    Args:
        path: Path to Python file

    Returns:
        PythonFileInfo object with extracted information

    Example:
        >>> info = analyze_python_file("main.py")
        >>> if info.is_valid_syntax:
        ...     print(f"Found {len(info.functions)} functions")
    """
    file_path = Path(path)
    info = PythonFileInfo(path=file_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        info.line_count = len(code.splitlines())

        # Try to parse AST
        try:
            tree = ast.parse(code)
            info.is_valid_syntax = True

            # Extract docstring
            if isinstance(tree, ast.Module) and tree.body:
                if isinstance(tree.body[0], ast.Expr) and isinstance(
                    tree.body[0].value, ast.Str
                ):
                    info.docstring = tree.body[0].value.s
                elif isinstance(tree.body[0], ast.Expr) and isinstance(
                    tree.body[0].value, ast.Constant
                ):
                    info.docstring = str(tree.body[0].value.value)

            # Extract imports
            info.imports = extract_imports_from_code(code)

            # Extract functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    info.functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    info.classes.append(node.name)

        except SyntaxError as e:
            info.is_valid_syntax = False
            info.syntax_error = str(e)

    except Exception as e:
        info.syntax_error = str(e)

    return info


def validate_python_syntax(path: Pathish) -> Tuple[bool, Optional[str]]:
    """Check if a Python file has valid syntax.

    Args:
        path: Path to Python file

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> valid, error = validate_python_syntax("main.py")
        >>> if not valid:
        ...     print(f"Syntax error: {error}")
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def get_python_files_with_issues(
    root: Pathish, exclude: Optional[List[str]] = None
) -> List[Tuple[Path, str]]:
    """Find Python files with syntax errors.

    Args:
        root: Root directory to search
        exclude: Patterns to exclude

    Returns:
        List of tuples (file_path, error_message)

    Example:
        >>> issues = get_python_files_with_issues(".")
        >>> for file, error in issues:
        ...     print(f"{file}: {error}")
    """
    issues = []

    if exclude is None:
        exclude = ["**/__pycache__/**", "**/venv/**", "**/.venv/**"]

    for py_file in find_files(root, include=["**/*.py"], exclude=exclude):
        valid, error = validate_python_syntax(py_file)
        if not valid:
            issues.append((py_file, error))

    return issues

    # -----------------------------
    # Virtual environment utilities
    # -----------------------------


def detect_venv(root: Pathish) -> Optional[Path]:
    """Detect virtual environment in project.

    Args:
        root: Project root directory

    Returns:
        Path to venv directory if found, None otherwise

    Example:
        >>> venv_path = detect_venv(".")
        >>> if venv_path:
        ...     print(f"Found venv at {venv_path}")
    """
    root_path = Path(root)

    # Common venv directory names
    venv_names = ["venv", ".venv", "env", ".env", "virtualenv"]

    for name in venv_names:
        venv_path = root_path / name
        if venv_path.exists() and venv_path.is_dir():
            # Check if it's a valid venv
            if sys.platform == "win32":
                python_exe = venv_path / "Scripts" / "python.exe"
            else:
                python_exe = venv_path / "bin" / "python"

            if python_exe.exists():
                return venv_path

    return None


def get_venv_info(venv_path: Pathish) -> VenvInfo:
    """Get information about a virtual environment.

    Args:
        venv_path: Path to virtual environment directory

    Returns:
        VenvInfo object with venv information

    Example:
        >>> info = get_venv_info("venv")
        >>> if info.exists:
        ...     print(f"Python version: {info.python_version}")
    """
    venv_path_obj = Path(venv_path)
    info = VenvInfo(path=venv_path_obj)

    if not venv_path_obj.exists():
        return info

    info.exists = True

    # Get Python executable
    if sys.platform == "win32":
        python_exe = venv_path_obj / "Scripts" / "python.exe"
    else:
        python_exe = venv_path_obj / "bin" / "python"

    if not python_exe.exists():
        return info

    # Get Python version
    try:
        result = subprocess.run(
            [str(python_exe), "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            info.python_version = result.stdout.strip() or result.stderr.strip()
    except Exception:
        pass

    # Get pip version
    try:
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info.pip_version = result.stdout.strip()
    except Exception:
        pass

    # Get installed packages
    try:
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            info.installed_packages = {pkg["name"]: pkg["version"] for pkg in packages}
    except Exception:
        pass

    # Check if active
    try:
        info.is_active = sys.prefix == str(venv_path_obj.resolve())
    except Exception:
        pass

    return info

    # -----------------------------
    # Git utilities
    # -----------------------------


def get_git_info(root: Pathish) -> GitInfo:
    """Get Git repository information.

    Args:
        root: Project root directory

    Returns:
        GitInfo object with repository information

    Example:
        >>> git = get_git_info(".")
        >>> if git.is_repo and git.has_uncommitted:
        ...     print("Warning: Uncommitted changes found")
    """
    root_path = Path(root)
    info = GitInfo()

    # Check if Git repo
    git_dir = root_path / ".git"
    if not git_dir.exists():
        return info

    info.is_repo = True

    try:
        # Get current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info.branch = result.stdout.strip()
    except Exception:
        pass

    try:
        # Get staged files
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            cwd=root_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info.staged_files = [f for f in result.stdout.strip().split("\n") if f]
    except Exception:
        pass

    try:
        # Get modified files
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=root_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info.modified_files = [f for f in result.stdout.strip().split("\n") if f]
    except Exception:
        pass

    try:
        # Get untracked files
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info.untracked_files = [f for f in result.stdout.strip().split("\n") if f]
    except Exception:
        pass

    info.has_uncommitted = bool(info.staged_files or info.modified_files)

    try:
        # Get last commit
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%H %s"],
            cwd=root_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info.last_commit = result.stdout.strip()
    except Exception:
        pass

    return info

    # -----------------------------
    # Project structure analysis
    # -----------------------------


def analyze_project_structure(root: Pathish) -> ProjectStructureInfo:
    """Analyze project structure and organization.

    Args:
            root: Project root directory

    Returns:
            ProjectStructureInfo object with project structure information

    Example:
            >>> struct = analyze_project_structure(".")
            >>> if struct.has_src_layout:
            ...     print("Project uses src/ layout")
    """
    root_path = Path(root)
    info = ProjectStructureInfo(root=root_path)

    # Find Python files
    try:
        for py_file in root_path.rglob("*.py"):
            # Skip venv and cache
            if any(
                p in py_file.parts for p in ["venv", ".venv", "__pycache__", ".git"]
            ):
                continue

            info.python_files.append(py_file)

            # Check if test file
            if "test" in py_file.name.lower() or "tests" in py_file.parts:
                info.test_files.append(py_file)
    except Exception:
        pass

    # Check for common entry points
    for entry_name in ["main.py", "app.py", "run.py", "__main__.py", "cli.py"]:
        entry_path = root_path / entry_name
        if entry_path.exists():
            info.entry_points.append(entry_path)

    # Check for config files
    config_files = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "poetry.lock",
        "tox.ini",
        "pytest.ini",
        ".flake8",
        "mypy.ini",
        ".pylintrc",
        "setup.cfg",
    ]
    for config_name in config_files:
        config_path = root_path / config_name
        if config_path.exists():
            info.config_files.append(config_path)

    # Check for documentation
    doc_paths = [
        root_path / "docs",
        root_path / "documentation",
        root_path / "README.md",
    ]
    for doc_path in doc_paths:
        if doc_path.exists():
            info.documentation_files.append(doc_path)
            info.has_docs = True

    # Check layout type
    info.has_tests = len(info.test_files) > 0
    info.has_src_layout = (root_path / "src").exists()
    info.has_flat_layout = not info.has_src_layout and len(info.python_files) > 0

    return info

    # -----------------------------
    # File operations utilities
    # -----------------------------


def safe_backup_file(path: Pathish, backup_suffix: str = ".bak") -> Optional[Path]:
    """Create a backup of a file.

    Args:
        path: File to backup
        backup_suffix: Suffix for backup file

    Returns:
        Path to backup file if successful, None otherwise

    Example:
        >>> backup = safe_backup_file("config.json")
        >>> if backup:
        ...     print(f"Backup created at {backup}")
    """
    try:
        src = Path(path)
        if not src.exists():
            return None

        backup = src.with_suffix(src.suffix + backup_suffix)
        shutil.copy2(src, backup)
        return backup
    except Exception:
        return None


def safe_restore_file(backup_path: Pathish, remove_backup: bool = True) -> bool:
    """Restore a file from backup.

    Args:
        backup_path: Path to backup file
        remove_backup: Whether to remove backup after restore

    Returns:
        bool: True if restore successful

    Example:
        >>> if safe_restore_file("config.json.bak"):
        ...     print("File restored successfully")
    """
    try:
        backup = Path(backup_path)
        if not backup.exists():
            return False

        # Get original path by removing backup suffix
        original = backup.with_suffix("")

        shutil.copy2(backup, original)

        if remove_backup:
            backup.unlink()

        return True
    except Exception:
        return False


def calculate_file_hash(path: Pathish, algorithm: str = "sha256") -> Optional[str]:
    """Calculate hash of a file.

    Args:
        path: File to hash
        algorithm: Hash algorithm (md5, sha1, sha256, sha512)

    Returns:
        str: Hex digest of file hash, or None on error

    Example:
        >>> hash_val = calculate_file_hash("large_file.bin")
        >>> print(f"SHA256: {hash_val}")
    """
    try:
        hasher = hashlib.new(algorithm)

        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)

        return hasher.hexdigest()
    except Exception:
        return None


def get_directory_size(
    path: Pathish, exclude_patterns: Optional[List[str]] = None
) -> int:
    """Calculate total size of directory.

    Args:
        path: Directory path
        exclude_patterns: Patterns to exclude from calculation

    Returns:
        int: Total size in bytes

    Example:
        >>> size = get_directory_size(".", exclude_patterns=["**/venv/**"])
        >>> print(f"Size: {size / 1024 / 1024:.2f} MB")
    """
    total = 0
    path_obj = Path(path)

    if not path_obj.exists():
        return 0

    if exclude_patterns is None:
        exclude_patterns = []

    def should_exclude(file_path: Path) -> bool:
        path_str = file_path.as_posix()
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(path_str, pattern):
                return True
        return False

    try:
        for item in path_obj.rglob("*"):
            if item.is_file() and not should_exclude(item):
                try:
                    total += item.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass

    return total


def clean_pycache(root: Pathish, dry_run: bool = False) -> Tuple[int, int]:
    """Remove __pycache__ directories and .pyc files.

    Args:
        root: Root directory to clean
        dry_run: If True, only count without removing

    Returns:
        Tuple of (files_removed, dirs_removed)

    Example:
        >>> files, dirs = clean_pycache(".", dry_run=True)
        >>> print(f"Would remove {files} files and {dirs} directories")
    """
    files_removed = 0
    dirs_removed = 0
    root_path = Path(root)

    try:
        # Remove .pyc files
        for pyc_file in root_path.rglob("*.pyc"):
            if dry_run:
                files_removed += 1
            else:
                try:
                    pyc_file.unlink()
                    files_removed += 1
                except Exception:
                    pass

        # Remove __pycache__ directories
        for pycache_dir in root_path.rglob("__pycache__"):
            if pycache_dir.is_dir():
                if dry_run:
                    dirs_removed += 1
                else:
                    try:
                        shutil.rmtree(pycache_dir)
                        dirs_removed += 1
                    except Exception:
                        pass
    except Exception:
        pass

    return files_removed, dirs_removed

    # -----------------------------
    # Process execution utilities
    # -----------------------------


def run_command(
    command: List[str],
    cwd: Optional[Pathish] = None,
    timeout: Optional[int] = None,
    capture_output: bool = True,
    check: bool = False,
) -> Tuple[int, str, str]:
    """Run a command safely.

    Args:
        command: Command and arguments as list
        cwd: Working directory
        timeout: Timeout in seconds
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise on non-zero exit

    Returns:
        Tuple of (returncode, stdout, stderr)

    Example:
        >>> code, out, err = run_command(["python", "--version"])
        >>> if code == 0:
        ...     print(f"Python version: {out}")
    """
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            check=check,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout or "", e.stderr or ""
    except Exception as e:
        return -1, "", str(e)


def check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH.

    Args:
        command: Command name to check

    Returns:
        bool: True if command exists

    Example:
        >>> if check_command_exists("git"):
        ...     print("Git is available")
    """
    try:
        if sys.platform == "win32":
            result = subprocess.run(["where", command], capture_output=True, timeout=5)
        else:
            result = subprocess.run(["which", command], capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False

    # -----------------------------
    # Validation utilities
    # -----------------------------


def validate_python_project(root: Pathish) -> Dict[str, Any]:
    """Validate Python project structure and configuration.

    Args:
        root: Project root directory

    Returns:
        Dictionary with validation results

    Example:
        >>> results = validate_python_project(".")
        >>> if not results['is_valid']:
        ...     for issue in results['issues']:
        ...         print(f"Issue: {issue}")
    """
    root_path = Path(root)
    results = {
        "is_valid": True,
        "issues": [],
        "warnings": [],
        "info": {},
    }

    # Check if directory exists
    if not root_path.exists():
        results["is_valid"] = False
        results["issues"].append("Project directory does not exist")
        return results

    # Check for Python files
    py_files = list(root_path.rglob("*.py"))
    if not py_files:
        results["is_valid"] = False
        results["issues"].append("No Python files found")
        return results

    results["info"]["python_files_count"] = len(py_files)

    # Check for dependency files
    has_deps = False
    for dep_file in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]:
        if (root_path / dep_file).exists():
            has_deps = True
            break

    if not has_deps:
        results["warnings"].append(
            "No dependency file found (requirements.txt, pyproject.toml, etc.)"
        )

    # Check for venv
    venv = detect_venv(root_path)
    if not venv:
        results["warnings"].append("No virtual environment found")
    else:
        results["info"]["venv_path"] = str(venv)

    # Check for tests
    test_files = [f for f in py_files if "test" in f.name.lower()]
    if not test_files:
        results["warnings"].append("No test files found")
    else:
        results["info"]["test_files_count"] = len(test_files)

    # Check for syntax errors
    syntax_issues = get_python_files_with_issues(root_path)
    if syntax_issues:
        results["is_valid"] = False
        for file, error in syntax_issues:
            results["issues"].append(f"Syntax error in {file}: {error}")

    # Check for README
    readme_files = ["README.md", "README.rst", "README.txt", "README"]
    has_readme = any((root_path / readme).exists() for readme in readme_files)
    if not has_readme:
        results["warnings"].append("No README file found")

    return results

    # -----------------------------
    # Cache management utilities
    # -----------------------------


_plugin_cache: Dict[str, Any] = {}


def cache_set(plugin_id: str, key: str, value: Any) -> None:
    """Set a value in plugin cache.

    Args:
        plugin_id: Plugin identifier
        key: Cache key
        value: Value to cache

    Example:
        >>> cache_set("my.plugin", "processed_files", file_list)
    """
    cache_key = f"{plugin_id}:{key}"
    _plugin_cache[cache_key] = value


def cache_get(plugin_id: str, key: str, default: Any = None) -> Any:
    """Get a value from plugin cache.

    Args:
        plugin_id: Plugin identifier
        key: Cache key
        default: Default value if key not found

    Returns:
        Cached value or default

    Example:
        >>> files = cache_get("my.plugin", "processed_files", [])
    """
    cache_key = f"{plugin_id}:{key}"
    return _plugin_cache.get(cache_key, default)


def cache_clear(plugin_id: Optional[str] = None) -> None:
    """Clear plugin cache.

    Args:
        plugin_id: Plugin identifier, or None to clear all

    Example:
        >>> cache_clear("my.plugin")  # Clear specific plugin
        >>> cache_clear()  # Clear all plugins
    """
    global _plugin_cache
    if plugin_id is None:
        _plugin_cache.clear()
    else:
        keys_to_remove = [
            k for k in _plugin_cache.keys() if k.startswith(f"{plugin_id}:")
        ]
        for key in keys_to_remove:
            del _plugin_cache[key]

    # -----------------------------
    # Report generation utilities
    # -----------------------------


def get_outdated_packages(root: Pathish) -> List[PackageInfo]:
    """Liste les packages obsolètes dans le projet.

    Args:
    root: Répertoire racine du projet

    Returns:
        Liste de PackageInfo pour les packages obsolètes

    Example:
        >>> outdated = get_outdated_packages(".")
        >>> for pkg in outdated:
        ...     print(f"{pkg.name}: {pkg.version} -> {pkg.latest_version}")
    """
    root_path = Path(root)
    outdated = []

    venv = detect_venv(root_path)
    if not venv:
        return outdated

    if sys.platform == "win32":
        pip_exe = venv / "Scripts" / "pip.exe"
    else:
        pip_exe = venv / "bin" / "pip"

    if not pip_exe.exists():
        return outdated

    try:
        code, out, err = run_command(
            [str(pip_exe), "list", "--outdated", "--format=json"],
            cwd=root_path,
            timeout=60,
        )

        if code == 0:
            packages = json.loads(out)
            for pkg in packages:
                info = PackageInfo(
                    name=pkg.get("name", ""),
                    version=pkg.get("version", ""),
                    latest_version=pkg.get("latest_version", ""),
                    is_outdated=True,
                )
                outdated.append(info)
    except Exception:
        pass

    return outdated


# -----------------------------
# Métriques de code
# -----------------------------


def calculate_code_metrics(path: Pathish) -> CodeMetrics:
    """Calcule les métriques de code pour un fichier Python.

    Args:
        path: Chemin du fichier Python

    Returns:
        CodeMetrics avec les statistiques

    Example:
        >>> metrics = calculate_code_metrics("main.py")
        >>> print(f"LOC: {metrics.code_lines}, Comments: {metrics.comment_lines}")
    """
    metrics = CodeMetrics()

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        metrics.total_lines = len(lines)

        in_docstring = False
        docstring_char = None

        for line in lines:
            stripped = line.strip()

            # Ligne vide
            if not stripped:
                metrics.blank_lines += 1
                continue

            # Gestion des docstrings
            if '"""' in stripped or "'''" in stripped:
                if not in_docstring:
                    docstring_char = '"""' if '"""' in stripped else "'''"
                    in_docstring = True
                    metrics.comment_lines += 1
                    if stripped.count(docstring_char) >= 2:
                        in_docstring = False
                    continue
                else:
                    metrics.comment_lines += 1
                    if docstring_char in stripped:
                        in_docstring = False
                    continue

            if in_docstring:
                metrics.comment_lines += 1
                continue

            # Commentaire simple
            if stripped.startswith("#"):
                metrics.comment_lines += 1
                continue

            # Ligne de code
            metrics.code_lines += 1

        # Analyser l'AST pour les fonctions/classes
        try:
            info = analyze_python_file(path)
            metrics.functions_count = len(info.functions)
            metrics.classes_count = len(info.classes)
            metrics.imports_count = len(info.imports)
        except Exception:
            pass

    except Exception:
        pass

    return metrics


def calculate_project_metrics(root: Pathish) -> Dict[str, Any]:
    """Calcule les métriques pour tout un projet.

    Args:
    root: Répertoire racine du projet

    Returns:
    Dictionnaire avec métriques agrégées

    Example:
    >>> metrics = calculate_project_metrics(".")
    >>> print(f"Total LOC: {metrics['total_code_lines']}")
    """
    root_path = Path(root)
    total_metrics = {
        "total_files": 0,
        "total_lines": 0,
        "total_code_lines": 0,
        "total_comment_lines": 0,
        "total_blank_lines": 0,
        "total_functions": 0,
        "total_classes": 0,
        "files_with_issues": 0,
    }

    for py_file in find_files(root_path, include=["**/*.py"]):
        total_metrics["total_files"] += 1

        metrics = calculate_code_metrics(py_file)
        total_metrics["total_lines"] += metrics.total_lines
        total_metrics["total_code_lines"] += metrics.code_lines
        total_metrics["total_comment_lines"] += metrics.comment_lines
        total_metrics["total_blank_lines"] += metrics.blank_lines
        total_metrics["total_functions"] += metrics.functions_count
        total_metrics["total_classes"] += metrics.classes_count

        if not analyze_python_file(py_file).is_valid_syntax:
            total_metrics["files_with_issues"] += 1

    return total_metrics


# -----------------------------
# Analyse de sécurité
# -----------------------------


def scan_for_secrets(root: Pathish) -> List[SecurityIssue]:
    """Scanne le code pour détecter des secrets hardcodés.

    Args:
        root: Répertoire racine du projet

    Returns:
        Liste de SecurityIssue détectés

    Example:
        >>> issues = scan_for_secrets(".")
        >>> for issue in issues:
        ...     print(f"Secret trouvé: {issue.file_path}:{issue.line_number}")
    """
    issues = []
    root_path = Path(root)

    # Patterns pour détecter les secrets
    patterns = {
        "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "api_key": re.compile(
            r'api[_-]?key["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE
        ),
        "password": re.compile(
            r'password["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE
        ),
        "token": re.compile(r'token["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
        "secret": re.compile(
            r'secret["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE
        ),
        "private_key": re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
    }

    for py_file in find_files(
        root_path, include=["**/*.py", "**/*.json", "**/*.yml", "**/*.yaml"]
    ):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    for issue_type, pattern in patterns.items():
                        if pattern.search(line):
                            issue = SecurityIssue(
                                severity="high",
                                issue_type=f"hardcoded_{issue_type}",
                                file_path=py_file,
                                line_number=line_num,
                                description=f"Possible {issue_type} hardcodé détecté",
                                recommendation="Utiliser des variables d'environnement ou un gestionnaire de secrets",
                            )
                            issues.append(issue)
        except Exception:
            continue

    return issues


def check_dangerous_imports(root: Pathish) -> List[SecurityIssue]:
    """Détecte les imports potentiellement dangereux.

    Args:
        root: Répertoire racine du projet

    Returns:
        Liste de SecurityIssue pour imports dangereux

    Example:
        >>> issues = check_dangerous_imports(".")
        >>> if issues:
        ...     print(f"Trouvé {len(issues)} imports dangereux")
    """
    issues = []
    root_path = Path(root)

    dangerous_modules = {
        "eval": "L'utilisation d'eval() peut exécuter du code arbitraire",
        "exec": "L'utilisation d'exec() peut exécuter du code arbitraire",
        "pickle": "pickle peut exécuter du code arbitraire lors du désérialization",
        "subprocess.call": "Vérifier que les entrées utilisateur sont sanitisées",
        "os.system": "os.system peut être vulnérable aux injections de commandes",
    }

    for py_file in find_files(root_path, include=["**/*.py"]):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                code = f.read()

            for module, warning in dangerous_modules.items():
                if module in code:
                    # Trouver le numéro de ligne
                    for line_num, line in enumerate(code.split("\n"), 1):
                        if module in line:
                            issue = SecurityIssue(
                                severity="medium",
                                issue_type="dangerous_import",
                                file_path=py_file,
                                line_number=line_num,
                                description=f"Utilisation de {module}",
                                recommendation=warning,
                            )
                            issues.append(issue)
                            break
        except Exception:
            continue

    return issues


# -----------------------------
# Gestion de versions
# -----------------------------


def get_current_version(root: Pathish) -> Optional[str]:
    """Extrait la version actuelle du projet.

    Args:
        root: Répertoire racine du projet

    Returns:
        Version actuelle ou None

    Example:
        >>> version = get_current_version(".")
        >>> print(f"Version actuelle: {version}")
    """
    root_path = Path(root)

    # Vérifier pyproject.toml
    pyproject = root_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = parse_pyproject_toml(pyproject)
            # Poetry
            if "tool" in content and "poetry" in content["tool"]:
                version = content["tool"]["poetry"].get("version")
                if version:
                    return str(version)
            # PEP 621
            if "project" in content:
                version = content["project"].get("version")
                if version:
                    return str(version)
        except Exception:
            pass

    # Vérifier setup.py
    setup_py = root_path / "setup.py"
    if setup_py.exists():
        try:
            with open(setup_py, "r") as f:
                content = f.read()
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        except Exception:
            pass

    # Vérifier __init__.py
    for init_file in root_path.rglob("__init__.py"):
        try:
            with open(init_file, "r") as f:
                content = f.read()
                match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        except Exception:
            continue

    return None


def bump_version(root: Pathish, bump_type: str = "patch") -> Tuple[bool, str, str]:
    """Incrémente la version du projet.

    Args:
        root: Répertoire racine du projet
        bump_type: Type de bump ("major", "minor", "patch")

    Returns:
        Tuple (succès, ancienne_version, nouvelle_version)

    Example:
        >>> success, old, new = bump_version(".", "minor")
        >>> if success:
        ...     print(f"Version: {old} -> {new}")
    """
    root_path = Path(root)
    current = get_current_version(root_path)

    if not current:
        return False, "", "Version actuelle non trouvée"

    try:
        # Parser la version
        parts = current.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2].split("-")[0]) if len(parts) > 2 else 0

        # Incrémenter selon le type
        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        else:  # patch
            patch += 1

        new_version = f"{major}.{minor}.{patch}"

        # Mettre à jour les fichiers
        # TODO: Implémenter la mise à jour réelle des fichiers

        return True, current, new_version

    except Exception as e:
        return False, current, f"Erreur: {str(e)}"


# -----------------------------
# Tests et couverture
# -----------------------------


def run_tests(root: Pathish, coverage: bool = False) -> TestResults:
    """Exécute les tests du projet.

    Args:
        root: Répertoire racine du projet
        coverage: Activer la couverture de code

    Returns:
        TestResults avec les résultats

    Example:
        >>> results = run_tests(".", coverage=True)
        >>> print(f"Tests: {results.passed}/{results.total} passés")
    """
    root_path = Path(root)
    results = TestResults()

    # Détecter le framework de test
    has_pytest = (root_path / "pytest.ini").exists() or (
        root_path / "pyproject.toml"
    ).exists()
    has_unittest = any(f.name.startswith("test_") for f in root_path.rglob("test_*.py"))

    if not (has_pytest or has_unittest):
        return results

    try:
        if has_pytest:
            cmd = ["pytest", "-v"]
            if coverage:
                cmd.extend(["--cov", "--cov-report=json"])
        else:
            cmd = ["python", "-m", "unittest", "discover"]

        start_time = time.time()
        code, out, err = run_command(cmd, cwd=root_path, timeout=300)
        results.duration_seconds = time.time() - start_time

        # Parser les résultats pytest
        if has_pytest:
            if "passed" in out:
                match = re.search(r"(\d+) passed", out)
                if match:
                    results.passed = int(match.group(1))
            if "failed" in out:
                match = re.search(r"(\d+) failed", out)
                if match:
                    results.failed = int(match.group(1))
            if "skipped" in out:
                match = re.search(r"(\d+) skipped", out)
                if match:
                    results.skipped = int(match.group(1))

            results.total = results.passed + results.failed + results.skipped

            # Lire la couverture si disponible
            if coverage:
                coverage_file = root_path / "coverage.json"
                if coverage_file.exists():
                    try:
                        with open(coverage_file, "r") as f:
                            cov_data = json.loads(f.read())
                            results.coverage_percent = cov_data.get("totals", {}).get(
                                "percent_covered"
                            )
                    except Exception:
                        pass

    except Exception:
        pass

    return results


# -----------------------------
# Docker support
# -----------------------------


def analyze_docker_config(root: Pathish) -> DockerInfo:
    """Analyse la configuration Docker du projet.

    Args:
        root: Répertoire racine du projet

    Returns:
        DockerInfo avec les informations Docker

    Example:
        >>> docker = analyze_docker_config(".")
        >>> if docker.has_dockerfile:
        ...     print(f"Base image: {docker.base_images[0]}")
    """
    root_path = Path(root)
    info = DockerInfo()

    # Vérifier Dockerfile
    dockerfile = root_path / "Dockerfile"
    if dockerfile.exists():
        info.has_dockerfile = True
        info.dockerfile_path = dockerfile

        try:
            with open(dockerfile, "r") as f:
                content = f.read()

                # Extraire l'image de base
                for line in content.split("\n"):
                    if line.strip().startswith("FROM"):
                        image = line.split("FROM")[1].strip().split()[0]
                        info.base_images.append(image)

                    # Extraire les ports exposés
                    elif line.strip().startswith("EXPOSE"):
                        ports = line.split("EXPOSE")[1].strip().split()
                        info.exposed_ports.extend(
                            [int(p) for p in ports if p.isdigit()]
                        )

                    # Extraire les volumes
                    elif line.strip().startswith("VOLUME"):
                        volume = line.split("VOLUME")[1].strip()
                        info.volumes.append(volume)
        except Exception:
            pass

    # Vérifier docker-compose
    for compose_name in ["docker-compose.yml", "docker-compose.yaml"]:
        compose_file = root_path / compose_name
        if compose_file.exists():
            info.has_docker_compose = True
            info.compose_path = compose_file
            break

    return info


# -----------------------------
# CI/CD Detection
# -----------------------------


def analyze_ci_config(root: Pathish) -> CIInfo:
    """Analyse la configuration CI/CD du projet.

    Args:
        root: Répertoire racine du projet

    Returns:
        CIInfo avec les informations CI/CD

    Example:
        >>> ci = analyze_ci_config(".")
        >>> if ci.has_ci:
        ...     print(f"CI: {ci.ci_type}")
    """
    root_path = Path(root)
    info = CIInfo()

    # GitHub Actions
    github_workflows = root_path / ".github" / "workflows"
    if github_workflows.exists():
        info.has_ci = True
        info.ci_type = "github_actions"

        for workflow_file in github_workflows.glob("*.yml"):
            info.config_path = workflow_file

            try:
                with open(workflow_file, "r") as f:
                    content = f.read()

                    # Extraire les versions Python
                    if "python-version" in content:
                        versions = re.findall(
                            r"python-version:\s*\[([^\]]+)\]", content
                        )
                        if versions:
                            info.python_versions = [
                                v.strip().strip("\"'") for v in versions[0].split(",")
                            ]

                    # Vérifier les steps
                    info.has_tests = "pytest" in content or "unittest" in content
                    info.has_linting = (
                        "flake8" in content or "pylint" in content or "ruff" in content
                    )
                    info.has_coverage = "coverage" in content or "codecov" in content
            except Exception:
                pass

            break

    # GitLab CI
    gitlab_ci = root_path / ".gitlab-ci.yml"
    if gitlab_ci.exists():
        info.has_ci = True
        info.ci_type = "gitlab_ci"
        info.config_path = gitlab_ci

    # Circle CI
    circle_ci = root_path / ".circleci" / "config.yml"
    if circle_ci.exists():
        info.has_ci = True
        info.ci_type = "circle_ci"
        info.config_path = circle_ci

    # Travis CI
    travis_ci = root_path / ".travis.yml"
    if travis_ci.exists():
        info.has_ci = True
        info.ci_type = "travis_ci"
        info.config_path = travis_ci

    return info


# -----------------------------
# Network utilities
# -----------------------------


def download_file(url: str, destination: Pathish, timeout: int = 30) -> bool:
    """Télécharge un fichier depuis une URL.

    Args:
        url: URL du fichier
        destination: Chemin de destination
        timeout: Timeout en secondes

    Returns:
        bool: True si succès

    Example:
        >>> if download_file("https://example.com/file.txt", "file.txt"):
        ...     print("Téléchargement réussi")
    """
    try:
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        req = urllib.request.Request(url)
        req.add_header("User-Agent", "PyCompiler-BC-Plugin/1.0")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            with open(dest_path, "wb") as out_file:
                out_file.write(response.read())

        return True
    except Exception:
        return False


def check_url_accessible(url: str, timeout: int = 10) -> bool:
    """Vérifie si une URL est accessible.

    Args:
        url: URL à vérifier
        timeout: Timeout en secondes

    Returns:
        bool: True si accessible

    Example:
        >>> if check_url_accessible("https://pypi.org"):
        ...     print("PyPI est accessible")
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(parsed.netloc, timeout=timeout)
        else:
            conn = http.client.HTTPConnection(parsed.netloc, timeout=timeout)

        conn.request("HEAD", parsed.path or "/")
        response = conn.getresponse()
        conn.close()

        return response.status < 400
    except Exception:
        return False


def get_external_ip() -> Optional[str]:
    """Obtient l'adresse IP externe.

    Returns:
        str: Adresse IP ou None

    Example:
        >>> ip = get_external_ip()
        >>> if ip:
        ...     print(f"IP externe: {ip}")
    """
    try:
        req = urllib.request.Request("https://api.ipify.org?format=json")
        req.add_header("User-Agent", "PyCompiler-BC-Plugin/1.0")

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())
            return data.get("ip")
    except Exception:
        return None


# -----------------------------
# Recherche et remplacement avancés
# -----------------------------


def search_in_files(
    root: Pathish,
    pattern: Union[str, Pattern],
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    case_sensitive: bool = True,
) -> List[Tuple[Path, int, str]]:
    """Recherche un pattern dans les fichiers.

    Args:
        root: Répertoire racine
        pattern: Pattern à rechercher (str ou regex compilé)
        include: Patterns de fichiers à inclure
        exclude: Patterns de fichiers à exclure
        case_sensitive: Recherche sensible à la casse

    Returns:
        Liste de tuples (fichier, ligne, contenu)

    Example:
        >>> results = search_in_files(".", "TODO", include=["**/*.py"])
        >>> for file, line, content in results:
        ...     print(f"{file}:{line}: {content}")
    """
    results = []
    root_path = Path(root)

    if isinstance(pattern, str):
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
    else:
        regex = pattern

    if include is None:
        include = ["**/*"]

    for file_path in find_files(root_path, include=include, exclude=exclude):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        results.append((file_path, line_num, line.rstrip()))
        except Exception:
            continue

    return results


def replace_in_files(
    root: Pathish,
    search_pattern: Union[str, Pattern],
    replacement: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict[Path, int]:
    """Remplace un pattern dans les fichiers.

    Args:
        root: Répertoire racine
        search_pattern: Pattern à rechercher
        replacement: Texte de remplacement
        include: Patterns de fichiers à inclure
        exclude: Patterns de fichiers à exclure
        dry_run: Si True, ne modifie pas les fichiers

    Returns:
        Dictionnaire {fichier: nombre_de_remplacements}

    Example:
        >>> changes = replace_in_files(".", "TODO", "DONE", include=["**/*.py"], dry_run=True)
        >>> print(f"Fichiers affectés: {len(changes)}")
    """
    changes = {}
    root_path = Path(root)

    if isinstance(search_pattern, str):
        regex = re.compile(search_pattern)
    else:
        regex = search_pattern

    if include is None:
        include = ["**/*"]

    for file_path in find_files(root_path, include=include, exclude=exclude):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content, count = regex.subn(replacement, content)

            if count > 0:
                changes[file_path] = count

                if not dry_run:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
        except Exception:
            continue

    return changes


# -----------------------------
# Génération de documentation
# -----------------------------


def generate_requirements_from_imports(root: Pathish) -> List[str]:
    """Génère une liste de requirements à partir des imports.

    Args:
        root: Répertoire racine du projet

    Returns:
        Liste de packages requis

    Example:
        >>> requirements = generate_requirements_from_imports(".")
        >>> for req in requirements:
        ...     print(req)
    """
    root_path = Path(root)
    all_imports = set()

    # Modules stdlib à exclure
    stdlib_modules = (
        set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
    )

    for py_file in find_files(root_path, include=["**/*.py"]):
        try:
            info = analyze_python_file(py_file)
            all_imports.update(info.imports)
        except Exception:
            continue

    # Filtrer les modules stdlib
    external_packages = [imp for imp in all_imports if imp not in stdlib_modules]

    return sorted(external_packages)


def generate_readme(
    root: Pathish, project_name: Optional[str] = None, description: Optional[str] = None
) -> str:
    """Génère un README.md basique pour le projet.

    Args:
        root: Répertoire racine du projet
        project_name: Nom du projet
        description: Description du projet

    Returns:
        str: Contenu du README

    Example:
        >>> readme = generate_readme(".", "Mon Projet", "Un super projet Python")
        >>> with open("README.md", "w") as f:
        ...     f.write(readme)
    """
    root_path = Path(root)

    if not project_name:
        project_name = root_path.name

    if not description:
        description = f"Description du projet {project_name}"

    # Analyser le projet
    struct = analyze_project_structure(root_path)
    deps = get_project_dependencies(root_path)
    version = get_current_version(root_path)

    sections = []

    # En-tête
    sections.append(f"# {project_name}")
    sections.append("")
    sections.append(description)
    sections.append("")

    # Version
    if version:
        sections.append(f"**Version:** {version}")
        sections.append("")

    # Installation
    sections.append("## Installation")
    sections.append("")
    sections.append("```bash")

    if (root_path / "pyproject.toml").exists():
        sections.append("poetry install")
    elif (root_path / "Pipfile").exists():
        sections.append("pipenv install")
    else:
        sections.append("pip install -r requirements.txt")

    sections.append("```")
    sections.append("")

    # Usage
    if struct.entry_points:
        sections.append("## Usage")
        sections.append("")
        sections.append("```bash")
        sections.append(f"python {struct.entry_points[0].name}")
        sections.append("```")
        sections.append("")

    # Structure
    sections.append("## Structure du projet")
    sections.append("")
    sections.append(f"- **Fichiers Python:** {len(struct.python_files)}")
    sections.append(f"- **Fichiers de test:** {len(struct.test_files)}")
    sections.append(f"- **Fichiers de configuration:** {len(struct.config_files)}")
    sections.append("")

    # Dépendances
    if deps.all_dependencies:
        sections.append("## Dépendances")
        sections.append("")
        for dep in sorted(deps.all_dependencies):
            sections.append(f"- {dep}")
        sections.append("")

    # Tests
    if struct.has_tests:
        sections.append("## Tests")
        sections.append("")
        sections.append("```bash")
        sections.append("pytest")
        sections.append("```")
        sections.append("")

    # License
    sections.append("## License")
    sections.append("")
    sections.append("À définir")
    sections.append("")

    return "\n".join(sections)


# -----------------------------
# Utilitaires de temps et monitoring
# -----------------------------


class Timer:
    """Gestionnaire de contexte pour mesurer le temps d'exécution.

    Example:
        >>> with Timer() as t:
        ...     # Code à mesurer
        ...     pass
        >>> print(f"Durée: {t.elapsed:.2f}s")
    """


def __init__(self):
    self.start_time = None
    self.end_time = None
    self.elapsed = 0.0


def __enter__(self):
    self.start_time = time.time()
    return self


def __exit__(self, *args):
    self.end_time = time.time()
    self.elapsed = self.end_time - self.start_time


def format_bytes(bytes_count: int) -> str:
    """Formate un nombre d'octets en format lisible.

    Args:
        bytes_count: Nombre d'octets

    Returns:
        str: Taille formatée (ex: "1.5 MB")

    Example:
        >>> print(format_bytes(1500000))
        '1.43 MB'
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"


def format_duration(seconds: float) -> str:
    """Formate une durée en format lisible.

    Args:
        seconds: Durée en secondes

    Returns:
        str: Durée formatée (ex: "1h 23m 45s")

    Example:
        >>> print(format_duration(3725))
        '1h 2m 5s'
    """
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {int(seconds)}s"

    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"


# -----------------------------
# Report generation utilities
# -----------------------------


def generate_markdown_report(title: str, sections: Dict[str, Any]) -> str:
    """Generate a markdown report.

    Args:
        title: Report title
        sections: Dictionary of section_name -> content

    Returns:
        str: Markdown formatted report

    Example:
        >>> report = generate_markdown_report(
        ...     "Code Analysis",
        ...     {"Files": "100 files", "Issues": "3 issues found"}
        ... )
    """
    lines = [f"# {title}", ""]

    for section_name, content in sections.items():
        lines.append(f"## {section_name}")
        lines.append("")

        if isinstance(content, dict):
            for key, value in content.items():
                lines.append(f"- **{key}**: {value}")
        elif isinstance(content, list):
            for item in content:
                lines.append(f"- {item}")
        else:
            lines.append(str(content))
        lines.append("")

    return "\n".join(lines)


def save_report(
    report: str, filename: str, output_dir: Optional[Pathish] = None
) -> Optional[Path]:
    """Save a report to file.

    Args:
        report: Report content
        filename: Output filename
        output_dir: Output directory (default: current directory)

    Returns:
        Path to saved file, or None on error

    Example:
        >>> path = save_report(report, "analysis.md", "reports")
        >>> if path:
        ...     print(f"Report saved to {path}")
    """
    try:
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            file_path = output_path / filename
        else:
            file_path = Path(filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report)

        return file_path
    except Exception:
        return None


# -----------------------------
# Template generation
# -----------------------------


def Generate_Bc_Plugin_Template() -> str:
    """Generate a ready-to-use BC plugin template.

    The template is compatible with the BCASL loader:
    - Exposes a plugin class with proper metadata
    - Provides the global PLUGIN variable for execution
    - Provides the bcasl_register(manager) function for direct registration
    - Includes Dialog API for user interaction and logging
    - Includes proper version requirements

    Returns:
        str: Complete BC plugin template code

    Example:
        >>> template = Generate_Bc_Plugin_Template()
        >>> with open("Plugins/my_plugin/__init__.py", "w") as f:
        ...     f.write(template)
    """

    template = '''from __future__ import annotations

from pathlib import Path
from Plugins_SDK.BcPluginContext import BcPluginBase, PluginMeta, PreCompileContext
from Plugins_SDK.GeneralContext import Dialog

# Create Dialog instances for user interaction and logging
log = Dialog()
dialog = Dialog()

META = PluginMeta(
    id="my.plugin.id",
    name="My BC Plugin",
    version="1.0.0",
    description="Describe what this BC plugin does before compilation.",
    author="Your Name",
    tags=("check",),   # e.g., ("clean", "check", "optimize", "prepare", ...)
    required_bcasl_version="2.0.0",
    required_core_version="1.0.0",
    required_plugins_sdk_version="1.0.0",
    required_bc_plugin_context_version="1.0.0",
    required_general_context_version="1.0.0",
)


class MyPlugin(BcPluginBase):
    def __init__(self) -> None:
        super().__init__(META)

    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        """Execute pre-compilation actions.
        
        Args:
            ctx: PreCompileContext with workspace information and utilities
        """
        try:
            # Example: Ask user for confirmation
            response = dialog.msg_question(
                title="My Plugin",
                text="Proceed with pre-build checks?",
                default_yes=True,
            )
            
            if not response:
                log.log_info("Plugin cancelled by user")
                return
            
            # Example: Check for Python files
            files = list(ctx.iter_files(["*.py"], []))
            if not files:
                log.log_warn("No Python files found in workspace")
                raise RuntimeError("No Python files found in workspace")
            
            log.log_info(f"Found {len(files)} Python files")
            # Perform additional preparation...
            
        except Exception as e:
            log.log_error(f"Plugin error: {e}")
            raise


# Create plugin instance
PLUGIN = MyPlugin()


def bcasl_register(manager):
    """Register the plugin with the BCASL manager."""
    manager.add_plugin(PLUGIN)
'''

    return template


# -----------------------------
# Public API exports
# -----------------------------

__all__ = [
    # Version
    "__version__",
    # Base classes and types
    "BcPluginBase",
    "PluginMeta",
    "PreCompileContext",
    "register_plugin",
    "BCASL_PLUGIN_REGISTER_FUNC",
    # Type aliases
    "Pathish",
    # Data classes
    "DependencyInfo",
    "PythonFileInfo",
    "VenvInfo",
    "GitInfo",
    "ProjectStructureInfo",
    "CodeMetrics",
    "SecurityIssue",
    "PackageInfo",
    "TestResults",
    "DockerInfo",
    "CIInfo",
    # Workspace management
    "set_selected_workspace",
    "get_workspace_info",
    # Environment management
    "detect_environment_manager",
    "get_python_version_from_project",
    "install_dependencies",
    # Dependency analysis
    "parse_requirements_txt",
    "parse_pyproject_toml",
    "get_project_dependencies",
    "extract_imports_from_code",
    "get_outdated_packages",
    # Python file analysis
    "analyze_python_file",
    "validate_python_syntax",
    "get_python_files_with_issues",
    # Virtual environment
    "detect_venv",
    "get_venv_info",
    # Git utilities
    "get_git_info",
    # Project structure
    "analyze_project_structure",
    # Code metrics
    "calculate_code_metrics",
    "calculate_project_metrics",
    # Security analysis
    "scan_for_secrets",
    "check_dangerous_imports",
    # Version management
    "get_current_version",
    "bump_version",
    # Testing
    "run_tests",
    # Docker
    "analyze_docker_config",
    # CI/CD
    "analyze_ci_config",
    # Network utilities
    "download_file",
    "check_url_accessible",
    "get_external_ip",
    # File operations
    "safe_backup_file",
    "safe_restore_file",
    "calculate_file_hash",
    "get_directory_size",
    "clean_pycache",
    # Search and replace
    "search_in_files",
    "replace_in_files",
    # File pattern utilities
    "match_patterns",
    "find_files",
    "count_files_by_extension",
    # Path utilities
    "ensure_directory",
    "is_python_project",
    "get_relative_path",
    # Process execution
    "run_command",
    "check_command_exists",
    # Validation
    "validate_python_project",
    # Cache management
    "cache_set",
    "cache_get",
    "cache_clear",
    # Documentation generation
    "generate_requirements_from_imports",
    "generate_readme",
    # Report generation
    "generate_markdown_report",
    "save_report",
    # Time utilities
    "Timer",
    "format_bytes",
    "format_duration",
    # Template generation
    "Generate_Bc_Plugin_Template",
]
