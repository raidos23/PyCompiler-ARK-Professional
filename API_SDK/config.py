# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

"""
API_SDK.config — Configuration helpers for API plugins

This module encapsulates configuration access and persistence utilities used by
API plugins:
- ConfigView: read/write view over a dict-backed configuration
- load_workspace_config: read bcasl.* or .bcasl.* (json/yaml/toml/ini/cfg)
- ensure_settings_file: create a plugin-level settings file with safe defaults
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import io
import json

# Optional parsers
try:
    import yaml as _yaml  # type: ignore
except Exception:  # pragma: no cover
    _yaml = None  # type: ignore

try:
    import tomllib as _toml  # type: ignore  # Python 3.11+
except Exception:  # pragma: no cover
    try:
        import tomli as _toml  # type: ignore  # backport
    except Exception:  # pragma: no cover
        _toml = None  # type: ignore

Pathish = Union[str, Path]


class ConfigView:
    """Convenient read/write view over the global configuration.

    Typical usage: sub = cfg.for_plugin("my_plugin"); v = sub.get("key", default)
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        self._data: Dict[str, Any] = data or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def for_plugin(self, plugin_id: str) -> "ConfigView":
        plugins = self._data.setdefault("plugins", {})
        plugin_cfg = plugins.setdefault(plugin_id, {})
        if not isinstance(plugin_cfg, dict):
            plugin_cfg = {}
            plugins[plugin_id] = plugin_cfg
        return ConfigView(plugin_cfg)

    # Common helpers
    @property
    def required_files(self) -> List[str]:
        rf = self._data.get("required_files", [])
        return list(rf) if isinstance(rf, (list, tuple)) else []

    @property
    def file_patterns(self) -> List[str]:
        fp = self._data.get("file_patterns", [])
        return list(fp) if isinstance(fp, (list, tuple)) else []

    @property
    def exclude_patterns(self) -> List[str]:
        ep = self._data.get("exclude_patterns", [])
        return list(ep) if isinstance(ep, (list, tuple)) else []

    @property
    def engine_id(self) -> Optional[str]:
        v = self._data.get("engine_id")
        return str(v) if isinstance(v, (str, bytes)) else None


def load_workspace_config(workspace_root: Path) -> Dict[str, Any]:
    """Read bcasl.* or .bcasl.* at the workspace root, supporting JSON/YAML/TOML/INI/CFG."""

    def _parse_text_config(p: Path) -> Dict[str, Any]:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            return {}
        suffix = p.suffix.lower().lstrip(".")
        try:
            if suffix == "json":
                return json.loads(text)
            if suffix in ("yaml", "yml") and _yaml:
                data = _yaml.safe_load(text)
                return data if isinstance(data, dict) else {}
            if suffix == "toml" and _toml:
                return _toml.loads(text)
            if suffix in ("ini", "cfg"):
                import configparser as _cp
                cp = _cp.ConfigParser()
                cp.read_string(text)
                cfg: Dict[str, Any] = {}
                for sect in cp.sections():
                    cfg[sect] = {k: v for k, v in cp.items(sect)}
                if cp.defaults():
                    cfg.setdefault("DEFAULT", {}).update(dict(cp.defaults()))
                return cfg
        except Exception:
            pass
        # Heuristic multi-format fallback
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
                    import configparser as _cp
                    cp = _cp.ConfigParser()
                    cp.read_string(text)
                    cfg: Dict[str, Any] = {}
                    for sect in cp.sections():
                        cfg[sect] = {k: v for k, v in cp.items(sect)}
                    if cp.defaults():
                        cfg.setdefault("DEFAULT", {}).update(dict(cp.defaults()))
                    return cfg
            except Exception:
                continue
        return {}

    candidates = [
        "bcasl.json", ".bcasl.json",
        "bcasl.yaml", ".bcasl.yaml",
        "bcasl.yml", ".bcasl.yml",
        "bcasl.toml", ".bcasl.toml",
        "bcasl.ini", ".bcasl.ini",
        "bcasl.cfg", ".bcasl.cfg",
    ]
    for name in candidates:
        p = workspace_root / name
        if p.exists() and p.is_file():
            cfg = _parse_text_config(p)
            if isinstance(cfg, dict):
                return cfg
            return {}

    for p in list(workspace_root.glob("bcasl.*")) + list(workspace_root.glob(".bcasl.*")):
        if p.is_file():
            cfg = _parse_text_config(p)
            if isinstance(cfg, dict):
                return cfg
    return {}


def ensure_settings_file(
    sctx: Any,
    *,
    subdir: str = "config",
    basename: str = "settings",
    fmt: str = "yaml",
    defaults: Optional[Dict[str, Any]] = None,
    overwrite: bool = False,
) -> Path:
    """Ensure a workspace settings file exists and return its Path.

    - Creates <workspace>/<subdir>/<basename>.<ext> if missing
    - Formats supported: yaml (default), json, toml, ini/cfg
    - Uses safe workspace path composition via sctx.safe_path
    """
    fmt_norm = (fmt or "yaml").lower()
    if fmt_norm not in ("yaml", "json", "toml", "ini", "cfg"):
        raise ValueError(f"Unsupported settings format: {fmt}")
    # Choose extension
    if fmt_norm == "yaml":
        ext = "yaml"
    elif fmt_norm == "json":
        ext = "json"
    elif fmt_norm == "toml":
        ext = "toml"
    else:
        ext = "ini"

    target = sctx.safe_path(subdir, f"{basename}.{ext}")
    # Create directory
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"Unable to create settings directory: {target.parent}") from e

    if target.exists() and not overwrite:
        return target

    data: Dict[str, Any] = dict(defaults or {
        "name": "World",
        "install_subject": "my_tool",
        "install_explanation": "Installation de dépendances nécessaires",
    })

    text: str
    try:
        if fmt_norm == "json":
            text = json.dumps(data, indent=2, ensure_ascii=False)
        elif fmt_norm == "yaml":
            if _yaml is not None:
                text = _yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
            else:
                # Minimal YAML-ish fallback
                lines = []
                for k, v in data.items():
                    if isinstance(v, (int, float)):
                        vs = str(v)
                    elif isinstance(v, bool):
                        vs = "true" if v else "false"
                    else:
                        vs = json.dumps(str(v), ensure_ascii=False)
                    lines.append(f"{k}: {vs}")
                text = "\n".join(lines) + "\n"
        elif fmt_norm == "toml":
            # Minimal TOML fallback (no dumper guaranteed)
            lines = []
            for k, v in data.items():
                if isinstance(v, bool):
                    vs = "true" if v else "false"
                elif isinstance(v, (int, float)):
                    vs = str(v)
                else:
                    s = str(v).replace("\"", "\\\"")
                    vs = f'"{s}"'
                lines.append(f"{k} = {vs}")
            text = "\n".join(lines) + "\n"
        else:  # ini/cfg
            import configparser as _cp
            buf = io.StringIO()
            cp = _cp.ConfigParser()
            cp["DEFAULT"] = {k: str(v) for k, v in data.items()}
            cp.write(buf)
            text = buf.getvalue()
    except Exception as e:
        raise RuntimeError(f"Failed to serialize default settings as {fmt_norm}") from e

    try:
        target.write_text(text, encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Unable to write settings file: {target}") from e
    return target


__all__ = [
    "ConfigView",
    "load_workspace_config",
    "ensure_settings_file",
]
