# SPDX-License-Identifier: GPL-3.0-only
# API_SDK — Industrial-grade modular facade for API plugins
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Optional, Union

# -----------------------------
# Versioning and capabilities
# -----------------------------
__version__ = "3.2.3"

def _parse_version(v: str) -> tuple:
    try:
        parts = v.strip().split("+")[0].split("-")[0].split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except Exception:
        return (0, 0, 0)

def ensure_min_sdk(required: str) -> bool:
    """Return True if current API_SDK version >= required (semver)."""
    try:
        cur = _parse_version(__version__)
        need = _parse_version(str(required))
        return cur >= need
    except Exception:
        return False

# -----------------------------
# Modular re-exports (progress, config, context)
# -----------------------------
# -----------------------------
# i18n facade (host-level)
# -----------------------------
from Core.i18n import (  # type: ignore  # noqa: E402
    available_languages,
    get_translations,
    normalize_lang_pref,
    resolve_system_language,
)

from .config import (  # noqa: E402
    ConfigView,
    ensure_settings_file,
    load_workspace_config,
)
from .context import (  # noqa: E402
    SDKContext,
)
from .progress import (  # noqa: E402
    ProgressHandle,
    create_progress,
    progress,
    show_msgbox,
    sys_msgbox_for_installing,
)

# -----------------------------
# Plugin base (BCASL) and decorator
# -----------------------------
# Reuse BCASL types to guarantee compatibility with the host
try:  # noqa: E402
    from bcasl import (
        BCASL as BCASL,
        ExecutionReport as ExecutionReport,
        Bc_PluginBase as Bc_PluginBase,
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
    class Bc_PluginBase:  # type: ignore
        pass

    class PluginMeta:  # type: ignore
        pass

    class PreCompileContext:  # type: ignore
        pass

    class ExecutionReport:  # type: ignore
        pass

    class BCASL:  # type: ignore
        pass

    def register_plugin(cls: Any) -> Any:  # type: ignore
        setattr(cls, "__bcasl_plugin__", True)
        return cls
    BCASL_PLUGIN_REGISTER_FUNC = "bcasl_register"

# ACASL PostCompileContext facade (optional, available when acasl package is present)
try:
    from acasl import ACASLContext as PostCompileContext  # type: ignore
except Exception:
    class PostCompileContext:  # type: ignore
        pass

# ACASL PluginBase (post-compile plugins)
class Ac_PluginBase:  # type: ignore
    """Base class for ACASL (post-compile) plugins."""

    pass

Pathish = Union[str, Path]

def _sdk_snake_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

def plugin(id: Optional[str] = None, version: str = "", description: str = ""):
    """Decorator to declare plugin metadata quickly.

    Usage:
        @plugin(id="my_plugin", version="0.1.0", description="...")
        class MyPlugin(PluginBase): ...
    If id is omitted, it is derived from the class name in snake_case.
    """

    def _wrap(cls):
        if not issubclass(cls, Bc_PluginBase):
            raise TypeError("@plugin must decorate a subclass of PluginBase")
        cls.id = id or _sdk_snake_case(cls.__name__)
        cls.version = version
        cls.description = description
        return cls
    return _wrap

def _detect_workspace_root(pre_ctx: Any) -> Path:
    # 1) Use the workspace selected by the application (UI)
    try:
        from Core.worker import get_selected_workspace  # type: ignore

        sel = get_selected_workspace()
        if sel:
            p = Path(sel)
            if p.exists():
                return p.resolve()
    except Exception:
        pass
    # 2) Fallback to common attributes on the pre-compile context
    for attr in ("workspace_root", "project_root", "root", "base_dir", "path"):
        try:
            v = getattr(pre_ctx, attr)
            if v:
                p = Path(v)
                if p.exists():
                    return p.resolve()
        except Exception:
            continue
    raise RuntimeError(
        "Workspace not found: select a folder in the UI or provide 'workspace_root' in context."
    )

def wrap_context(
    pre_ctx: PreCompileContext,
    *,
    log_fn: Optional[Any] = None,
    engine_id: Optional[str] = None,
) -> SDKContext:
    root = _detect_workspace_root(pre_ctx)
    cfg = load_workspace_config(root)
    engine = engine_id or getattr(pre_ctx, "engine_id", None)
    return SDKContext(
        workspace_root=root,
        config_view=ConfigView(cfg),
        log_fn=log_fn,
        engine_id=engine,
    )

def wrap_post_context(
    post_ctx: PostCompileContext, *, log_fn: Optional[Any] = None
) -> SDKContext:
    """Wrap an ACASL PostCompileContext into SDKContext for reuse of the same helpers.
    - Copies workspace root and artifacts
    - Loads workspace config
    - Enforces ACASL scope: restrict file operations to engine output directory when provided
    """
    try:
        ws = Path(getattr(post_ctx, "workspace_root", "."))
    except Exception:
        ws = Path(".")
    root = ws.resolve()
    cfg = load_workspace_config(root)
    # Resolve allowed output directory (ACASL scope)
    allowed_dir = None
    try:
        od = getattr(post_ctx, "output_dir", None)
        if od:
            try:
                allowed_dir = Path(str(od)).resolve()
            except Exception:
                allowed_dir = None
    except Exception:
        allowed_dir = None
    # Artifacts: best-effort ensure they are within allowed_dir when set
    try:
        arts_in = list(getattr(post_ctx, "artifacts", []) or [])
    except Exception:
        arts_in = []
    arts: list[str] = []
    if allowed_dir is not None:
        for a in arts_in:
            try:
                rp = Path(a).resolve()
                _ = rp.relative_to(allowed_dir)
                arts.append(str(rp))
            except Exception:
                # skip artifacts outside of allowed scope
                continue
    else:
        arts = list(arts_in)
    return SDKContext(
        workspace_root=root,
        config_view=ConfigView(cfg),
        log_fn=log_fn,
        engine_id=None,
        artifacts=arts,
        allowed_dir=allowed_dir,
    )

# -----------------------------
# Subprocess helper (safe run)
# -----------------------------

def run_command(
    cmd: list[str] | str,
    *,
    timeout_s: int = 60,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    shell: bool = False,
) -> tuple[int, str, str]:
    """Run a command with timeout, sanitized environment and captured output.
    Returns (returncode, stdout, stderr). On timeout, returns (-999, out, err).
    - Sanitizes environment by default (minimal PATH/LANG/HOME) and merges 'env' overrides.
    - Does not expand through the shell unless shell=True is explicitly provided.
    """
    import os as _os
    import subprocess

    try:
        base_env = {
            k: v
            for k, v in _os.environ.items()
            if k in ("PATH", "LANG", "HOME", "LC_ALL", "LC_CTYPE")
        }
    except Exception:
        base_env = {}
    if isinstance(env, dict):
        base_env.update({str(k): str(v) for k, v in env.items()})
    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd,
            env=base_env,
            shell=bool(shell),
            capture_output=True,
            text=True,
            timeout=int(timeout_s) if timeout_s else None,
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired as te:
        out = (
            te.stdout.decode()
            if isinstance(te.stdout, (bytes, bytearray))
            else (te.stdout or "")
        )
        err = (
            te.stderr.decode()
            if isinstance(te.stderr, (bytes, bytearray))
            else (te.stderr or "")
        )
        return -999, out, err

# -----------------------------
# Per-plugin i18n loader (from local languages/)
# -----------------------------

def _parse_local_lang_text(text: str, suffix: str) -> dict[str, Any]:
    try:
        if suffix == ".json":
            return json.loads(text)
        if suffix in (".yaml", ".yml") and _yaml:
            data = _yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        if suffix == ".toml" and _toml:
            return _toml.loads(text)
        if suffix in (".ini", ".cfg"):
            import configparser as _cp

            cp = _cp.ConfigParser()
            cp.read_string(text)
            cfg: dict[str, Any] = {}
            for sect in cp.sections():
                cfg[sect] = {k: v for k, v in cp.items(sect)}
            if cp.defaults():
                cfg.setdefault("DEFAULT", {}).update(dict(cp.defaults()))
            return cfg
    except Exception:
        return {}
    return {}

async def load_plugin_translations(
    plugin_file_or_dir: Pathish,
    lang_pref: Optional[str] = None,
    *,
    fallback_to_core: bool = True,
) -> dict[str, Any]:
    """Load plugin-level translations asynchronously from plugin languages/ dir and merge with core i18n.

    - Resolves lang code via normalize_lang_pref (async, CPU-only)
    - Reads plugin-local i18n files in a background thread
    - Merges with core translations loaded via get_translations_async when fallback_to_core is True
    """
    try:
        p = Path(plugin_file_or_dir)
        pdir = p if p.is_dir() else p.parent
    except Exception:
        pdir = Path(".")
    lang_code = await normalize_lang_pref(lang_pref)
    lang_dir = pdir / "languages"

    # Resolve System asynchronously
    if lang_code == "System":
        lang_code = await resolve_system_language()

    # Load local language file in a worker thread (filesystem IO)
    local = (
        await asyncio.to_thread(_load_local_lang_file_any, lang_dir, lang_code) or {}
    )
    if (not local) and lang_code != "en":
        local = await asyncio.to_thread(_load_local_lang_file_any, lang_dir, "en") or {}

    if fallback_to_core:
        base = await get_translations(lang_code)
        merged: dict[str, Any] = dict(base) if isinstance(base, dict) else {}
        try:
            merged.update(local)
        except Exception:
            pass
    else:
        merged = dict(local)

    # Normalize meta
    try:
        top_name = merged.get("name") if isinstance(merged, dict) else None
        top_code = merged.get("code") if isinstance(merged, dict) else None
        meta_in = merged.get("_meta", {}) if isinstance(merged, dict) else {}
        meta = {
            "code": (
                top_code
                or (meta_in.get("code") if isinstance(meta_in, dict) else None)
                or lang_code
            ),
            "name": (
                top_name
                or (meta_in.get("name") if isinstance(meta_in, dict) else None)
                or (
                    "English"
                    if lang_code == "en"
                    else ("Français" if lang_code == "fr" else lang_code)
                )
            ),
        }
        merged["_meta"] = meta
    except Exception:
        pass
    return merged

def _load_local_lang_file_any(lang_dir: Path, code: str) -> Optional[dict[str, Any]]:
    if not lang_dir.exists() or not lang_dir.is_dir():
        return None
    candidates = [
        lang_dir / f"{code}.json",
        lang_dir / f"{code}.yaml",
        lang_dir / f"{code}.yml",
        lang_dir / f"{code}.toml",
        lang_dir / f"{code}.ini",
        lang_dir / f"{code}.cfg",
    ]
    for p in candidates:
        try:
            if p.exists() and p.is_file():
                text = p.read_text(encoding="utf-8")
                data = _parse_local_lang_text(text, p.suffix.lower())
                if isinstance(data, dict) and data:
                    return data
        except Exception:
            continue
    return None

# Optional parsers for plugin-level i18n files
try:
    import yaml as _yaml  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover
    _yaml = None  # type: ignore
try:  # noqa: E402
    import tomllib as _toml  # Python 3.11+
except Exception:  # pragma: no cover
    try:
        import tomli as _toml  # type: ignore # backport
    except Exception:  # pragma: no cover
        _toml = None

# -----------------------------
# Scaffolding utilities
# -----------------------------
PLUGIN_TEMPLATE = """# SPDX-License-Identifier: GPL-3.0-only
"""
PLUGIN_TEMPLATE += "\n".join(
    [
        "from __future__ import annotations",
        "",
        "from API_SDK import PluginBase, PreCompileContext, wrap_context, ConfigView, plugin, InstallAuth, PluginMeta",
        "",
        '@plugin(id="{plugin_id}", version="0.1.0", description="{description}")',
        "class {class_name}(PluginBase):",
        "    def on_pre_compile(self, ctx: PreCompileContext) -> None:",
        "        sctx = wrap_context(ctx)",
        "        subcfg = sctx.config_view.for_plugin(self.id)",
        '        name = subcfg.get("name", "World")',
        '        sctx.log_info(f"Hello {name}! (engine={{{{sctx.engine_id}}}})")',
        '        sctx.msg_info("Example", f"Hello {name}!")',
        '        required = sctx.config_view.required_files or ["main.py"]',
        "        missing = sctx.require_files(required)",
        "        if missing:",
        '            raise FileNotFoundError(f"Missing required files: {[str(m) for m in missing]}")',
        "",
        'META = PluginMeta(id="{plugin_id}", name="{class_name}", version="0.1.0", description="{description}")',
        "PLUGIN = {class_name}(META)",
        "",
        "def bcasl_register(manager):",
        "    manager.add_plugin(PLUGIN)",
    ]
)

def scaffold_plugin(
    target_dir: Pathish,
    plugin_id: str,
    name: Optional[str] = None,
    description: str = "Generated plugin",
) -> Path:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", plugin_id):
        raise ValueError("plugin_id must be a valid Python identifier")

    class_name = name or "".join(part.capitalize() for part in plugin_id.split("_"))
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", class_name):
        raise ValueError("derived class_name invalid; provide 'name' to override")

    pkg_dir = target / plugin_id
    if pkg_dir.exists():
        raise FileExistsError(f"Package already exists: {pkg_dir}")
    pkg_dir.mkdir(parents=False, exist_ok=False)

    file_path = pkg_dir / "__init__.py"
    content = PLUGIN_TEMPLATE.format(
        plugin_id=plugin_id, class_name=class_name, description=description
    )
    file_path.write_text(content + "\n", encoding="utf-8")
    return file_path

# -----------------------------
# Public bridge to set selected workspace from plugins
# -----------------------------

def set_selected_workspace(path: Pathish) -> bool:
    """Always accept workspace change requests (SDK-level contract).

    - Auto-creates the target directory if missing
    - Invokes the GUI-side bridge when available (non-blocking acceptance)
    - Returns True in all cases (including headless/no-GUI environments)
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
        from Core.worker import request_workspace_change_from_api  # type: ignore

        try:
            request_workspace_change_from_api(str(path))
        except Exception:
            pass
    except Exception:
        # No GUI or bridge available — still accept
        pass
    return True

# -----------------------------
# Capabilities report
# -----------------------------

def get_capabilities() -> dict:
    return {
        "version": __version__,
        "progress": {
            "context_manager": True,
            "qt": True,
        },
        "config": {
            "multi_format": True,
            "ensure_settings_file": True,
        },
        "context": {
            "iter_cache": True,
            "batch_replace": True,
            "parallel_map": True,
        },
        "i18n": True,
        "subprocess": True,
        "workspace_bridge": True,
        "acasl": {
            "post_context_wrapper": True,
            "artifacts_in_context": True,
        },
    }

def sdk_info() -> dict:
    return {
        "version": __version__,
        "exports": sorted(list(__all__)),
        "capabilities": get_capabilities(),
    }

__all__ = [
    # Progress/messaging
    "ProgressHandle",
    "create_progress",
    "progress",
    "show_msgbox",
    "sys_msgbox_for_installing",
    # Config
    "ConfigView",
    "load_workspace_config",
    "ensure_settings_file",
    # Context
    "SDKContext",
    "PostCompileContext",
    "wrap_post_context",
    # BCASL facade
    "PluginBase",
    "PluginMeta",
    "PreCompileContext",
    "ExecutionReport",
    "BCASL",
    "register_plugin",
    "BCASL_PLUGIN_REGISTER_FUNC",
    # ACASL facade
    "Ac_PluginBase",
    # Decorator & wrapping
    "plugin",
    "wrap_context",
    # i18n helpers
    "normalize_lang_pref",
    "available_languages",
    "resolve_system_language",
    "get_translations",
    "load_plugin_translations",
    # Scaffolding
    "scaffold_plugin",
    # UI bridge
    "set_selected_workspace",
    # Version & caps
    "__version__",
    "ensure_min_sdk",
    "get_capabilities",
    "sdk_info",
]
