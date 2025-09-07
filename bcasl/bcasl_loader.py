# SPDX-License-Identifier: GPL-3.0-only
"""
api_loader - Intégration BCASL dans PyCompiler Pro++

- Charge automatiquement tous les plugins BCASL situés dans le dossier API/ (packages Python)
- Exécute leurs hooks on_pre_compile AVANT le démarrage de la compilation
- Journalise le résultat dans l'UI (self.log)

Notes:
- Les plugins sont chargés depuis le répertoire du programme (repo_root/API)
- Le contexte de pré-compilation pointe vers le workspace utilisateur (self.workspace_dir)
- Un fichier de configuration optionnel bcasl.* ou .bcasl.* (json/yaml/yml/toml/ini/cfg) à la racine du workspace
  est lu; à défaut un bcasl.json minimal est créé. Il peut définir des options passées aux plugins (ex: required_files, file_patterns, ...)
"""
from __future__ import annotations

import configparser
import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

# Optional parsers
try:
    import tomllib as _toml  # Python 3.11+
except Exception:
    try:
        import tomllib as _toml  # Backport
    except Exception:
        _toml = None

try:
    import yaml as _yaml
except Exception:
    _yaml = None

from bcasl import BCASL, PreCompileContext


def _has_bcasl_marker(pkg_dir: Path) -> bool:
    """Return True if plugin package declares BCASL_PLUGIN = True in its __init__.py."""
    try:
        init_py = pkg_dir / "__init__.py"
        if not init_py.exists():
            return False
        txt = init_py.read_text(encoding="utf-8", errors="ignore")
        import re as _re

        return _re.search(r"(?m)^\s*BCASL_PLUGIN\s*=\s*True\s*(#.*)?$", txt) is not None
    except Exception:
        return False


# Optional Qt threading primitives for non-blocking execution
try:
    from PySide6.QtCore import QEventLoop, QObject, Qt, QThread, Signal, Slot
except Exception:  # pragma: no cover
    QObject = None  # type: ignore
    Signal = None  # type: ignore
    Slot = None  # type: ignore
    QThread = None  # type: ignore
    QEventLoop = None  # type: ignore


def _write_json_atomic(path: Path, data: dict[str, Any]) -> bool:
    """Write JSON atomically with optional backup. Returns True on success."""
    import os as _os
    import tempfile

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=".bcasl_", dir=str(path.parent))
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            # Backup existing file if any
            try:
                if path.exists():
                    bkp = path.with_suffix(path.suffix + ".bak")
                    try:
                        if bkp.exists():
                            bkp.unlink()
                    except Exception:
                        pass
                    path.replace(bkp)
            except Exception:
                pass
            _os.replace(tmp_path, str(path))
            try:
                _os.chmod(str(path), 0o644)
            except Exception:
                pass
            return True
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    except Exception:
        return False


def _load_workspace_config(workspace_root: Path) -> dict[str, Any]:
    def _parse_text_config(p: Path) -> dict[str, Any]:
        # Lit le fichier texte et tente de le parser en dict selon l'extension puis par heuristiques
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            return {}
        suffix = p.suffix.lower().lstrip(".")
        try:
            if suffix == "json":
                return json.loads(text)
            if suffix in ("yaml", "yml"):
                if _yaml:
                    data = _yaml.safe_load(text)
                    return data if isinstance(data, dict) else {}
            if suffix == "toml":
                if _toml:
                    return _toml.loads(text)
            if suffix in ("ini", "cfg"):
                cp = configparser.ConfigParser()
                try:
                    cp.read_string(text)
                except Exception:
                    return {}
                cfg: dict[str, Any] = {}
                for sect in cp.sections():
                    cfg[sect] = {k: v for k, v in cp.items(sect)}
                if cp.defaults():
                    cfg.setdefault("DEFAULT", {}).update(dict(cp.defaults()))
                return cfg
        except Exception:
            pass
        # Fallback heuristique multi-format
        for try_fmt in ("json", "yaml", "toml", "ini"):
            try:
                if try_fmt == "json":
                    return json.loads(text)
                if try_fmt == "yaml" and _yaml:
                    data = _yaml.safe_load(text)
                    if isinstance(data, dict):
                        return data
                if try_fmt == "toml" and _toml:
                    return _toml.loads(text)
                if try_fmt == "ini":
                    cp = configparser.ConfigParser()
                    cp.read_string(text)
                    cfg: dict[str, Any] = {}
                    for sect in cp.sections():
                        cfg[sect] = {k: v for k, v in cp.items(sect)}
                    if cp.defaults():
                        cfg.setdefault("DEFAULT", {}).update(dict(cp.defaults()))
                    return cfg
            except Exception:
                continue
        return {}

    # Priorité sur des noms usuels
    candidates = [
        "bcasl.json",
        ".bcasl.json",
        "bcasl.yaml",
        ".bcasl.yaml",
        "bcasl.yml",
        ".bcasl.yml",
        "bcasl.toml",
        ".bcasl.toml",
        "bcasl.ini",
        ".bcasl.ini",
        "bcasl.cfg",
        ".bcasl.cfg",
    ]
    for name in candidates:
        p = workspace_root / name
        if p.exists() and p.is_file():
            cfg = _parse_text_config(p)
            if isinstance(cfg, dict) and cfg:
                return cfg
            # invalid/empty config; try next candidate
            continue

    # Recherche générique: toute extension
    for p in list(workspace_root.glob("bcasl.*")) + list(workspace_root.glob(".bcasl.*")):
        if p.is_file():
            cfg = _parse_text_config(p)
            if isinstance(cfg, dict) and cfg:
                return cfg
            # skip invalid/empty parsed content and continue scanning
            continue

    # Aucun fichier de config; créer un bcasl.json enrichi par défaut
    try:
        if workspace_root.exists() and workspace_root.is_dir():
            # Détecter les plugins disponibles dans <repo_root>/API
            try:
                repo_root = Path(__file__).resolve().parents[1]
                api_dir = repo_root / "API"
            except Exception:
                api_dir = None
            detected_plugins: dict[str, Any] = {}
            if api_dir and api_dir.exists() and api_dir.is_dir():
                try:
                    for entry in sorted(api_dir.iterdir()):
                        # Package-only: require __init__.py and explicit BCASL_PLUGIN = True opt-in
                        if entry.is_dir() and (entry / "__init__.py").exists() and _has_bcasl_marker(entry):
                            detected_plugins[entry.name] = {"enabled": True}
                except Exception:
                    pass
            # Suggérer des fichiers requis usuels
            suggested_required: list[str] = []
            try:
                for fname in ("main.py", "app.py", "requirements.txt"):
                    p = workspace_root / fname
                    if p.exists() and p.is_file():
                        suggested_required.append(fname)
            except Exception:
                pass
            # Construire la configuration par défaut enrichie
            # Étendre la liste de fichiers requis usuels avec fichiers de build/config/doc si présents
            try:
                for fname in ("pyproject.toml", "setup.cfg", "setup.py", "manage.py", "README.md", "LICENSE"):
                    p = workspace_root / fname
                    if p.exists() and p.is_file() and fname not in suggested_required:
                        suggested_required.append(fname)
            except Exception:
                pass
            # Déterminer des motifs de fichiers pertinents à partir de la structure du workspace
            suggested_patterns_set: set[str] = set()
            try:
                # 1) Heuristique pyproject.toml (poetry / setuptools)
                pyproj = workspace_root / "pyproject.toml"
                if pyproj.exists() and pyproj.is_file() and _toml:
                    try:
                        pdata = _toml.loads(pyproj.read_text(encoding="utf-8"))
                        tool = pdata.get("tool", {}) if isinstance(pdata, dict) else {}
                        # poetry
                        poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
                        pkgs = poetry.get("packages", []) if isinstance(poetry, dict) else []
                        if isinstance(pkgs, list):
                            for entry in pkgs:
                                inc = (entry or {}).get("include") if isinstance(entry, dict) else None
                                if inc:
                                    suggested_patterns_set.add(f"{inc}/**/*.py")
                        # python package name (src layout common)
                        pname = poetry.get("name") if isinstance(poetry, dict) else None
                        if pname and (workspace_root / "src").is_dir():
                            m = pname.replace("-", "_")
                            if (workspace_root / "src" / m).exists():
                                suggested_patterns_set.add("src/**/*.py")
                        # setuptools
                        st = tool.get("setuptools", {}) if isinstance(tool, dict) else {}
                        # package-dir mapping
                        pkgdir = (st.get("package-dir") or {}) if isinstance(st, dict) else {}
                        if isinstance(pkgdir, dict):
                            for _, rel in pkgdir.items():
                                if rel and (workspace_root / rel).is_dir():
                                    suggested_patterns_set.add(f"{rel}/**/*.py")
                        # packages.find.where list
                        try:
                            find = st.get("packages", {}).get("find", {}) if isinstance(st, dict) else {}
                            where_list = find.get("where", []) if isinstance(find, dict) else []
                            if isinstance(where_list, list):
                                for w in where_list:
                                    if w and (workspace_root / w).is_dir():
                                        suggested_patterns_set.add(f"{w}/**/*.py")
                        except Exception:
                            pass
                        # explicit packages list
                        try:
                            pkgs2 = st.get("packages", []) if isinstance(st, dict) else []
                            if isinstance(pkgs2, list):
                                for name in pkgs2:
                                    if isinstance(name, str) and name:
                                        suggested_patterns_set.add(f"{name.replace('.', '/')}/**/*.py")
                        except Exception:
                            pass
                    except Exception:
                        pass
                # 2) setup.cfg
                setup_cfg = workspace_root / "setup.cfg"
                if setup_cfg.exists() and setup_cfg.is_file():
                    try:
                        cp = configparser.ConfigParser()
                        cp.read(setup_cfg, encoding="utf-8")
                        # options.package_dir
                        if cp.has_option("options", "package_dir"):
                            try:
                                m = dict(cp.items("options.package_dir"))
                                for _, rel in m.items():
                                    if rel and (workspace_root / rel).is_dir():
                                        suggested_patterns_set.add(f"{rel}/**/*.py")
                            except Exception:
                                pass
                        # options.packages.find where
                        if cp.has_section("options.packages.find") and cp.has_option("options.packages.find", "where"):
                            where = cp.get("options.packages.find", "where")
                            for part in where.split("\n") if "\n" in where else where.split(","):
                                w = part.strip()
                                if w and (workspace_root / w).is_dir():
                                    suggested_patterns_set.add(f"{w}/**/*.py")
                    except Exception:
                        pass
                # 3) setup.py heuristique (src layout)
                setup_py = workspace_root / "setup.py"
                if setup_py.exists() and setup_py.is_file():
                    try:
                        txt = setup_py.read_text(encoding="utf-8", errors="ignore")
                        if "package_dir" in txt and "src" in txt and (workspace_root / "src").is_dir():
                            suggested_patterns_set.add("src/**/*.py")
                    except Exception:
                        pass
                # 4) Packages top-level (__init__.py)
                try:
                    for d in workspace_root.iterdir():
                        if d.is_dir() and (d / "__init__.py").exists():
                            suggested_patterns_set.add(f"{d.name}/**/*.py")
                except Exception:
                    pass
                # 5) Dossiers courants d'application
                for common in ("src", "app", "apps", "backend", "server", "api", "lib"):
                    p = workspace_root / common
                    if p.is_dir():
                        try:
                            if any(True for _ in p.rglob("*.py")):
                                suggested_patterns_set.add(f"{common}/**/*.py")
                        except Exception:
                            pass
                # 6) Scripts racine avec point d'entrée
                entry_points: list[Path] = []
                try:
                    for py in workspace_root.glob("*.py"):
                        try:
                            content = py.read_text(encoding="utf-8")
                            if "if __name__ == '__main__'" in content or 'if __name__ == "__main__"' in content:
                                suggested_patterns_set.add(py.name)
                                entry_points.append(py)
                        except Exception:
                            pass
                except Exception:
                    pass
                # 7) Détection par dépendances/frameworks
                try:
                    req = workspace_root / "requirements.txt"
                    req_txt = req.read_text(encoding="utf-8") if req.exists() else ""
                    low = req_txt.lower()
                    # Django: inclure dossier contenant settings.py et manage.py sibling
                    if "django" in low or (workspace_root / "manage.py").exists():
                        try:
                            for settings in workspace_root.rglob("settings.py"):
                                d = settings.parent
                                if d.is_dir() and (d / "__init__.py").exists() or any(True for _ in d.rglob("*.py")):
                                    rel = d.relative_to(workspace_root).as_posix()
                                    suggested_patterns_set.add(f"{rel}/**/*.py")
                        except Exception:
                            pass
                        if (workspace_root / "manage.py").exists():
                            suggested_patterns_set.add("manage.py")
                    # Flask / FastAPI: inclure répertoires typiques
                    if "flask" in low or "fastapi" in low:
                        for cand in ("app", "api", "project"):
                            p = workspace_root / cand
                            if p.is_dir():
                                try:
                                    if any(True for _ in p.rglob("*.py")):
                                        suggested_patterns_set.add(f"{cand}/**/*.py")
                                except Exception:
                                    pass
                except Exception:
                    pass
                # 8) Inférence par imports depuis les points d'entrée
                try:
                    import re

                    mod_re = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z_][\w\.]*)", re.MULTILINE)
                    seeds: set[str] = set()
                    # Ajouter __main__ dans src/** si présent
                    try:
                        for m in workspace_root.rglob("__main__.py"):
                            entry_points.append(m)
                    except Exception:
                        pass
                    for ep in entry_points[:20]:  # limite de sécurité
                        try:
                            txt = ep.read_text(encoding="utf-8", errors="ignore")
                            for m in mod_re.findall(txt):
                                top = (m.split(".")[0] or "").strip()
                                if not top:
                                    continue
                                seeds.add(top)
                        except Exception:
                            pass
                    for s in list(seeds)[:50]:
                        # Correspondances possibles: s.py à la racine
                        try:
                            if (workspace_root / f"{s}.py").exists():
                                suggested_patterns_set.add(f"{s}.py")
                        except Exception:
                            pass
                        # Dossier top-level
                        try:
                            d = workspace_root / s
                            if d.is_dir():
                                suggested_patterns_set.add(f"{s}/**/*.py")
                        except Exception:
                            pass
                        # src layout
                        try:
                            d2 = workspace_root / "src" / s
                            if d2.is_dir():
                                suggested_patterns_set.add("src/**/*.py")
                        except Exception:
                            pass
                except Exception:
                    pass
                # 8.1) Monorepo: projets Python imbriqués (pyproject/setup)
                try:
                    skip = {
                        "venv",
                        ".venv",
                        "build",
                        "dist",
                        ".git",
                        "__pycache__",
                        "main.build",
                        ".mypy_cache",
                        ".idea",
                        "node_modules",
                    }
                    for d in workspace_root.iterdir():
                        if not d.is_dir() or d.name in skip:
                            continue
                        sub_pyproj = d / "pyproject.toml"
                        sub_setup_cfg = d / "setup.cfg"
                        sub_setup_py = d / "setup.py"
                        if sub_pyproj.exists() or sub_setup_cfg.exists() or sub_setup_py.exists():
                            sub_src = d / "src"
                            try:
                                if sub_src.is_dir() and any(True for _ in sub_src.rglob("*.py")):
                                    suggested_patterns_set.add(f"{d.name}/src/**/*.py")
                                elif any(True for _ in d.rglob("*.py")):
                                    suggested_patterns_set.add(f"{d.name}/**/*.py")
                            except Exception:
                                pass
                except Exception:
                    pass
                # 8.2) Mapping requirements -> modules top-level
                try:
                    req = workspace_root / "requirements.txt"
                    req_txt = req.read_text(encoding="utf-8") if req.exists() else ""
                    for line in req_txt.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        # couper aux séparateurs de version/extras/markers
                        cut = line.split(";")[0]
                        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
                            cut = cut.split(sep)[0]
                        name = cut.split("[")[0].strip()
                        if not name:
                            continue
                        mod = name.lower().replace("-", "_")
                        try:
                            if (workspace_root / mod).is_dir():
                                suggested_patterns_set.add(f"{mod}/**/*.py")
                            elif (workspace_root / "src" / mod).is_dir():
                                suggested_patterns_set.add("src/**/*.py")
                        except Exception:
                            pass
                except Exception:
                    pass
                # 9) Fallback global si rien trouvé
                if not suggested_patterns_set:
                    suggested_patterns_set.add("**/*.py")
            except Exception:
                pass
            # Post-traitement: compression des motifs (supprime les redondances)
            try:
                bases = []
                for pat in sorted(suggested_patterns_set):
                    base = pat
                    if "/**/" in pat:
                        base = pat.split("/**/")[0]
                    elif pat.endswith("**/*.py"):
                        base = pat[: -len("**/*.py")].rstrip("/")
                    bases.append((pat, base))
                compressed: set[str] = set()
                for pat, base in bases:
                    redundant = False
                    for other, obase in bases:
                        if other == pat:
                            continue
                        if obase and base and base.startswith(obase) and other.endswith("**/*.py"):
                            redundant = True
                            break
                    if not redundant:
                        compressed.add(pat)
                suggested_patterns = sorted(compressed)
            except Exception:
                suggested_patterns = sorted(suggested_patterns_set)
            from datetime import datetime, timezone

            # Intégrer .gitignore dans exclude_patterns et préparer ordre/priorités
            # Élargir exclude_patterns de base
            exclude_patterns = [
                "**/__pycache__/**",
                "**/*.pyc",
                "build/**",
                "dist/**",
                "venv/**",
                ".venv/**",
                "main.build/**",
                ".git/**",
                ".mypy_cache/**",
                ".idea/**",
                ".tox/**",
                ".pytest_cache/**",
                ".ruff_cache/**",
                ".eggs/**",
                "__pypackages__/**",
                ".vscode/**",
                "docs/_build/**",
                "tests/**",
            ]
            try:
                gid = workspace_root / ".gitignore"
                if gid.exists() and gid.is_file():
                    for raw in gid.read_text(encoding="utf-8", errors="ignore").splitlines():
                        s = raw.strip()
                        if not s or s.startswith("#") or s.startswith("!"):
                            continue
                        s = s.replace("\\", "/")
                        s = s.lstrip("/")
                        if s.endswith("/"):
                            s = s.rstrip("/") + "/**"
                        if s not in exclude_patterns:
                            exclude_patterns.append(s)
            except Exception:
                pass
            # Définir un ordre par défaut des plugins et priorités (basé sur tags)
            detected_ids = list(detected_plugins.keys())
            # Mapping de scores: plus petit = plus tôt
            try:
                meta_map = _discover_bcasl_meta(api_dir)
            except Exception:
                meta_map = {}
            tag_score = {
                # Nettoyage
                "clean": 0,
                "cleanup": 0,
                "sanitize": 0,
                "prune": 0,
                "tidy": 0,
                # Vérifications / sécurité
                "validation": 10,
                "presence": 10,
                "sanity": 10,
                "policy": 10,
                "requirements": 10,
                "check": 10,
                "audit": 10,
                "scan": 10,
                "security": 10,
                "sast": 10,
                "compliance": 10,
                "license-check": 10,
                # Tests rapides (avant lourdes transformations)
                "test": 15,
                "tests": 15,
                "unit-test": 15,
                "integration-test": 15,
                "pytest": 15,
                # Préparation / génération / provisioning
                "prepare": 20,
                "codegen": 20,
                "generate": 20,
                "fetch": 20,
                "resources": 20,
                "download": 20,
                "install": 20,
                "bootstrap": 20,
                "configure": 20,
                # Conformité / entêtes / normalisation
                "license": 30,
                "header": 30,
                "normalize": 30,
                "inject": 30,
                "spdx": 30,
                "banner": 30,
                "copyright": 30,
                # Lint / format / typage
                "lint": 40,
                "format": 40,
                "black": 40,
                "isort": 40,
                "sort-imports": 40,
                "typecheck": 40,
                "mypy": 40,
                "flake8": 40,
                "ruff": 40,
                "pep8": 40,
                # Minification (avant obfuscation)
                "minify": 45,
                "uglify": 45,
                "shrink": 45,
                "compress-code": 45,
                # Obfuscation / transpilation / protection
                "obfuscation": 50,
                "obfuscate": 50,
                "transpile": 50,
                "protect": 50,
                "encrypt": 50,
                # Packaging / bundling / archives
                "package": 55,
                "packaging": 55,
                "bundle": 55,
                "archive": 55,
                "compress": 55,
                "zip": 55,
                # Manifest / version / metadata
                "manifest": 60,
                "version": 60,
                "metadata": 60,
                "bump": 60,
                "changelog": 60,
                # Documentation
                "docs": 70,
                "documentation": 70,
                "doc": 70,
                "generate-docs": 70,
                # Publication / déploiement (rare en BCASL mais supporté)
                "publish": 80,
                "deploy": 80,
                "release": 80,
            }

            def _score_for(pid: str) -> int:
                try:
                    meta = meta_map.get(pid) or {}
                    tags = meta.get("tags") or []
                    # 1) Priorité par tags explicites
                    if isinstance(tags, list) and tags:
                        return int(min((tag_score.get(str(t).lower(), 100) for t in tags), default=100))
                    # 2) Heuristique sémantique basée sur nom/description (pas d'id codé en dur)
                    text = (str(meta.get("name") or "") + " " + str(meta.get("description") or "")).lower()
                    kw_groups = [
                        # Nettoyage
                        ({"clean", "cleanup", "sanitize", "prune", "tidy"}, 0),
                        # Vérifications / sécurité
                        (
                            {
                                "validation",
                                "validate",
                                "presence",
                                "sanity",
                                "policy",
                                "requirement",
                                "requirements",
                                "check",
                                "audit",
                                "scan",
                                "security",
                                "sast",
                                "compliance",
                                "license-check",
                            },
                            10,
                        ),
                        # Tests
                        ({"test", "tests", "unit", "unit-test", "integration", "integration-test", "pytest"}, 15),
                        # Préparation / génération
                        (
                            {
                                "prepare",
                                "codegen",
                                "generate",
                                "fetch",
                                "resource",
                                "resources",
                                "download",
                                "install",
                                "bootstrap",
                                "configure",
                            },
                            20,
                        ),
                        # Conformité / entêtes
                        ({"license", "header", "normalize", "inject", "spdx", "banner", "copyright"}, 30),
                        # Lint / format / typage
                        (
                            {
                                "lint",
                                "format",
                                "black",
                                "isort",
                                "sort-imports",
                                "typecheck",
                                "mypy",
                                "flake8",
                                "ruff",
                                "pep8",
                            },
                            40,
                        ),
                        # Minification
                        ({"minify", "uglify", "shrink", "compress-code"}, 45),
                        # Obfuscation / transpilation
                        ({"obfuscation", "obfuscate", "transpile", "protect", "encrypt"}, 50),
                        # Packaging / bundling
                        ({"package", "packaging", "bundle", "archive", "compress", "zip"}, 55),
                        # Manifest / version
                        ({"manifest", "version", "metadata", "bump", "changelog"}, 60),
                        # Documentation
                        ({"docs", "documentation", "doc", "generate-docs"}, 70),
                        # Publication / déploiement
                        ({"publish", "deploy", "release"}, 80),
                    ]
                    for kws, score in kw_groups:
                        if any(k in text for k in kws):
                            return score
                except Exception:
                    pass
                # 3) Défaut neutre
                return 100

            # Tri stable par (score, id)
            plugin_order = sorted(detected_ids, key=lambda x: (_score_for(x), x))
            plugins_out: dict[str, Any] = {}
            for idx, pid in enumerate(plugin_order):
                try:
                    cur = detected_plugins.get(pid, {})
                    enabled = (
                        bool(cur.get("enabled", True))
                        if isinstance(cur, dict)
                        else bool(cur)
                        if isinstance(cur, bool)
                        else True
                    )
                except Exception:
                    enabled = True
                plugins_out[pid] = {"enabled": enabled, "priority": idx}
            # Options enrichies
            try:
                import platform as _plat

                _is_windows = _plat.system().lower().startswith("win")
            except Exception:
                _is_windows = False
            headless = False
            try:
                if not _is_windows and (not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")):
                    headless = True
            except Exception:
                pass

            default_cfg: dict[str, Any] = {
                "_meta": {
                    "generated": True,
                    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "schema": "1.0",
                },
                "required_files": suggested_required,
                "file_patterns": suggested_patterns,
                "exclude_patterns": exclude_patterns,
                "options": {
                    "plugin_timeout_s": 0.0,
                    "phase_soft_timeout_s": 30.0,
                    "noninteractive_plugins": bool(headless),
                    "allow_sandbox_dialogs": True,
                    "plugin_parallelism": 0,
                    "sandbox": True,
                    "iter_files_cache": True,
                    "plugin_limits": {"mem_mb": 0, "cpu_time_s": 0, "nofile": 0, "fsize_mb": 0},
                },
                "plugins": plugins_out,
                "plugin_order": plugin_order,
            }
            target = workspace_root / "bcasl.json"
            ok = _write_json_atomic(target, default_cfg)
            if not ok:
                # Fallback best-effort write
                try:
                    target.write_text(json.dumps(default_cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                except Exception:
                    # Last resort: leave only in-memory config
                    pass
            return default_cfg
    except Exception:
        pass
    return {}


def _prepare_enabled_plugins_dir(api_dir: Path, cfg: dict[str, Any], workspace_root: Path) -> Path:
    """Construit un dossier éphémère qui ne contient que les plugins activés.
    - Si cfg["plugins"][plugin_id]["enabled"] est False, le plugin est exclu
    - Utilise des liens symboliques si possible, sinon copie (fallback)
    - Retourne le chemin du dossier à utiliser pour load_plugins_from_directory
    """
    try:
        # Lister les plugins disponibles dans API/
        available = []
        for entry in sorted(api_dir.iterdir()):
            # Package-only: require __init__.py inside plugin directory AND explicit BCASL_PLUGIN = True
            if entry.is_dir() and (entry / "__init__.py").exists() and _has_bcasl_marker(entry):
                available.append(entry.name)
        # Déterminer la liste des activés
        enabled_map = {}
        if isinstance(cfg, dict):
            pmap = cfg.get("plugins", {})
            if isinstance(pmap, dict):
                for pid in available:
                    val = pmap.get(pid, {"enabled": True})
                    if isinstance(val, dict):
                        enabled_map[pid] = bool(val.get("enabled", True))
                    elif isinstance(val, bool):
                        enabled_map[pid] = val
        # Si aucune config fournie, tout est activé
        if not enabled_map:
            for pid in available:
                enabled_map[pid] = True
        # Construire le dossier filtré
        target = workspace_root / ".pycompiler" / "api_enabled"
        try:
            shutil.rmtree(target, ignore_errors=True)
        except Exception:
            pass
        os.makedirs(target, exist_ok=True)
        # Créer symlinks ou copies pour chaque plugin activé
        for pid in available:
            if not enabled_map.get(pid, True):
                continue
            src = api_dir / pid
            dst = target / pid
            try:
                os.symlink(src, dst, target_is_directory=True)
            except Exception:
                # Fallback copie
                try:
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                except Exception:
                    pass
        return target
    except Exception:
        # En cas d'erreur, retourner le dossier API original (aucun filtrage)
        return api_dir


# Worker to run BCASL in a background thread and forward logs safely to the UI
if QObject is not None and Signal is not None:

    class _BCASLWorker(QObject):
        finished = Signal(object)  # report or None
        log = Signal(str)

        def __init__(self, workspace_root: Path, api_dir: Path, cfg: dict[str, Any], plugin_timeout: float) -> None:
            super().__init__()
            self.workspace_root = workspace_root
            self.api_dir = api_dir
            self.cfg = cfg
            self.plugin_timeout = plugin_timeout

        @Slot()
        def run(self) -> None:
            try:
                manager = BCASL(self.workspace_root, config=self.cfg, plugin_timeout_s=self.plugin_timeout)
                enabled_dir = _prepare_enabled_plugins_dir(self.api_dir, self.cfg, self.workspace_root)
                loaded, errors = manager.load_plugins_from_directory(enabled_dir)
                try:
                    self.log.emit(f"🧩 BCASL: {loaded} package(s) de plugins chargé(s) depuis API/\n")
                    for mod, msg in errors or []:
                        self.log.emit(f"⚠️ Plugin '{mod}': {msg}\n")
                except Exception:
                    pass
                # Appliquer activation/désactivation et priorités depuis la config
                try:
                    pmap = self.cfg.get("plugins", {}) if isinstance(self.cfg, dict) else {}
                    order_list = []
                    try:
                        order_list = list(self.cfg.get("plugin_order", [])) if isinstance(self.cfg, dict) else []
                    except Exception:
                        order_list = []
                    # Priorité par 'plugin_order' en premier
                    if order_list:
                        for idx, pid in enumerate(order_list):
                            try:
                                self.log.emit(f"⏫ Priorité {idx} pour {pid}\n")
                            except Exception:
                                pass
                            try:
                                manager.set_priority(pid, int(idx))
                            except Exception:
                                pass
                    # Priorité par plugins[pid].priority ensuite
                    if isinstance(pmap, dict):
                        for pid, val in pmap.items():
                            try:
                                if isinstance(val, dict) and "priority" in val:
                                    manager.set_priority(pid, int(val.get("priority", 0)))
                            except Exception:
                                pass
                except Exception:
                    pass
                report = manager.run_pre_compile(PreCompileContext(self.workspace_root))
                self.finished.emit(report)
            except Exception as e:
                try:
                    self.log.emit(f"⚠️ Erreur BCASL: {e}\n")
                except Exception:
                    pass
                self.finished.emit(None)


# Bridge to marshal BCASL signals into the GUI thread safely
if QObject is not None and Signal is not None:

    class _BCASLUiBridge(QObject):
        def __init__(self, gui, on_done, thread) -> None:
            super().__init__()
            self._gui = gui
            self._on_done = on_done
            self._thread = thread

        @Slot(str)
        def on_log(self, s: str) -> None:
            try:
                if hasattr(self._gui, "log") and self._gui.log:
                    self._gui.log.append(s)
            except Exception:
                pass

        @Slot(object)
        def on_finished(self, rep) -> None:
            try:
                # Post summary and callback on GUI thread
                from PySide6.QtCore import QTimer as _QT

                def _invoke():
                    try:
                        if rep and hasattr(self._gui, "log") and self._gui.log is not None:
                            self._gui.log.append("BCASL - Rapport:\n")
                            for item in rep:
                                try:
                                    state = (
                                        "OK"
                                        if getattr(item, "success", False)
                                        else f"FAIL: {getattr(item, 'error', '')}"
                                    )
                                    dur = getattr(item, "duration_ms", 0.0)
                                    pid = getattr(item, "plugin_id", "?")
                                    self._gui.log.append(f" - {pid}: {state} ({dur:.1f} ms)\n")
                                except Exception:
                                    pass
                            try:
                                self._gui.log.append(rep.summary() + "\n")
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        if callable(self._on_done):
                            self._on_done(rep)
                    except Exception:
                        pass

                try:
                    _QT.singleShot(0, _invoke)
                except Exception:
                    try:
                        _invoke()
                    except Exception:
                        pass
            finally:
                try:
                    self._thread.quit()
                except Exception:
                    pass


from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def ensure_bcasl_thread_stopped(self, timeout_ms: int = 5000) -> None:
    """Arrête proprement le thread BCASL s'il est actif, pour éviter
    "QThread: Destroyed while thread is still running" au quit.
    """
    try:
        t = getattr(self, "_bcasl_thread", None)
        if t is not None:
            try:
                if t.isRunning():
                    try:
                        t.quit()
                    except Exception:
                        pass
                    if not t.wait(timeout_ms):
                        try:
                            t.terminate()
                        except Exception:
                            pass
                        try:
                            t.wait(1000)
                        except Exception:
                            pass
            except Exception:
                pass
        # Nettoyage des références
        try:
            self._bcasl_thread = None
            self._bcasl_worker = None
        except Exception:
            pass
    except Exception:
        pass


def resolve_bcasl_timeout(self) -> float:
    """Calcule le timeout effectif (secondes) des plugins BCASL.
    <= 0 implique un timeout illimité (0.0 renvoyé).
    """
    try:
        if not getattr(self, "workspace_dir", None):
            return 0.0
        workspace_root = Path(self.workspace_dir).resolve()
        cfg = _load_workspace_config(workspace_root)
        import os as _os

        try:
            env_timeout = float(_os.environ.get("PYCOMPILER_BCASL_PLUGIN_TIMEOUT", "0"))
        except Exception:
            env_timeout = 0.0
        try:
            opt = cfg.get("options", {}) if isinstance(cfg, dict) else {}
            cfg_timeout = float(opt.get("plugin_timeout_s", 0.0)) if isinstance(opt, dict) else 0.0
        except Exception:
            cfg_timeout = 0.0
        plugin_timeout_raw = cfg_timeout if cfg_timeout != 0.0 else env_timeout
        return float(plugin_timeout_raw) if plugin_timeout_raw and plugin_timeout_raw > 0 else 0.0
    except Exception:
        return 0.0


def _discover_bcasl_meta(api_dir: Path) -> dict[str, dict[str, Any]]:
    """Discover BCASL plugins in API/ directory (no execution).
    Returns a mapping plugin_dir_name -> metadata dict including:
      - id (BCASL_ID or folder name), description (BCASL_DESCRIPTION)
      - optional: name, version, author, created, license, compatibility (list), tags (list)
    Only packages with BCASL_PLUGIN = True are considered.
    """
    meta: dict[str, dict[str, Any]] = {}
    try:
        for entry in sorted(api_dir.iterdir()):
            try:
                if not entry.is_dir():
                    continue
                init_py = entry / "__init__.py"
                if not init_py.exists():
                    continue
                if not _has_bcasl_marker(entry):
                    continue
                m: dict[str, Any] = {"id": entry.name, "folder": entry.name}
                try:
                    txt = init_py.read_text(encoding="utf-8", errors="ignore")
                    import ast as _ast
                    import re as _re

                    def _get(pat: str) -> str:
                        mm = _re.search(pat, txt, _re.S)
                        return mm.group("val").strip() if mm else ""

                    def _get_list(sym: str) -> list[str]:
                        try:
                            mm = _re.search(rf"(?m)^\s*{sym}\s*=\s*(?P<val>\[.*?\])\s*$", txt, _re.S)
                            if not mm:
                                mm = _re.search(rf"{sym}\s*=\s*(?P<val>\[.*?\])", txt, _re.S)
                            if mm:
                                v = _ast.literal_eval(mm.group("val"))
                                if isinstance(v, list):
                                    return [str(x) for x in v]
                        except Exception:
                            pass
                        return []

                    pid = _get(r"BCASL_ID\s*=\s*([\'\"])(?P<val>.+?)\1") or entry.name
                    desc = _get(r"BCASL_DESCRIPTION\s*=\s*([\'\"])(?P<val>.+?)\1")
                    name = _get(r"BCASL_NAME\s*=\s*([\'\"])(?P<val>.+?)\1")
                    ver = _get(r"BCASL_VERSION\s*=\s*([\'\"])(?P<val>.+?)\1")
                    author = _get(r"BCASL_AUTHOR\s*=\s*([\'\"])(?P<val>.+?)\1")
                    created = _get(r"BCASL_CREATED\s*=\s*([\'\"])(?P<val>.+?)\1")
                    lic = _get(r"BCASL_LICENSE\s*=\s*([\'\"])(?P<val>.+?)\1")
                    compat = _get_list("BCASL_COMPATIBILITY")
                    tags = _get_list("BCASL_TAGS")
                    if pid:
                        m["id"] = pid
                    if desc:
                        m["description"] = desc
                    if name:
                        m["name"] = name
                    if ver:
                        m["version"] = ver
                    if author:
                        m["author"] = author
                    if created:
                        m["created"] = created
                    if lic:
                        m["license"] = lic
                    if compat:
                        m["compatibility"] = compat
                    if tags:
                        m["tags"] = tags
                except Exception:
                    pass
                meta[entry.name] = m
            except Exception:
                continue
    except Exception:
        pass
    return meta


def open_api_loader_dialog(self) -> None:
    """Ouvre une fenêtre permettant d'activer/désactiver les plugins API (BCASL).
    - Source des plugins: <repo_root>/API (packages Python)
    - Persistance: met à jour/écrit <workspace>/bcasl.json (clé 'plugins')
    - Format: { "plugins": { "<plugin_id>": {"enabled": true|false}, ... } }
    """
    try:
        if not getattr(self, "workspace_dir", None):
            QMessageBox.warning(
                self,
                self.tr("Attention", "Warning"),
                self.tr(
                    "Veuillez d'abord sélectionner un dossier workspace.", "Please select a workspace folder first."
                ),
            )
            return
        workspace_root = Path(self.workspace_dir).resolve()
        repo_root = Path(__file__).resolve().parents[1]
        api_dir = repo_root / "API"
        if not api_dir.exists():
            QMessageBox.information(
                self,
                self.tr("Information", "Information"),
                self.tr("Aucun répertoire API/ trouvé dans le projet.", "No API/ directory found in the project."),
            )
            return
        # Découverte stricte des plugins: paquets Python valides (BCASL_PLUGIN, ID, DESCRIPTION)
        meta_map = _discover_bcasl_meta(api_dir)
        plugin_ids = list(sorted(meta_map.keys()))
        if not plugin_ids:
            QMessageBox.information(
                self,
                self.tr("Information", "Information"),
                self.tr("Aucun plugin détecté dans API/.", "No plugins detected in API/."),
            )
            return
        # Charger config existante
        cfg = _load_workspace_config(workspace_root)
        plugins_cfg = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
        # Construire la boîte de dialogue
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Chargeur API", "API Loader"))
        layout = QVBoxLayout(dlg)
        info = QLabel(
            self.tr(
                "Activez/désactivez les plugins API et définissez leur ordre d'exécution (haut = d'abord).",
                "Enable/disable API plugins and set their execution order (top = first).",
            )
        )
        layout.addWidget(info)
        # Liste réordonnable par glisser-déposer, avec cases à cocher
        lst = QListWidget(dlg)
        lst.setSelectionMode(QAbstractItemView.SingleSelection)
        lst.setDragDropMode(QAbstractItemView.InternalMove)
        # Déterminer un ordre initial: plugin_order si présent, sinon plugin_ids triés
        order = []
        try:
            order = cfg.get("plugin_order", []) if isinstance(cfg, dict) else []
            order = [pid for pid in order if pid in plugin_ids]
        except Exception:
            order = []
        remaining = [pid for pid in plugin_ids if pid not in order]
        ordered_ids = order + remaining
        for pid in ordered_ids:
            meta = meta_map.get(pid, {})
            label = pid
            try:
                disp = meta.get("name") or pid
                ver = meta.get("version") or ""
                label = f"{disp} ({pid}) v{ver}" if ver else f"{disp} ({pid})"
            except Exception:
                label = pid
            item = QListWidgetItem(label)
            # Tooltip étendu (description + métadonnées)
            try:
                lines = []
                desc = meta.get("description") or ""
                if desc:
                    lines.append(desc)
                auth = meta.get("author") or ""
                if auth:
                    lines.append(f"Auteur: {auth}")
                created = meta.get("created") or ""
                if created:
                    lines.append(f"Créé: {created}")
                lic = meta.get("license") or ""
                if lic:
                    lines.append(f"Licence: {lic}")
                comp = meta.get("compatibility") or []
                if isinstance(comp, list) and comp:
                    lines.append("Compatibilité: " + ", ".join([str(x) for x in comp]))
                tags = meta.get("tags") or []
                if isinstance(tags, list) and tags:
                    lines.append("Tags: " + ", ".join([str(x) for x in tags]))
                if lines:
                    item.setToolTip("\n".join(lines))
            except Exception:
                pass
            # État activé/désactivé
            enabled = True
            try:
                pentry = plugins_cfg.get(pid, {})
                if isinstance(pentry, dict):
                    enabled = bool(pentry.get("enabled", True))
                elif isinstance(pentry, bool):
                    enabled = pentry
            except Exception:
                pass
            # Rétablir un hint de priorité si présent (non affiché)
            try:
                if isinstance(plugins_cfg.get(pid, {}), dict) and "priority" in plugins_cfg[pid]:
                    pr = int(plugins_cfg[pid]["priority"])  # noqa: F841
            except Exception:
                pass
            # Stocker l'id réel et rendre l'élément cochable
            try:
                item.setData(0x0100, pid)
            except Exception:
                pass
            item.setFlags(
                item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
            )
            item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
            lst.addItem(item)
        layout.addWidget(lst)
        # Raw config editor (JSON) toggle and panel
        btn_toggle_raw = QPushButton(self.tr("Modifier la configuration brute (bcasl.*)", "Edit raw config (bcasl.*)"))
        layout.addWidget(btn_toggle_raw)
        raw_box = QWidget(dlg)
        raw_lay = QVBoxLayout(raw_box)
        raw_hint = QLabel(
            self.tr(
                "Vous pouvez modifier la configuration directement. Elle sera enregistrée dans {} à la racine du workspace.",
                "You can edit the configuration directly. It will be saved to {} at the workspace root.",
            )
        )
        raw_lay.addWidget(raw_hint)
        raw_editor = QPlainTextEdit(raw_box)
        try:
            raw_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        except Exception:
            pass
        # Load existing config file text if present; otherwise serialize current config to JSON
        raw_text = ""
        existing_path = None
        try:
            for name in [
                "bcasl.json",
                ".bcasl.json",
                "bcasl.yaml",
                ".bcasl.yaml",
                "bcasl.yml",
                ".bcasl.yml",
                "bcasl.toml",
                ".bcasl.toml",
                "bcasl.ini",
                ".bcasl.ini",
                "bcasl.cfg",
                ".bcasl.cfg",
            ]:
                p = workspace_root / name
                if p.exists() and p.is_file():
                    existing_path = p
                    break
            if existing_path:
                raw_text = existing_path.read_text(encoding="utf-8", errors="ignore")
            else:
                raw_text = json.dumps(cfg if isinstance(cfg, dict) else {}, ensure_ascii=False, indent=2)
        except Exception:
            raw_text = json.dumps(cfg if isinstance(cfg, dict) else {}, ensure_ascii=False, indent=2)
        raw_editor.setPlainText(raw_text)
        # Determine target path (existing config file or default to bcasl.json) and update labels accordingly
        try:
            existing_name = existing_path.name if existing_path else None
        except Exception:
            existing_name = None
        target_path = existing_path if existing_path else (workspace_root / "bcasl.json")
        try:
            target_name = target_path.name
        except Exception:
            target_name = "bcasl.json"
        try:
            btn_toggle_raw.setText(
                self.tr("Modifier la configuration brute ({})", "Edit raw config ({})").format(target_name)
            )
        except Exception:
            pass
        try:
            raw_hint.setText(
                self.tr(
                    "Vous pouvez modifier la configuration directement. Elle sera enregistrée dans {} à la racine du workspace.",
                    "You can edit the configuration directly. It will be saved to {} at the workspace root.",
                ).format(target_name)
            )
        except Exception:
            pass
        raw_lay.addWidget(raw_editor)
        # Action buttons for raw editor
        raw_btns = QHBoxLayout()
        btn_reload_raw = QPushButton(self.tr("Recharger", "Reload"))
        btn_save_raw = QPushButton(self.tr("Enregistrer brut", "Save raw"))
        raw_btns.addWidget(btn_reload_raw)
        raw_btns.addStretch(1)
        raw_btns.addWidget(btn_save_raw)
        raw_lay.addLayout(raw_btns)
        raw_box.setVisible(False)

        def _toggle_raw():
            try:
                raw_box.setVisible(not raw_box.isVisible())
            except Exception:
                pass

        btn_toggle_raw.clicked.connect(_toggle_raw)

        def _reload_raw():
            try:
                if target_path and target_path.exists():
                    txt = target_path.read_text(encoding="utf-8", errors="ignore")
                else:
                    txt = json.dumps(cfg if isinstance(cfg, dict) else {}, ensure_ascii=False, indent=2)
                raw_editor.setPlainText(txt)
            except Exception as e:
                QMessageBox.warning(
                    dlg, self.tr("Attention", "Warning"), self.tr(f"Échec du rechargement: {e}", f"Reload failed: {e}")
                )

        btn_reload_raw.clicked.connect(_reload_raw)

        def _save_raw():
            nonlocal target_path, target_name
            txt = raw_editor.toPlainText()
            # Determine format from target_path and validate when possible
            fmt = "json"
            try:
                fmt = (target_path.suffix or "").lower().lstrip(".") or "json"
            except Exception:
                fmt = "json"
            try:
                if fmt == "json":
                    data = json.loads(txt)
                    out = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
                elif fmt in ("yaml", "yml"):
                    if _yaml is not None:
                        try:
                            data = _yaml.safe_load(txt)
                            # allow empty file => {}
                            if data is None:
                                data = {}
                            out = _yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
                        except Exception:
                            # Attempt JSON fallback -> save as bcasl.json
                            try:
                                data = json.loads(txt)
                                new_target = workspace_root / "bcasl.json"
                                new_target.write_text(
                                    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                                )
                                target_path = new_target
                                target_name = new_target.name
                                try:
                                    btn_toggle_raw.setText(
                                        self.tr("Modifier la configuration brute ({})", "Edit raw config ({})").format(
                                            target_name
                                        )
                                    )
                                    raw_hint.setText(
                                        self.tr(
                                            "Vous pouvez modifier la configuration directement. Elle sera enregistrée dans {} à la racine du workspace.",
                                            "You can edit the configuration directly. It will be saved to {} at the workspace root.",
                                        ).format(target_name)
                                    )
                                except Exception:
                                    pass
                                if hasattr(self, "log") and self.log is not None:
                                    self.log.append(
                                        self.tr(
                                            "⚠️ Contenu non valide YAML; conversion détectée JSON -> sauvegarde dans bcasl.json",
                                            "⚠️ Invalid YAML content; detected JSON -> saved to bcasl.json",
                                        )
                                    )
                                return
                            except Exception as conv_err:
                                raise conv_err
                    else:
                        # No YAML lib: attempt JSON fallback; otherwise write as-is
                        try:
                            data = json.loads(txt)
                            new_target = workspace_root / "bcasl.json"
                            new_target.write_text(
                                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                            )
                            target_path = new_target
                            target_name = new_target.name
                            try:
                                btn_toggle_raw.setText(
                                    self.tr("Modifier la configuration brute ({})", "Edit raw config ({})").format(
                                        target_name
                                    )
                                )
                                raw_hint.setText(
                                    self.tr(
                                        "Vous pouvez modifier la configuration directement. Elle sera enregistrée dans {} à la racine du workspace.",
                                        "You can edit the configuration directly. It will be saved to {} at the workspace root.",
                                    ).format(target_name)
                                )
                            except Exception:
                                pass
                            if hasattr(self, "log") and self.log is not None:
                                self.log.append(
                                    self.tr(
                                        "ℹ️ Librairie YAML absente; contenu JSON détecté -> sauvegarde dans bcasl.json",
                                        "ℹ️ YAML library missing; detected JSON content -> saved to bcasl.json",
                                    )
                                )
                            return
                        except Exception:
                            out = txt if txt.endswith("\n") else (txt + "\n")
                elif fmt == "toml":
                    # Validate TOML if tomllib/tomli available. If invalid, try JSON->JSON fallback.
                    if _toml is not None:
                        try:
                            _ = _toml.loads(txt)
                            out = txt if txt.endswith("\n") else (txt + "\n")
                        except Exception:
                            # Attempt to parse as JSON and save as JSON file (bcasl.json)
                            try:
                                data = json.loads(txt)
                                new_target = workspace_root / "bcasl.json"
                                new_target.write_text(
                                    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                                )
                                target_path = new_target
                                target_name = new_target.name
                                try:
                                    btn_toggle_raw.setText(
                                        self.tr("Modifier la configuration brute ({})", "Edit raw config ({})").format(
                                            target_name
                                        )
                                    )
                                    raw_hint.setText(
                                        self.tr(
                                            "Vous pouvez modifier la configuration directement. Elle sera enregistrée dans {} à la racine du workspace.",
                                            "You can edit the configuration directly. It will be saved to {} at the workspace root.",
                                        ).format(target_name)
                                    )
                                except Exception:
                                    pass
                                if hasattr(self, "log") and self.log is not None:
                                    self.log.append(
                                        self.tr(
                                            "⚠️ Contenu non valide TOML; conversion détectée JSON -> sauvegarde dans bcasl.json",
                                            "⚠️ Invalid TOML content; detected JSON -> saved to bcasl.json",
                                        )
                                    )
                                return
                            except Exception as conv_err:
                                raise conv_err
                    else:
                        # No TOML parser: write as-is
                        out = txt if txt.endswith("\n") else (txt + "\n")
                elif fmt in ("ini", "cfg"):
                    # Basic validation using configparser with JSON fallback
                    try:
                        cp = configparser.ConfigParser()
                        cp.read_string(txt)
                        out = txt if txt.endswith("\n") else (txt + "\n")
                    except Exception:
                        # Attempt JSON fallback -> save as bcasl.json
                        try:
                            data = json.loads(txt)
                            new_target = workspace_root / "bcasl.json"
                            new_target.write_text(
                                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                            )
                            target_path = new_target
                            target_name = new_target.name
                            try:
                                btn_toggle_raw.setText(
                                    self.tr("Modifier la configuration brute ({})", "Edit raw config ({})").format(
                                        target_name
                                    )
                                )
                                raw_hint.setText(
                                    self.tr(
                                        "Vous pouvez modifier la configuration directement. Elle sera enregistrée dans {} à la racine du workspace.",
                                        "You can edit the configuration directly. It will be saved to {} at the workspace root.",
                                    ).format(target_name)
                                )
                            except Exception:
                                pass
                            if hasattr(self, "log") and self.log is not None:
                                self.log.append(
                                    self.tr(
                                        "⚠️ Contenu non valide INI/CFG; conversion détectée JSON -> sauvegarde dans bcasl.json",
                                        "⚠️ Invalid INI/CFG content; detected JSON -> saved to bcasl.json",
                                    )
                                )
                            return
                        except Exception as conv_err:
                            raise conv_err
                else:
                    # Unknown format: write as-is
                    out = txt if txt.endswith("\n") else (txt + "\n")
            except Exception as e:
                # Validation failed for selected format
                QMessageBox.critical(
                    dlg,
                    self.tr("Erreur", "Error"),
                    self.tr(
                        f"Contenu invalide pour le format {fmt.upper()}: {e}",
                        f"Invalid content for format {fmt.upper()}: {e}",
                    ),
                )
                return
            try:
                target_path.write_text(out, encoding="utf-8")
                if hasattr(self, "log") and self.log is not None:
                    self.log.append(
                        self.tr(
                            f"✅ Configuration brute enregistrée dans {target_name} (la boîte reste ouverte)",
                            f"✅ Raw config saved to {target_name} (dialog remains open)",
                        )
                    )
            except Exception as e:
                QMessageBox.critical(
                    dlg,
                    self.tr("Erreur", "Error"),
                    self.tr(f"Échec d'écriture {target_name}: {e}", f"Failed to write {target_name}: {e}"),
                )

        btn_save_raw.clicked.connect(_save_raw)
        layout.addWidget(raw_box)
        # Boutons d'action + réordonnancement
        btns = QHBoxLayout()
        btn_up = QPushButton("⬆️")
        btn_down = QPushButton("⬇️")
        btn_save = QPushButton(self.tr("Enregistrer", "Save"))
        btn_cancel = QPushButton(self.tr("Annuler", "Cancel"))

        def _move_sel(delta: int):
            row = lst.currentRow()
            if row < 0:
                return
            new_row = max(0, min(lst.count() - 1, row + delta))
            if new_row == row:
                return
            it = lst.takeItem(row)
            lst.insertItem(new_row, it)
            lst.setCurrentRow(new_row)

        btn_up.clicked.connect(lambda: _move_sel(-1))
        btn_down.clicked.connect(lambda: _move_sel(1))
        btns.addWidget(btn_up)
        btns.addWidget(btn_down)
        btns.addStretch(1)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

        def do_save():
            # Extraire ordre et états depuis la QListWidget
            new_plugins: dict[str, Any] = {}
            order_ids: list[str] = []
            for i in range(lst.count()):
                it = lst.item(i)
                pid = it.data(0x0100) or it.text()
                en = it.checkState() == Qt.Checked
                new_plugins[str(pid)] = {"enabled": bool(en), "priority": i}
                order_ids.append(str(pid))
            # Construire une copie de la config pour éviter de réassigner cfg (et l'erreur d'étendue)
            try:
                cfg_out: dict[str, Any] = dict(cfg) if isinstance(cfg, dict) else {}
            except Exception:
                cfg_out = {}
            cfg_out["plugins"] = new_plugins
            cfg_out["plugin_order"] = order_ids
            # Écrire bcasl.json (toujours JSON, priorité sur autres formats)
            target = workspace_root / "bcasl.json"
            try:
                target.write_text(json.dumps(cfg_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                try:
                    if hasattr(self, "log") and self.log is not None:
                        self.log.append(
                            self.tr(
                                "✅ Plugins/API enregistrés avec ordre dans bcasl.json",
                                "✅ API plugins and order saved to bcasl.json",
                            )
                        )
                except Exception:
                    pass
                dlg.accept()
            except Exception as e:
                QMessageBox.critical(
                    dlg,
                    self.tr("Erreur", "Error"),
                    self.tr(f"Impossible d'écrire bcasl.json: {e}", f"Failed to write bcasl.json: {e}"),
                )

        btn_save.clicked.connect(do_save)
        btn_cancel.clicked.connect(dlg.reject)
        # Open non-modally to avoid blocking the UI thread
        try:
            dlg.setModal(False)
        except Exception:
            pass
        try:
            dlg.setWindowModality(Qt.NonModal)
        except Exception:
            pass
        try:
            dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        except Exception:
            try:
                dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            except Exception:
                pass
        # Keep a reference to avoid GC and clear it on finish
        try:
            self._api_loader_dlg = dlg
        except Exception:
            pass
        try:
            dlg.finished.connect(lambda _=None: setattr(self, "_api_loader_dlg", None))
        except Exception:
            pass
        try:
            dlg.show()
        except Exception:
            try:
                dlg.open()
            except Exception:
                try:
                    dlg.exec()
                except Exception:
                    pass
    except Exception as e:
        try:
            if hasattr(self, "log") and self.log is not None:
                self.log.append(f"⚠️ API Loader UI error: {e}")
        except Exception:
            pass


def run_pre_compile_async(self, on_done: Optional[callable] = None) -> None:
    """Lance BCASL en arrière-plan sans bloquer l'UI et appelle on_done(report) à la fin.
    - Ne bloque pas: aucun QEventLoop.exec() n'est utilisé.
    - on_done est rappelé dans le thread UI (via QTimer.singleShot).
    """
    try:
        if not getattr(self, "workspace_dir", None):
            if callable(on_done):
                on_done(None)
            return
        workspace_root = Path(self.workspace_dir).resolve()
        repo_root = Path(__file__).resolve().parents[1]
        api_dir = repo_root / "API"
        # Détection engine actif
        engine_id = None
        try:
            import utils.engines_loader as engines_loader  # import local

            idx = self.compiler_tabs.currentIndex() if hasattr(self, "compiler_tabs") and self.compiler_tabs else 0
            engine_id = engines_loader.registry.get_engine_for_tab(idx)
        except Exception:
            pass
        # Charger config utilisateur (création douce si manquante)
        missing_cfg = not (any(workspace_root.glob("bcasl.*")) or any(workspace_root.glob(".bcasl.*")))
        cfg = _load_workspace_config(workspace_root)
        if missing_cfg and (workspace_root / "bcasl.json").exists():
            try:
                if hasattr(self, "log") and self.log is not None:
                    self.log.append("📝 BCASL: fichier bcasl.json créé avec une configuration par défaut\n")
            except Exception:
                pass
        if engine_id and isinstance(cfg, dict) and "engine_id" not in cfg:
            cfg["engine_id"] = engine_id
        # Timeout: <= 0 illimité (0.0)
        import os as _os

        try:
            env_timeout = float(_os.environ.get("PYCOMPILER_BCASL_PLUGIN_TIMEOUT", "0"))
        except Exception:
            env_timeout = 0.0
        try:
            opt = cfg.get("options", {}) if isinstance(cfg, dict) else {}
            cfg_timeout = float(opt.get("plugin_timeout_s", 0.0)) if isinstance(opt, dict) else 0.0
        except Exception:
            cfg_timeout = 0.0
        plugin_timeout_raw = cfg_timeout if cfg_timeout != 0.0 else env_timeout
        plugin_timeout = plugin_timeout_raw if plugin_timeout_raw and plugin_timeout_raw > 0 else 0.0
        # Lancer le worker thread (aucune boucle imbriquée)
        from PySide6.QtCore import QTimer

        if QThread is not None and "_BCASLWorker" in globals():
            thread = QThread()
            worker = _BCASLWorker(workspace_root, api_dir, cfg, plugin_timeout)  # type: ignore[name-defined]
            # Conserver des références pour éviter la destruction du QThread avant sa fin
            try:
                self._bcasl_thread = thread
                self._bcasl_worker = worker
            except Exception:
                pass
            # Route logs and finish via a GUI-thread bridge to avoid cross-thread UI access
            bridge = _BCASLUiBridge(self, on_done, thread)
            try:
                self._bcasl_ui_bridge = bridge
            except Exception:
                pass
            if hasattr(self, "log") and self.log is not None:
                worker.log.connect(bridge.on_log)
            worker.finished.connect(bridge.on_finished)
            worker.finished.connect(worker.deleteLater)

            # Nettoyage des références et suppression différée du thread
            def _clear_refs():
                try:
                    if getattr(self, "_bcasl_thread", None) is thread:
                        self._bcasl_thread = None
                    if getattr(self, "_bcasl_worker", None) is worker:
                        self._bcasl_worker = None
                    # Clear soft timer reference
                    if hasattr(self, "_bcasl_soft_timer"):
                        try:
                            t = self._bcasl_soft_timer
                            if t:
                                t.stop()
                        except Exception:
                            pass
                        self._bcasl_soft_timer = None
                    if hasattr(self, "_bcasl_ui_bridge"):
                        try:
                            b = self._bcasl_ui_bridge
                            if b:
                                b.deleteLater()
                        except Exception:
                            pass
                        self._bcasl_ui_bridge = None
                except Exception:
                    pass
                try:
                    thread.deleteLater()
                except Exception:
                    pass

            thread.finished.connect(_clear_refs)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            thread.start()
            # Soft timeout fallback: if unlimited (plugin_timeout <= 0), allow user to skip BCASL after a delay
            try:
                if plugin_timeout <= 0:
                    import os as _os2

                    try:
                        opt2 = cfg.get("options", {}) if isinstance(cfg, dict) else {}
                        soft_s = float(
                            opt2.get(
                                "phase_soft_timeout_s", float(_os2.environ.get("PYCOMPILER_BCASL_SOFT_TIMEOUT", "30"))
                            )
                        )
                    except Exception:
                        soft_s = 30.0
                    if soft_s and soft_s > 0:
                        tmr = QTimer(self)
                        tmr.setSingleShot(True)

                        def _on_soft():
                            try:
                                # still running?
                                if getattr(self, "_bcasl_thread", None) is thread and thread.isRunning():
                                    from PySide6.QtWidgets import QMessageBox as _QMB

                                    res = _QMB.question(
                                        self,
                                        self.tr("BCASL trop long", "BCASL taking too long"),
                                        self.tr(
                                            f"Les plugins BCASL s'exécutent toujours après {soft_s:.0f}s.\nVoulez-vous les arrêter et démarrer la compilation maintenant ?",
                                            f"BCASL plugins are still running after {soft_s:.0f}s.\nDo you want to stop them and start compilation now?",
                                        ),
                                        _QMB.Yes | _QMB.No,
                                        _QMB.No,
                                    )
                                    if res == _QMB.Yes:
                                        try:
                                            ensure_bcasl_thread_stopped(self)
                                        except Exception:
                                            pass
                                        if callable(on_done):
                                            try:
                                                on_done(None)
                                            except Exception:
                                                pass
                            except Exception:
                                pass

                        tmr.timeout.connect(_on_soft)
                        tmr.start(int(soft_s * 1000))
                        self._bcasl_soft_timer = tmr
            except Exception:
                pass
            return
        # Fallback: si pas de Qt threading, exécuter rapidement et rappeler on_done
        try:
            manager = BCASL(workspace_root, config=cfg, plugin_timeout_s=plugin_timeout)
            enabled_dir = _prepare_enabled_plugins_dir(api_dir, cfg, workspace_root)
            loaded, errors = manager.load_plugins_from_directory(enabled_dir)
            if hasattr(self, "log") and self.log is not None:
                self.log.append(f"🧩 BCASL: {loaded} package(s) de plugins chargé(s) depuis API/\n")
                for mod, msg in errors or []:
                    self.log.append(f"⚠️ Plugin '{mod}': {msg}\n")
            # Appliquer activation/désactivation et priorités depuis la config
            try:
                pmap = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
                order_list = []
                try:
                    order_list = list(cfg.get("plugin_order", [])) if isinstance(cfg, dict) else []
                except Exception:
                    order_list = []
                if order_list:
                    for idx, pid in enumerate(order_list):
                        try:
                            self.log.append(f"⏫ Priorité {idx} pour {pid}\n")
                        except Exception:
                            pass
                        try:
                            manager.set_priority(pid, int(idx))
                        except Exception:
                            pass
                if isinstance(pmap, dict):
                    for pid, val in pmap.items():
                        try:
                            if isinstance(val, dict) and "priority" in val:
                                manager.set_priority(pid, int(val.get("priority", 0)))
                        except Exception:
                            pass
            except Exception:
                pass
            report = manager.run_pre_compile(PreCompileContext(workspace_root))
        except Exception as _e:
            report = None
            try:
                if hasattr(self, "log") and self.log is not None:
                    self.log.append(f"⚠️ Erreur BCASL: {_e}\n")
            except Exception:
                pass
        if callable(on_done):
            try:
                on_done(report)
            except Exception:
                pass
    except Exception as e:
        try:
            if hasattr(self, "log") and self.log is not None:
                self.log.append(f"⚠️ Erreur BCASL (async): {e}\n")
        except Exception:
            pass
        if callable(on_done):
            try:
                on_done(None)
            except Exception:
                pass


def run_pre_compile(self) -> Optional[object]:
    """Exécute la phase BCASL de pré-compilation.

    - project_root (BCASL) = workspace utilisateur (self.workspace_dir)
    - plugins chargés depuis <repo_root>/API (packages Python)
    Retourne le rapport si disponible, sinon None.
    """
    try:
        if not getattr(self, "workspace_dir", None):
            # Rien à faire si workspace invalide
            return None
        workspace_root = Path(self.workspace_dir).resolve()
        repo_root = Path(__file__).resolve().parents[1]
        api_dir = repo_root / "API"

        # Détection modulaire de l'engine actif (sans valeurs codées en dur)
        engine_id = None
        try:
            import utils.engines_loader as engines_loader  # import local pour limiter le coût si non utilisé

            idx = self.compiler_tabs.currentIndex() if hasattr(self, "compiler_tabs") and self.compiler_tabs else 0
            engine_id = engines_loader.registry.get_engine_for_tab(idx)
        except Exception:
            pass

        # Configuration BCASL (préférence à la config utilisateur)
        missing_cfg = not (any(workspace_root.glob("bcasl.*")) or any(workspace_root.glob(".bcasl.*")))
        cfg = _load_workspace_config(workspace_root)
        if missing_cfg and (workspace_root / "bcasl.json").exists():
            try:
                if hasattr(self, "log") and self.log is not None:
                    self.log.append("📝 BCASL: fichier bcasl.json créé avec une configuration par défaut\n")
            except Exception:
                pass
        if engine_id and "engine_id" not in cfg:
            cfg["engine_id"] = engine_id
        # Timeout configurable: options.plugin_timeout_s in bcasl.* or env PYCOMPILER_BCASL_PLUGIN_TIMEOUT; <= 0 means unlimited
        import os as _os

        try:
            env_timeout = float(_os.environ.get("PYCOMPILER_BCASL_PLUGIN_TIMEOUT", "0"))
        except Exception:
            env_timeout = 0.0
        try:
            opt = cfg.get("options", {}) if isinstance(cfg, dict) else {}
            cfg_timeout = float(opt.get("plugin_timeout_s", 0.0)) if isinstance(opt, dict) else 0.0
        except Exception:
            cfg_timeout = 0.0
        plugin_timeout_raw = cfg_timeout if cfg_timeout != 0.0 else env_timeout
        plugin_timeout = plugin_timeout_raw if plugin_timeout_raw and plugin_timeout_raw > 0 else 0.0
        # Run BCASL in background to avoid blocking UI when plugins use no progress UI
        if QThread is not None and QEventLoop is not None and "_BCASLWorker" in globals():
            try:
                thread = QThread()
                worker = _BCASLWorker(workspace_root, api_dir, cfg, plugin_timeout)  # type: ignore[name-defined]
                result_holder: dict[str, Any] = {"report": None}
                if hasattr(self, "log") and self.log is not None:
                    bridge2 = _BCASLUiBridge(self, None, thread)
                    worker.log.connect(bridge2.on_log)
                    try:
                        thread.finished.connect(bridge2.deleteLater)
                    except Exception:
                        pass

                def _on_finished(rep):
                    result_holder["report"] = rep
                    try:
                        thread.quit()
                    except Exception:
                        pass

                worker.finished.connect(_on_finished)
                worker.finished.connect(worker.deleteLater)
                thread.finished.connect(thread.deleteLater)
                worker.moveToThread(thread)
                thread.started.connect(worker.run)
                thread.start()
                loop = QEventLoop()
                thread.finished.connect(loop.quit)
                loop.exec()  # nested loop; UI remains responsive
                report = result_holder.get("report")
                if report and hasattr(self, "log") and self.log is not None:
                    self.log.append("BCASL - Rapport:\n")
                    for item in report:
                        state = "OK" if item.success else f"FAIL: {item.error}"
                        self.log.append(f" - {item.plugin_id}: {state} ({item.duration_ms:.1f} ms)\n")
                    self.log.append(report.summary() + "\n")
                return report
            except Exception:
                # Fallback to synchronous path on any threading error
                pass
        # Synchronous fallback (no Qt available)
        manager = BCASL(workspace_root, config=cfg, plugin_timeout_s=plugin_timeout)
        enabled_dir = _prepare_enabled_plugins_dir(api_dir, cfg, workspace_root)
        loaded, errors = manager.load_plugins_from_directory(enabled_dir)
        if hasattr(self, "log") and self.log is not None:
            self.log.append(f"🧩 BCASL: {loaded} package(s) de plugins chargé(s) depuis API/\n")
            for mod, msg in errors or []:
                self.log.append(f"⚠️ Plugin '{mod}': {msg}\n")
        # Appliquer activation/désactivation et priorités depuis la config
        try:
            pmap = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
            order_list = []
            try:
                order_list = list(cfg.get("plugin_order", [])) if isinstance(cfg, dict) else []
            except Exception:
                order_list = []
            if order_list:
                for idx, pid in enumerate(order_list):
                    try:
                        self.log.append(f"⏫ Priorité {idx} pour {pid}\n")
                    except Exception:
                        pass
                    try:
                        manager.set_priority(pid, int(idx))
                    except Exception:
                        pass
            if isinstance(pmap, dict):
                for pid, val in pmap.items():
                    try:
                        if isinstance(val, dict) and "priority" in val:
                            manager.set_priority(pid, int(val.get("priority", 0)))
                    except Exception:
                        pass
        except Exception:
            pass
        report = manager.run_pre_compile(PreCompileContext(workspace_root))
        if hasattr(self, "log") and self.log is not None:
            self.log.append("BCASL - Rapport:\n")
            for item in report:
                state = "OK" if item.success else f"FAIL: {item.error}"
                self.log.append(f" - {item.plugin_id}: {state} ({item.duration_ms:.1f} ms)\n")
            self.log.append(report.summary() + "\n")
        return report
    except Exception as e:
        try:
            if hasattr(self, "log") and self.log is not None:
                self.log.append(f"⚠️ Erreur BCASL: {e}\n")
        except Exception:
            pass
        return None
