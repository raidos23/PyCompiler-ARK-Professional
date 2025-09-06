# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import threading
import shutil
from pathlib import Path
from typing import Callable, List, Optional, Any
import json

from PySide6.QtWidgets import QMessageBox
try:
    from PySide6.QtCore import QTimer, QObject, Signal, Slot, QThread
except Exception:  # pragma: no cover
    QTimer = None  # type: ignore
    QObject = None  # type: ignore
    Signal = None  # type: ignore
    Slot = None  # type: ignore
    QThread = None  # type: ignore


class ACASLContext:
    def __init__(self, gui, artifacts: List[str]):
        self.gui = gui
        self.workspace_root = Path(getattr(gui, 'workspace_dir', os.getcwd()) or os.getcwd())
        self.artifacts = [str(Path(a)) for a in artifacts]
        self._closing_flag = lambda: bool(getattr(gui, '_closing', False))

    def _post_ui(self, fn) -> None:
        """Post a callable to the GUI thread in a safe, cross-version way.
        Uses QTimer.singleShot(0, fn) when available; otherwise falls back to direct call.
        Avoids passing QObject receivers to singleShot to prevent ABI/overload issues.
        """
        # Do not schedule UI work if GUI is closing
        try:
            if bool(getattr(self.gui, '_closing', False)):
                return
        except Exception:
            pass
        try:
            if QTimer is not None:
                try:
                    QTimer.singleShot(0, fn)
                except Exception:
                    try:
                        fn()
                    except Exception:
                        pass
            else:
                try:
                    fn()
                except Exception:
                    pass
        except Exception:
            pass

    # Logging helpers
    def log_info(self, msg: str) -> None:
        try:
            if hasattr(self.gui, 'log') and self.gui.log:
                self._post_ui(lambda: self.gui.log.append(msg))
        except Exception:
            pass

    def log_warn(self, msg: str) -> None:
        try:
            if hasattr(self.gui, 'log') and self.gui.log:
                self._post_ui(lambda: self.gui.log.append(f"⚠️ {msg}"))
        except Exception:
            pass

    def log_error(self, msg: str) -> None:
        try:
            if hasattr(self.gui, 'log') and self.gui.log:
                self._post_ui(lambda: self.gui.log.append(f"❌ {msg}"))
        except Exception:
            pass

    # Simple message boxes (bilingual content should be provided by the caller)
    def msg_info(self, title: str, text: str) -> None:
        try:
            self._post_ui(lambda: QMessageBox.information(self.gui, title, text))
        except Exception:
            pass

    def msg_warn(self, title: str, text: str) -> None:
        try:
            self._post_ui(lambda: QMessageBox.warning(self.gui, title, text))
        except Exception:
            pass

    def msg_question(self, title: str, text: str, default_yes: bool = True) -> bool:
        try:
            btn = QMessageBox.Yes if default_yes else QMessageBox.No
            import threading as _th
            if _th.current_thread() is _th.main_thread():
                res = QMessageBox.question(self.gui, title, text, QMessageBox.Yes | QMessageBox.No, btn)
                return res == QMessageBox.Yes
            else:
                # Post a UI question for visibility but return a safe default immediately
                self._post_ui(lambda: QMessageBox.question(self.gui, title, text, QMessageBox.Yes | QMessageBox.No, btn))
                return bool(default_yes)
        except Exception:
            return bool(default_yes)

    def is_canceled(self) -> bool:
        return self._closing_flag()


def _acasl_try_open_engine_output(gui) -> None:
    """Invoke the current engine's on_success to open the output folder once.
    Relies on markers and last success info set by utils.compiler.handle_finished.
    This function must be called on the GUI thread.
    """
    try:
        # Already opened once during engine on_success
        if getattr(gui, '_engine_output_opened', False):
            return
        engine_id = getattr(gui, '_last_success_engine_id', None)
        last_map = getattr(gui, '_last_success_files', None)
        file = None
        if engine_id and isinstance(last_map, dict):
            file = last_map.get(engine_id)
        if not file:
            # Fallback: resolve engine from current tab and look up last file
            try:
                import utils.engines_loader as engines_loader
                idx = gui.compiler_tabs.currentIndex() if hasattr(gui, 'compiler_tabs') and gui.compiler_tabs else 0
                eid = engines_loader.registry.get_engine_for_tab(idx)
                if eid and isinstance(last_map, dict):
                    file = last_map.get(eid)
                    engine_id = eid
            except Exception:
                pass
        if engine_id and file:
            try:
                # ACASL-only policy: determine and open output folder without delegating to engines
                try:
                    from engine_sdk.utils import open_output_directory as _open_out  # type: ignore
                except Exception:
                    _open_out = None  # type: ignore
                try:
                    if _open_out:
                        _open_out(gui, engine_id=str(engine_id), source_file=str(file), artifacts=getattr(gui, '_last_artifacts', None))
                except Exception:
                    pass
                # Mark as opened attempt to avoid duplicates
                try:
                    setattr(gui, '_engine_output_opened', True)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass


# Helper functions for robust discovery without executing plugin code
def _has_acasl_marker(pkg_dir: Path) -> bool:
    try:
        init_py = pkg_dir / "__init__.py"
        if not init_py.exists():
            return False
        txt = init_py.read_text(encoding="utf-8", errors="ignore")
        import re as _re
        return _re.search(r"(?m)^\s*ACASL_PLUGIN\s*=\s*True\s*(#.*)?$", txt) is not None
    except Exception:
        return False

from typing import Dict

def _extract_acasl_meta_from_text(init_path: Path) -> Optional[Dict[str, str]]:
    """Parse __init__.py text to extract ACASL metadata without executing it.
    Returns dict with: id, description; optional name, version, author, created, license, compatibility, tags.
    """
    try:
        txt = init_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    import re as _re
    if not _re.search(r"(?m)^\s*ACASL_PLUGIN\s*=\s*True\s*(#.*)?$", txt):
        return None
    def _get(pat: str) -> str:
        m = _re.search(pat, txt, _re.S)
        return m.group("val").strip() if m else ""
    def _get_list(sym: str) -> list[str]:
        try:
            m = _re.search(rf"(?m)^\s*{sym}\s*=\s*(?P<val>\[.*?\])\s*$", txt, _re.S)
            if not m:
                m = _re.search(rf"{sym}\s*=\s*(?P<val>\[.*?\])", txt, _re.S)
            if m:
                import ast as _ast
                v = _ast.literal_eval(m.group("val"))
                if isinstance(v, list):
                    return [str(x) for x in v]
        except Exception:
            pass
        return []
    idv = _get(r"ACASL_ID\s*=\s*([\'\"])(?P<val>.+?)\1")
    desc = _get(r"ACASL_DESCRIPTION\s*=\s*([\'\"])(?P<val>.+?)\1")
    if not idv or not desc:
        return None
    name = _get(r"ACASL_NAME\s*=\s*([\'\"])(?P<val>.+?)\1")
    ver = _get(r"ACASL_VERSION\s*=\s*([\'\"])(?P<val>.+?)\1")
    author = _get(r"ACASL_AUTHOR\s*=\s*([\'\"])(?P<val>.+?)\1")
    created = _get(r"ACASL_CREATED\s*=\s*([\'\"])(?P<val>.+?)\1")
    lic = _get(r"ACASL_LICENSE\s*=\s*([\'\"])(?P<val>.+?)\1")
    compat = _get_list("ACASL_COMPATIBILITY")
    tags = _get_list("ACASL_TAGS")
    # Ensure a run symbol appears to exist (def or assignment)
    if not (_re.search(r"(?m)^\s*def\s+acasl_run\s*\(", txt) or _re.search(r"(?m)^\s*acasl_run\s*=\s*", txt)):
        return None
    return {
        "id": idv,
        "description": desc,
        "name": name,
        "version": ver,
        "author": author,
        "created": created,
        "license": lic,
        "compatibility": compat,
        "tags": tags,
    }

def _write_json_atomic(path: Path, data: dict) -> bool:
    """Atomically write JSON to path, with best-effort backup of existing file."""
    import tempfile
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        fd, tmp = tempfile.mkstemp(prefix=".acasl_", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            # Optional backup of existing file
            try:
                if path.exists():
                    bak = path.with_suffix(path.suffix + ".bak")
                    try:
                        if bak.exists():
                            bak.unlink()
                    except Exception:
                        pass
                    try:
                        path.replace(bak)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                os.replace(tmp, str(path))
            except Exception:
                shutil.move(tmp, str(path))
            try:
                os.chmod(str(path), 0o644)
            except Exception:
                pass
            return True
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
    except Exception:
        return False

# Global reference to the running thread (for cancellation)
_ACASL_THREAD: Optional[threading.Thread] = None

# Qt Worker to run ACASL in background and forward logs (BCASL-like)
if QObject is not None and Signal is not None:
    class _ACASLWorker(QObject):
        finished = Signal(object)  # report or None
        log = Signal(str)

        def __init__(self, gui, workspace_root: Path, api_dir: Path, cfg: dict, plugin_timeout: float, artifacts: list[str]) -> None:
            super().__init__()
            self.gui = gui
            self.workspace_root = workspace_root
            self.api_dir = api_dir
            self.cfg = cfg
            self.plugin_timeout = float(plugin_timeout) if plugin_timeout else 0.0
            self.artifacts = list(artifacts)

        @Slot()
        def run(self) -> None:
            try:
                # Discover available plugins
                plugins_all = _discover_plugins()
                id_to_meta: dict[str, dict] = {p['id']: p for p in plugins_all if isinstance(p, dict) and 'id' in p}
                id_to_folder: dict[str, str] = {p['id']: p.get('folder') for p in plugins_all if isinstance(p, dict) and 'id' in p}
                available_ids: list[str] = list(id_to_meta.keys())
                # Config and ordering
                cfg = self.cfg or {}
                pmap = cfg.get('plugins', {}) if isinstance(cfg, dict) else {}
                order = cfg.get('plugin_order', []) if isinstance(cfg, dict) else []
                enabled_order: list[str] = [pid for pid in order if pid in available_ids]
                for pid in available_ids:
                    if pid not in enabled_order:
                        try:
                            meta = pmap.get(pid, {})
                            enabled = bool(meta.get('enabled', True)) if isinstance(meta, dict) else bool(meta) if isinstance(meta, bool) else True
                        except Exception:
                            enabled = True
                        if enabled:
                            enabled_order.append(pid)
                try:
                    pr_map: dict[str, int] = {}
                    if isinstance(pmap, dict):
                        for k, v in pmap.items():
                            if isinstance(v, dict) and 'priority' in v:
                                try:
                                    pr_map[str(k)] = int(v.get('priority', 0))
                                except Exception:
                                    pass
                    if pr_map:
                        enabled_order = sorted(enabled_order, key=lambda x: pr_map.get(x, enabled_order.index(x)))
                except Exception:
                    pass
                final_ids: list[str] = []
                for pid in enabled_order:
                    try:
                        meta = pmap.get(pid, {})
                        enabled = bool(meta.get('enabled', True)) if isinstance(meta, dict) else bool(meta) if isinstance(meta, bool) else True
                    except Exception:
                        enabled = True
                    if enabled:
                        final_ids.append(pid)
                # Build filtered dir and re-discover
                try:
                    enabled_dir = _prepare_enabled_acasl_dir(self.api_dir, cfg, self.workspace_root, set(available_ids), {pid: id_to_folder.get(pid, pid)})
                except Exception:
                    enabled_dir = self.api_dir
                filtered = _discover_plugins(enabled_dir)
                id_to_meta = {p['id']: p for p in filtered if isinstance(p, dict) and 'id' in p}
                available_ids = list(id_to_meta.keys())
                try:
                    self.log.emit(f"🧩 ACASL: {len([pid for pid in final_ids if pid in id_to_meta])} plugin(s) activé(s) sur {len(available_ids)} détecté(s)")
                except Exception:
                    pass
                # Run
                report = {"status": "ok", "plugins": []}
                ctx = ACASLContext(self.gui, self.artifacts)
                try:
                    self.log.emit("🚀 ACASL: post‑compilation démarrée…")
                except Exception:
                    pass
                try:
                    for idx, pid in enumerate(final_ids):
                        try:
                            self.log.emit(f"⏫ Priorité {idx} pour {pid}")
                        except Exception:
                            pass
                except Exception:
                    pass
                for pid in final_ids:
                    meta = id_to_meta.get(pid)
                    if not meta:
                        continue
                    if ctx.is_canceled():
                        try:
                            self.log.emit("ACASL annulé (closing flag).")
                        except Exception:
                            pass
                        report["status"] = "canceled"
                        break
                    folder = meta.get('folder') or pid
                    init_path = (enabled_dir / str(folder) / '__init__.py')
                    if not init_path.exists():
                        try:
                            self.log.emit(f"ACASL plugin '{pid}' introuvable (init).")
                        except Exception:
                            pass
                        report["plugins"].append({
                            "id": pid,
                            "name": meta.get('name') or pid,
                            "version": meta.get('version', ''),
                            "ok": False,
                            "error": "init.py missing"
                        })
                        continue
                    import time as _time
                    start_ms = _time.monotonic()
                    try:
                        self.log.emit(f"• ACASL → {meta.get('name') or pid}")
                    except Exception:
                        pass
                    ok = False
                    err_msg = None
                    duration_ms = 0.0
                    pkg_name = f"ACASL.{folder}"
                    try:
                        spec = importlib.util.spec_from_file_location(pkg_name, init_path)
                        if spec is None or spec.loader is None:
                            raise RuntimeError("spec loader missing")
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[pkg_name] = mod
                        try:
                            spec.loader.exec_module(mod)
                        except Exception as _imp_e:
                            try:
                                del sys.modules[pkg_name]
                            except Exception:
                                pass
                            raise _imp_e
                        # Strict signature
                        if not bool(getattr(mod, 'ACASL_PLUGIN', False)):
                            raise RuntimeError("signature ACASL_PLUGIN manquante ou False")
                        mid = str(getattr(mod, 'ACASL_ID', '') or '').strip()
                        if not mid or mid != pid:
                            raise RuntimeError("ACASL_ID manquante ou incohérente")
                        mdesc = str(getattr(mod, 'ACASL_DESCRIPTION', '') or '').strip()
                        if not mdesc:
                            raise RuntimeError("ACASL_DESCRIPTION manquante")
                        run = getattr(mod, 'acasl_run', None)
                        if not callable(run):
                            raise RuntimeError("acasl_run callable manquante")
                        if self.plugin_timeout > 0:
                            result_holder = {"err": None}
                            def _call():
                                try:
                                    run(ctx)
                                except Exception as e:
                                    result_holder["err"] = e
                            th = threading.Thread(target=_call, name=f"ACASL-{pid}", daemon=True)
                            th.start()
                            th.join(self.plugin_timeout)
                            if th.is_alive():
                                err_msg = f"timeout après {self.plugin_timeout:.1f}s"
                            else:
                                if result_holder["err"] is None:
                                    ok = True
                                else:
                                    err_msg = str(result_holder["err"]) or repr(result_holder["err"])
                        else:
                            run(ctx)
                            ok = True
                    except Exception as e:
                        err_msg = str(e)
                    finally:
                        try:
                            duration_ms = (_time.monotonic() - start_ms) * 1000.0
                        except Exception:
                            duration_ms = 0.0
                    if ok:
                        report["plugins"].append({
                            "id": pid,
                            "name": meta.get('name') or pid,
                            "version": meta.get('version', ''),
                            "ok": True,
                            "duration_ms": duration_ms
                        })
                    else:
                        try:
                            self.log.emit(f"ACASL plugin '{pid}' a échoué: {err_msg}")
                        except Exception:
                            pass
                        report["plugins"].append({
                            "id": pid,
                            "name": meta.get('name') or pid,
                            "version": meta.get('version', ''),
                            "ok": False,
                            "error": err_msg or "unknown error",
                            "duration_ms": duration_ms
                        })
                try:
                    if report.get("status") != "canceled":
                        self.log.emit("✅ ACASL: post‑compilation terminée.")
                except Exception:
                    pass
                self.finished.emit(report)
            except Exception as e:
                try:
                    self.log.emit(f"⚠️ ACASL worker error: {e}")
                except Exception:
                    pass
                self.finished.emit(None)


if QObject is not None and Signal is not None:
    class _ACASLUiBridge(QObject):
        def __init__(self, gui, finished_cb, thread) -> None:
            super().__init__()
            self._gui = gui
            self._finished_cb = finished_cb
            self._thread = thread
        @Slot(str)
        def on_log(self, s: str) -> None:
            try:
                if hasattr(self._gui, 'log') and self._gui.log:
                    self._gui.log.append(s)
            except Exception:
                pass
        @Slot(object)
        def on_finished(self, rep) -> None:
            try:
                try:
                    tmr = getattr(self._gui, '_acasl_soft_timer', None)
                    if tmr:
                        tmr.stop()
                except Exception:
                    pass
                # Close any pending non-modal soft-timeout box
                try:
                    box = getattr(self._gui, '_acasl_soft_box', None)
                    if box:
                        try:
                            box.done(0)
                        except Exception:
                            try:
                                box.close()
                            except Exception:
                                pass
                        try:
                            setattr(self._gui, '_acasl_soft_box', None)
                        except Exception:
                            pass
                except Exception:
                    pass
                if callable(self._finished_cb):
                    from PySide6.QtCore import QTimer as _QT
                    try:
                        _QT.singleShot(0, lambda: self._finished_cb(rep))
                    except Exception:
                        try:
                            self._finished_cb(rep)
                        except Exception:
                            pass
                # Also invoke engine's on_success to open output folder if not done yet
                try:
                    from PySide6.QtCore import QTimer as _QT2
                    _QT2.singleShot(0, lambda: _acasl_try_open_engine_output(self._gui))
                except Exception:
                    try:
                        _acasl_try_open_engine_output(self._gui)
                    except Exception:
                        pass
            finally:
                try:
                    if hasattr(self._thread, 'isRunning') and self._thread.isRunning():
                        self._thread.quit()
                except Exception:
                    pass

def _discover_plugins(base_dir: Optional[Path] = None) -> list[dict]:
    """Discover ACASL plugins from a directory (default: API/ at project root) with metadata.
    Robust discovery avoids executing plugin code; metadata is parsed from __init__.py.
    A valid plugin must declare:
      - ACASL_PLUGIN = True
      - ACASL_ID (str), ACASL_DESCRIPTION (str)
      - acasl_run symbol present (def or assignment)
    Returns a list of dicts: {id, name, version, description, folder}
    """
    out: list[dict] = []
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent / 'API'
    if not base_dir.is_dir():
        return out
    seen_ids: set[str] = set()
    for entry in sorted(base_dir.iterdir()):
        try:
            if not entry.is_dir():
                continue
            init_path = entry / '__init__.py'
            if not init_path.is_file():
                continue
            meta = _extract_acasl_meta_from_text(init_path)
            if not meta:
                continue
            pid = str(meta.get('id') or '').strip()
            if not pid or pid in seen_ids:
                # Skip duplicates, keep first occurrence deterministically
                continue
            seen_ids.add(pid)
            out.append({
                'id': pid,
                'name': (meta.get('name') or entry.name).strip() or entry.name,
                'version': (meta.get('version') or '').strip(),
                'description': (meta.get('description') or '').strip(),
                'author': (meta.get('author') or '').strip(),
                'created': (meta.get('created') or '').strip(),
                'license': (meta.get('license') or '').strip(),
                'compatibility': meta.get('compatibility') or [],
                'tags': meta.get('tags') or [],
                'folder': entry.name,
            })
        except Exception:
            continue
    return out


def run_post_compile_async(gui, artifacts: List[str], finished_cb: Optional[Callable[[dict], None]] = None) -> None:
    """Run ACASL plugins asynchronously to avoid blocking the UI.
    - Loads configuration (acasl.*) to determine enabled plugins and their order
    - Discovers ACASL packages from API/ (signature ACASL_PLUGIN=True required)
    - Executes enabled plugins in configured order
    """
    global _ACASL_THREAD
    if _ACASL_THREAD and _ACASL_THREAD.is_alive():
        try:
            if hasattr(gui, 'log') and gui.log:
                gui.log.append("⚠️ ACASL déjà en cours, nouvelle exécution ignorée.")
        except Exception:
            pass
        return

    # Context & workspace
    # Save artifacts reference on GUI for universal discovery (used by engine_sdk.utils.discover_output_candidates)
    try:
        setattr(gui, '_last_artifacts', list(artifacts) if artifacts else [])
    except Exception:
        pass
    ctx = ACASLContext(gui, artifacts)
    try:
        workspace_root = Path(getattr(gui, 'workspace_dir', os.getcwd()) or os.getcwd()).resolve()
    except Exception:
        workspace_root = Path(os.getcwd())

    # Discover available ACASL plugin functions
    plugins_all = _discover_plugins()  # list of metadata dicts
    # Map plugin id -> metadata
    id_to_meta: dict[str, dict] = {p['id']: p for p in plugins_all if isinstance(p, dict) and 'id' in p}
    id_to_folder: dict[str, str] = {p['id']: p.get('folder') for p in plugins_all if isinstance(p, dict) and 'id' in p}

    # Load configuration and compute enabled order
    repo_root = Path(__file__).resolve().parents[1]
    api_dir = repo_root / 'API'
    available_ids: list[str] = list(id_to_meta.keys())
    cfg, _cfg_path, _action = _load_or_init_acasl_config(workspace_root, available_ids)
    pmap = cfg.get('plugins', {}) if isinstance(cfg, dict) else {}
    order = cfg.get('plugin_order', []) if isinstance(cfg, dict) else []
    # Resolve per-plugin soft timeout (<=0 means unlimited)
    try:
        opt = cfg.get('options', {}) if isinstance(cfg, dict) else {}
        cfg_timeout = float(opt.get('plugin_timeout_s', 0.0)) if isinstance(opt, dict) else 0.0
    except Exception:
        cfg_timeout = 0.0
    try:
        import os as _os
        env_timeout = float(_os.environ.get('PYCOMPILER_ACASL_PLUGIN_TIMEOUT', '0'))
    except Exception:
        env_timeout = 0.0
    plugin_timeout: float = cfg_timeout if cfg_timeout != 0.0 else env_timeout
    if not plugin_timeout or plugin_timeout <= 0:
        plugin_timeout = 0.0

    # Qt worker path (BCASL-like)
    if QThread is not None and '_ACASLWorker' in globals():
        thread = QThread()
        worker = _ACASLWorker(gui, workspace_root, api_dir, cfg, plugin_timeout, artifacts)  # type: ignore[name-defined]
        # Keep references on gui to avoid premature deletion
        try:
            gui._acasl_thread = thread
            gui._acasl_worker = worker
        except Exception:
            pass
        # Route logs and finish through a GUI-thread bridge
        bridge = _ACASLUiBridge(gui, finished_cb, thread)
        try:
            gui._acasl_ui_bridge = bridge
        except Exception:
            pass
        if hasattr(gui, 'log') and gui.log:
            worker.log.connect(bridge.on_log)
        worker.finished.connect(bridge.on_finished)
        worker.finished.connect(worker.deleteLater)
        def _clear_refs():
            try:
                if getattr(gui, '_acasl_thread', None) is thread:
                    gui._acasl_thread = None
                if getattr(gui, '_acasl_worker', None) is worker:
                    gui._acasl_worker = None
                if hasattr(gui, '_acasl_soft_timer'):
                    try:
                        t = gui._acasl_soft_timer
                        if t:
                            t.stop()
                    except Exception:
                        pass
                    gui._acasl_soft_timer = None
                if hasattr(gui, '_acasl_ui_bridge'):
                    try:
                        b = gui._acasl_ui_bridge
                        if b:
                            b.deleteLater()
                    except Exception:
                        pass
                    gui._acasl_ui_bridge = None
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
        # Soft timeout prompt if unlimited
        try:
            if plugin_timeout <= 0 and QTimer is not None:
                soft_s = 30.0
                try:
                    opt2 = cfg.get('options', {}) if isinstance(cfg, dict) else {}
                    soft_s = float(opt2.get('phase_soft_timeout_s', 30.0))
                except Exception:
                    pass
                tmr = QTimer(gui)
                tmr.setSingleShot(True)
                def _on_soft():
                    try:
                        if getattr(gui, '_acasl_thread', None) is thread and thread.isRunning() and not getattr(gui, '_closing', False):
                            try:
                                from PySide6.QtCore import Qt as _Qt
                            except Exception:
                                _Qt = None
                            box = QMessageBox(gui)
                            box.setIcon(QMessageBox.Question)
                            box.setWindowTitle("ACASL trop long")
                            box.setText(f"Les plugins ACASL s'exécutent toujours après {soft_s:.0f}s.\nVoulez-vous les arrêter et ouvrir les artifacts ?")
                            yes_btn = box.addButton(QMessageBox.Yes)
                            no_btn = box.addButton(QMessageBox.No)
                            try:
                                box.setDefaultButton(no_btn)
                            except Exception:
                                pass
                            try:
                                if _Qt is not None:
                                    box.setWindowModality(_Qt.NonModal)
                            except Exception:
                                pass
                            def _on_click(btn):
                                try:
                                    if btn is yes_btn:
                                        try:
                                            ensure_acasl_thread_stopped(gui)
                                        except Exception:
                                            pass
                                        if callable(finished_cb):
                                            try:
                                                from PySide6.QtCore import QTimer as _QT3
                                                _QT3.singleShot(0, lambda: finished_cb(None))
                                            except Exception:
                                                try:
                                                    finished_cb(None)
                                                except Exception:
                                                    pass
                                except Exception:
                                    pass
                                finally:
                                    try:
                                        box.done(0)
                                    except Exception:
                                        pass
                            try:
                                box.buttonClicked.connect(_on_click)
                            except Exception:
                                pass
                            try:
                                setattr(gui, '_acasl_soft_box', box)
                            except Exception:
                                pass
                            box.show()
                    except Exception:
                        pass
                tmr.timeout.connect(_on_soft)
                tmr.start(int(soft_s * 1000))
                gui._acasl_soft_timer = tmr
        except Exception:
            pass
        return
    # Normalize order: keep only available ids, append missing ones
    enabled_order: list[str] = [pid for pid in order if pid in available_ids]
    for pid in available_ids:
        if pid not in enabled_order:
            enabled = True
            try:
                meta = pmap.get(pid, {})
                enabled = bool(meta.get('enabled', True)) if isinstance(meta, dict) else bool(meta) if isinstance(meta, bool) else True
            except Exception:
                enabled = True
            if enabled:
                enabled_order.append(pid)
    # Respect explicit 'priority' hints from config if present (like BCASL)
    try:
        pr_map: dict[str, int] = {}
        if isinstance(pmap, dict):
            for k, v in pmap.items():
                if isinstance(v, dict) and 'priority' in v:
                    try:
                        pr_map[str(k)] = int(v.get('priority', 0))
                    except Exception:
                        pass
        if pr_map:
            enabled_order = sorted(enabled_order, key=lambda x: pr_map.get(x, enabled_order.index(x)))
    except Exception:
        pass
    # Filter only enabled per config
    final_ids: list[str] = []
    for pid in enabled_order:
        try:
            meta = pmap.get(pid, {})
            enabled = bool(meta.get('enabled', True)) if isinstance(meta, dict) else bool(meta) if isinstance(meta, bool) else True
        except Exception:
            enabled = True
        if enabled:
            final_ids.append(pid)

    # Build filtered directory with only enabled plugins and (re)discover from it like BCASL
    enabled_dir = api_dir
    try:
        enabled_dir = _prepare_enabled_acasl_dir(api_dir, cfg, workspace_root, set(available_ids), {pid: id_to_folder.get(pid, pid)})
        filtered = _discover_plugins(enabled_dir)
        id_to_meta = {p['id']: p for p in filtered if isinstance(p, dict) and 'id' in p}
        available_ids = list(id_to_meta.keys())
    except Exception:
        enabled_dir = api_dir
    # Build final plugin function list preserving order
    plugins: list[dict] = [id_to_meta[pid] for pid in final_ids if pid in id_to_meta]
    try:
        if hasattr(gui, 'log') and gui.log:
            gui.log.append(f"🧩 ACASL: {len(plugins)} plugin(s) activé(s) sur {len(available_ids)} détecté(s)")
    except Exception:
        pass

    def _runner():
        report = {"status": "ok", "plugins": []}
        try:
            ctx.log_info("🚀 ACASL: post‑compilation démarrée…")
            # Log priorities similarly to BCASL when available
            try:
                for idx, pid in enumerate(final_ids):
                    ctx.log_info(f"⏫ Priorité {idx} pour {pid}")
            except Exception:
                pass
            for pid in final_ids:
                meta = id_to_meta.get(pid)
                if not meta:
                    continue
                if ctx.is_canceled():
                    ctx.log_warn("ACASL annulé (closing flag).")
                    report["status"] = "canceled"
                    break
                # Lazy import plugin module from enabled_dir and run
                folder = meta.get('folder') or pid
                init_path = (enabled_dir / str(folder) / '__init__.py')
                if not init_path.exists():
                    ctx.log_error(f"ACASL plugin '{pid}' introuvable (init).")
                    report["plugins"].append({
                        "id": pid,
                        "name": meta.get('name') or pid,
                        "version": meta.get('version', ''),
                        "ok": False,
                        "error": "init.py missing"
                    })
                    continue
                import time as _time
                start_ms = _time.monotonic()
                disp = f"{meta.get('name') or pid}"
                ctx.log_info(f"• ACASL → {disp}")
                ok = False
                err_msg = None
                duration_ms = 0.0
                pkg_name = f"ACASL.{folder}"
                try:
                    spec = importlib.util.spec_from_file_location(pkg_name, init_path)
                    if spec is None or spec.loader is None:
                        raise RuntimeError("spec loader missing")
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[pkg_name] = mod
                    try:
                        spec.loader.exec_module(mod)
                    except Exception as _imp_e:
                        # Cleanup partially loaded module
                        try:
                            del sys.modules[pkg_name]
                        except Exception:
                            pass
                        raise _imp_e
                    # Strict signature validation at runtime
                    if not bool(getattr(mod, 'ACASL_PLUGIN', False)):
                        raise RuntimeError("signature ACASL_PLUGIN manquante ou False")
                    mid = str(getattr(mod, 'ACASL_ID', '') or '').strip()
                    if not mid or mid != pid:
                        raise RuntimeError("ACASL_ID manquante ou incohérente")
                    mdesc = str(getattr(mod, 'ACASL_DESCRIPTION', '') or '').strip()
                    if not mdesc:
                        raise RuntimeError("ACASL_DESCRIPTION manquante")
                    run = getattr(mod, 'acasl_run', None)
                    if not callable(run):
                        raise RuntimeError("acasl_run callable manquante")
                    if plugin_timeout > 0:
                        result_holder = {"err": None}
                        def _call():
                            try:
                                run(ctx)
                            except Exception as e:
                                result_holder["err"] = e
                        th = threading.Thread(target=_call, name=f"ACASL-{pid}", daemon=True)
                        th.start()
                        th.join(plugin_timeout)
                        if th.is_alive():
                            err_msg = f"timeout après {plugin_timeout:.1f}s"
                        else:
                            if result_holder["err"] is None:
                                ok = True
                            else:
                                err_msg = str(result_holder["err"]) or repr(result_holder["err"])
                    else:
                        # No timeout: run inline
                        run(ctx)
                        ok = True
                except Exception as e:
                    err_msg = str(e)
                finally:
                    try:
                        duration_ms = ( _time.monotonic() - start_ms ) * 1000.0
                    except Exception:
                        duration_ms = 0.0
                if ok:
                    report["plugins"].append({
                        "id": pid,
                        "name": meta.get('name') or pid,
                        "version": meta.get('version', ''),
                        "ok": True,
                        "duration_ms": duration_ms
                    })
                else:
                    ctx.log_error(f"ACASL plugin '{pid}' a échoué: {err_msg}")
                    report["plugins"].append({
                        "id": pid,
                        "name": meta.get('name') or pid,
                        "version": meta.get('version', ''),
                        "ok": False,
                        "error": err_msg or "unknown error",
                        "duration_ms": duration_ms
                    })
            if report.get("status") != "canceled":
                ctx.log_info("✅ ACASL: post‑compilation terminée.")
        finally:
            # Schedule opening of engine output via GUI thread after ACASL
            try:
                ctx._post_ui(lambda: _acasl_try_open_engine_output(ctx.gui))
            except Exception:
                pass
            if callable(finished_cb):
                try:
                    ctx._post_ui(lambda rep=report: finished_cb(rep))
                except Exception:
                    pass

    t = threading.Thread(target=_runner, name="ACASL-Thread", daemon=True)
    _ACASL_THREAD = t
    t.start()


def ensure_acasl_thread_stopped(gui=None) -> None:
    """Best-effort, non-blocking stop: mark closing flag and request background threads to exit.
    Avoids blocking waits or force-terminating threads to prevent UI freezes/crashes."""
    global _ACASL_THREAD
    try:
        if gui is not None:
            setattr(gui, '_closing', True)
    except Exception:
        pass
    # Prefer stopping Qt worker thread without blocking the UI
    try:
        if gui is not None:
            t = getattr(gui, '_acasl_thread', None)
            if t is not None and hasattr(t, 'isRunning'):
                try:
                    if t.isRunning():
                        try:
                            t.quit()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    gui._acasl_thread = None
                    gui._acasl_worker = None
                except Exception:
                    pass
    except Exception:
        pass
    # Fallback: python thread (do not block the UI with join)
    t2 = _ACASL_THREAD
    if t2 and t2.is_alive():
        try:
            # Best-effort: let it finish on its own
            pass
        except Exception:
            pass
    _ACASL_THREAD = None


def resolve_acasl_timeout(self) -> float:
    """Compute effective ACASL plugin timeout (seconds) from config/env.
    <= 0 implies unlimited (0.0 returned).
    Sources: options.plugin_timeout_s in acasl.* or env PYCOMPILER_ACASL_PLUGIN_TIMEOUT
    """
    try:
        if not getattr(self, 'workspace_dir', None):
            return 0.0
        workspace_root = Path(self.workspace_dir).resolve()
        cfg, _p, _a = _load_or_init_acasl_config(workspace_root, [])
        import os as _os
        try:
            env_timeout = float(_os.environ.get("PYCOMPILER_ACASL_PLUGIN_TIMEOUT", "0"))
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


# Minimal UI dialog to configure ACASL plugins (enable/order) similar to BCASL
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QAbstractItemView, QMessageBox, QLabel, QPlainTextEdit, QWidget
)
from PySide6.QtCore import Qt
import json

# --- ACASL config helpers (support acasl.*; auto-create if missing) ---
from typing import Tuple
# Optional parsers (module-level, reused by raw editor)
try:
    import tomllib as _toml  # Python 3.11+
except Exception:  # pragma: no cover
    try:
        import tomli as _toml  # type: ignore
    except Exception:
        _toml = None  # type: ignore
try:
    import yaml as _yaml  # type: ignore
except Exception:  # pragma: no cover
    _yaml = None  # type: ignore

def _config_candidates(root: Path) -> list[Path]:
    names = [
        "acasl.json", "acasl.yaml", "acasl.yml", "acasl.toml", "acasl.ini", "acasl.cfg",
        ".acasl.json", ".acasl.yaml", ".acasl.yml", ".acasl.toml", ".acasl.ini", ".acasl.cfg",
    ]
    out = []
    for n in names:
        p = root / n
        if p.exists() and p.is_file():
            out.append(p)
    return out

def _read_acasl_cfg(path: Path) -> dict:
    suf = path.suffix.lower()
    try:
        txt = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    try:
        if suf == ".json":
            return json.loads(txt) or {}
        if suf in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore
                data = yaml.safe_load(txt)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        if suf == ".toml":
            try:
                import tomllib as toml  # py311+
            except Exception:
                try:
                    import tomli as toml  # type: ignore
                except Exception:
                    toml = None  # type: ignore
            if toml:
                try:
                    return toml.loads(txt) or {}
                except Exception:
                    return {}
            return {}
        if suf in (".ini", ".cfg"):
            try:
                import configparser as _cp
                cp = _cp.ConfigParser()
                cp.read_string(txt)
                cfg: dict = {}
                # plugins section: key -> enabled
                if cp.has_section("plugins"):
                    plugins = {}
                    for k, v in cp.items("plugins"):
                        val = str(v).strip().lower() in ("1", "true", "yes", "on")
                        plugins[k] = {"enabled": val}
                    if plugins:
                        cfg["plugins"] = plugins
                # general: plugin_order as comma list
                po = None
                if cp.has_option("general", "plugin_order"):
                    raw = cp.get("general", "plugin_order")
                    po = [x.strip() for x in raw.split(",") if x.strip()]
                if po:
                    cfg["plugin_order"] = po
                return cfg
            except Exception:
                return {}
    except Exception:
        return {}
    return {}

def _default_acasl_cfg(plugin_ids: list[str]) -> dict:
    from datetime import datetime
    return {
        "plugins": {pid: {"enabled": True, "priority": i} for i, pid in enumerate(plugin_ids)},
        "plugin_order": list(plugin_ids),
        "options": {"plugin_timeout_s": 0.0},
        "_meta": {"schema": 1, "generated": True, "generated_at": datetime.utcnow().isoformat() + "Z"},
    }


def _sanitize_acasl_cfg(plugin_ids: list[str], cfg_in: Any) -> tuple[dict, bool]:
    """Normalize an ACASL config against current plugin ids.
    - Drop unknown plugins
    - Add missing plugins (enabled=True)
    - Rebuild plugin_order and priority to be contiguous and deterministic
    - Preserve prior 'enabled' flags when possible
    Returns (normalized_cfg, changed)
    """
    changed = False
    cfg: dict = cfg_in if isinstance(cfg_in, dict) else {}
    plugins = cfg.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        changed = True
    # Filter only known plugin ids
    known = set(plugin_ids)
    filtered: dict = {}
    for pid, meta in plugins.items():
        if pid in known:
            if isinstance(meta, dict):
                en = bool(meta.get("enabled", True))
            else:
                en = bool(meta)
                changed = True
            filtered[pid] = {"enabled": en}
        else:
            changed = True
    plugins = filtered
    # Determine initial order
    order = cfg.get("plugin_order")
    if isinstance(order, list):
        order = [pid for pid in order if pid in known]
    else:
        # Try order by existing 'priority' if present, else fallback to plugin_ids order
        try:
            order = sorted(plugins.keys(), key=lambda k: int((plugins.get(k) or {}).get("priority", 0)))
        except Exception:
            order = [pid for pid in plugin_ids if pid in plugins]
        changed = True
    # Append newly discovered plugins at the end in deterministic order
    for pid in plugin_ids:
        if pid not in order:
            order.append(pid)
            if pid not in plugins:
                plugins[pid] = {"enabled": True}
            changed = True
    # Rebuild contiguous priorities from order
    for i, pid in enumerate(order):
        meta = plugins.get(pid) or {}
        if meta.get("priority") != i:
            meta["priority"] = i
            plugins[pid] = meta
            changed = True
    out = dict(cfg)
    out["plugins"] = plugins
    out["plugin_order"] = order
    # Ensure meta
    meta = out.get("_meta")
    if not isinstance(meta, dict) or meta.get("schema") != 1:
        out["_meta"] = {"schema": 1}
        changed = True
    # Ensure options with default timeout
    opts = out.get("options")
    if not isinstance(opts, dict):
        out["options"] = {"plugin_timeout_s": 0.0}
        changed = True
    else:
        if "plugin_timeout_s" not in opts:
            opts["plugin_timeout_s"] = 0.0
            out["options"] = opts
            changed = True
    return out, changed

def _write_acasl_cfg(path: Path, cfg: dict) -> Path:
    suf = path.suffix.lower()
    try:
        if suf == ".json":
            ok = _write_json_atomic(path, cfg)
            if not ok:
                path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return path
        if suf in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore
                path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
                return path
            except Exception:
                pass  # fallback to JSON
        if suf in (".ini", ".cfg"):
            try:
                import configparser as _cp
                cp = _cp.ConfigParser()
                # plugins
                cp.add_section("plugins")
                for pid, meta in (cfg.get("plugins", {}) or {}).items():
                    en = bool(meta.get("enabled", True)) if isinstance(meta, dict) else bool(meta)
                    cp.set("plugins", pid, "1" if en else "0")
                # general
                cp.add_section("general")
                order = cfg.get("plugin_order", []) or []
                cp.set("general", "plugin_order", ",".join(order))
                with path.open("w", encoding="utf-8") as f:
                    cp.write(f)
                return path
            except Exception:
                pass  # fallback to JSON
        # Fallback: write JSON next to requested file name as acasl.json
        jpath = path.parent / "acasl.json"
        ok = _write_json_atomic(jpath, cfg)
        if not ok:
            jpath.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return jpath
    except Exception as e:
        raise


def _prepare_enabled_acasl_dir(api_dir: Path, cfg: dict, workspace_root: Path, valid_ids: set[str], id_to_folder: dict[str, str]) -> Path:
    """Create a filtered directory with only enabled ACASL plugin packages.
    Similar to BCASL: uses symlinks when possible, otherwise copies.
    Filters by plugin IDs present in valid_ids and enabled in cfg["plugins"].
    Returns the path to the filtered directory, or api_dir on failure.
    """
    try:
        target = workspace_root / ".pycompiler" / "api_enabled"
        try:
            shutil.rmtree(target, ignore_errors=True)
        except Exception:
            pass
        os.makedirs(target, exist_ok=True)
        pmap = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
        for pid in sorted(valid_ids):
            try:
                meta = pmap.get(pid, {})
                enabled = bool(meta.get("enabled", True)) if isinstance(meta, dict) else bool(meta) if isinstance(meta, bool) else True
            except Exception:
                enabled = True
            if not enabled:
                continue
            folder = id_to_folder.get(pid)
            if not folder:
                continue
            src = api_dir / folder
            if not (src.is_dir() and (src / "__init__.py").exists() and _has_acasl_marker(src)):
                continue
            dst = target / folder
            try:
                os.symlink(src, dst, target_is_directory=True)
            except Exception:
                try:
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                except Exception:
                    pass
        return target
    except Exception:
        return api_dir


def _load_or_init_acasl_config(workspace_root: Path, plugin_ids: list[str]) -> Tuple[dict, Path, Optional[str]]:
    """Load existing acasl.* or create a default acasl.json.
    Returns (cfg, path, action) where action is 'created', 'migrated', or None.
    """
    # Try any existing acasl.* with precedence
    found = _config_candidates(workspace_root)
    if found:
        path = found[0]
        cfg = _read_acasl_cfg(path)
        if not isinstance(cfg, dict):
            cfg = {}
        # Sanitize/migrate in place if needed
        cfg_norm, changed = _sanitize_acasl_cfg(plugin_ids, cfg)
        if changed:
            _write_acasl_cfg(path, cfg_norm)
            return cfg_norm, path, "migrated"
        return cfg_norm, path, None
    # Create default acasl.json
    cfg = _default_acasl_cfg(plugin_ids)
    path = workspace_root / "acasl.json"
    _write_acasl_cfg(path, cfg)
    return cfg, path, "created"


def open_acasl_loader_dialog(self) -> None:
    try:
        if not getattr(self, 'workspace_dir', None):
            QMessageBox.warning(self, "ACASL", "Sélectionnez d'abord un dossier workspace.\nPlease select a workspace folder first.")
            return
        workspace_root = Path(self.workspace_dir).resolve()
        repo_root = Path(__file__).resolve().parents[1]
        api_dir = repo_root / "API"
        if not api_dir.exists():
            QMessageBox.information(self, "ACASL", "Aucun répertoire API trouvé dans le projet.\nNo API directory found in the project.")
            return
        # Discover plugins: Python packages in API (folder with __init__.py)
        # Build UI list from discovered metadata for better display
        metas = _discover_plugins()
        plugin_ids = []
        meta_by_id = {}
        for meta in metas:
            pid = meta.get('id')
            if not pid:
                continue
            plugin_ids.append(pid)
            meta_by_id[pid] = meta
        if not plugin_ids:
            QMessageBox.information(self, "ACASL", "Aucun plugin ACASL détecté dans API.\nNo ACASL plugin detected in API.")
            return
        # Load existing config (supports acasl.*). Auto-create if missing.
        cfg, cfg_path, action = _load_or_init_acasl_config(workspace_root, plugin_ids)
        plugins_cfg = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
        # Log creation/migration
        try:
            if action == "created" and hasattr(self, 'log') and self.log is not None:
                self.log.append(f"🆕 Configuration ACASL créée automatiquement: {cfg_path.name}")
            elif action == "migrated" and hasattr(self, 'log') and self.log is not None:
                self.log.append(f"🔄 Configuration ACASL mise à jour: {cfg_path.name}")
        except Exception:
            pass
        # Build dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("ACASL Loader")
        layout = QVBoxLayout(dlg)
        info = QLabel("Activez/désactivez les plugins ACASL et définissez leur ordre d'exécution (haut = d'abord).\nEnable/disable ACASL plugins and set their order (top = first).")
        layout.addWidget(info)
        lst = QListWidget(dlg)
        lst.setSelectionMode(QAbstractItemView.SingleSelection)
        lst.setDragDropMode(QAbstractItemView.InternalMove)
        # Determine initial order
        order = []
        try:
            order = cfg.get("plugin_order", []) if isinstance(cfg, dict) else []
            order = [pid for pid in order if pid in plugin_ids]
        except Exception:
            order = []
        remaining = [pid for pid in plugin_ids if pid not in order]
        ordered_ids = order + remaining
        for pid in ordered_ids:
            meta = meta_by_id.get(pid, {})
            label = pid
            try:
                disp = meta.get('name') or pid
                ver = meta.get('version') or ''
                if ver:
                    label = f"{disp} ({pid}) v{ver}"
                else:
                    label = f"{disp} ({pid})"
            except Exception:
                label = pid
            item = QListWidgetItem(label)
            # tooltip with description and extended metadata
            try:
                lines = []
                desc = meta.get('description') or ''
                if desc:
                    lines.append(desc)
                auth = meta.get('author') or ''
                if auth:
                    lines.append(f"Auteur: {auth}")
                created = meta.get('created') or ''
                if created:
                    lines.append(f"Créé: {created}")
                lic = meta.get('license') or ''
                if lic:
                    lines.append(f"Licence: {lic}")
                comp = meta.get('compatibility') or []
                if isinstance(comp, list) and comp:
                    lines.append("Compatibilité: " + ", ".join([str(x) for x in comp]))
                tags = meta.get('tags') or []
                if isinstance(tags, list) and tags:
                    lines.append("Tags: " + ", ".join([str(x) for x in tags]))
                if lines:
                    item.setToolTip("\n".join(lines))
            except Exception:
                pass
            enabled = True
            try:
                pentry = plugins_cfg.get(pid, {})
                if isinstance(pentry, dict):
                    enabled = bool(pentry.get("enabled", True))
                elif isinstance(pentry, bool):
                    enabled = pentry
            except Exception:
                enabled = True
            item.setData(0x0100, pid)  # store id in user role
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
            lst.addItem(item)
        layout.addWidget(lst)
        # Raw config editor (acasl.*) toggle and panel
        btn_toggle_raw = QPushButton("Modifier la configuration brute (acasl.*) / Edit raw config (acasl.*)")
        layout.addWidget(btn_toggle_raw)
        raw_box = QWidget(dlg)
        raw_lay = QVBoxLayout(raw_box)
        raw_hint = QLabel("Vous pouvez modifier la configuration directement. Elle sera enregistrée dans {} à la racine du workspace.\nYou can edit the configuration directly. It will be saved to {} at the workspace root.")
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
                "acasl.json", ".acasl.json", "acasl.yaml", ".acasl.yaml", "acasl.yml", ".acasl.yml",
                "acasl.toml", ".acasl.toml", "acasl.ini", ".acasl.ini", "acasl.cfg", ".acasl.cfg"
            ]:
                p = workspace_root / name
                if p.exists() and p.is_file():
                    existing_path = p
                    break
            if existing_path:
                raw_text = existing_path.read_text(encoding="utf-8", errors="ignore")
            else:
                import json as _json
                raw_text = _json.dumps(cfg if isinstance(cfg, dict) else {}, ensure_ascii=False, indent=2)
        except Exception:
            import json as _json
            raw_text = _json.dumps(cfg if isinstance(cfg, dict) else {}, ensure_ascii=False, indent=2)
        raw_editor.setPlainText(raw_text)
        # Determine target path (existing config file or default to acasl.json) and update labels accordingly
        try:
            existing_name = existing_path.name if existing_path else None
        except Exception:
            existing_name = None
        target_path = existing_path if existing_path else (workspace_root / "acasl.json")
        try:
            target_name = target_path.name
        except Exception:
            target_name = "acasl.json"
        try:
            raw_hint.setText(raw_hint.text().format(target_name, target_name))
        except Exception:
            pass
        raw_lay.addWidget(raw_editor)
        # Action buttons for raw editor
        raw_btns = QHBoxLayout()
        btn_reload_raw = QPushButton("Recharger / Reload")
        btn_save_raw = QPushButton("Enregistrer brut / Save raw")
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
                    import json as _json
                    txt = _json.dumps(cfg if isinstance(cfg, dict) else {}, ensure_ascii=False, indent=2)
                raw_editor.setPlainText(txt)
            except Exception as e:
                QMessageBox.warning(dlg, "Attention / Warning", f"Échec du rechargement / Reload failed: {e}")
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
            import json as _json
            try:
                if fmt == "json":
                    data = _json.loads(txt)
                    out = _json.dumps(data, ensure_ascii=False, indent=2) + "\n"
                elif fmt in ("yaml", "yml"):
                    if _yaml is not None:
                        try:
                            data = _yaml.safe_load(txt)
                            if data is None:
                                data = {}
                            # write back as YAML
                            out = _yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
                        except Exception:
                            # Attempt JSON fallback -> save as acasl.json
                            try:
                                data = _json.loads(txt)
                                new_target = workspace_root / "acasl.json"
                                new_target.write_text(_json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                                target_path = new_target
                                target_name = new_target.name
                                if hasattr(self, 'log') and self.log is not None:
                                    self.log.append("⚠️ YAML invalide; contenu JSON détecté -> sauvegarde dans acasl.json")
                                return
                            except Exception as conv_err:
                                raise conv_err
                    else:
                        # No YAML lib: attempt JSON fallback; otherwise write as-is
                        try:
                            data = _json.loads(txt)
                            new_target = workspace_root / "acasl.json"
                            new_target.write_text(_json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                            target_path = new_target
                            target_name = new_target.name
                            if hasattr(self, 'log') and self.log is not None:
                                self.log.append("ℹ️ Librairie YAML absente; contenu JSON détecté -> sauvegarde dans acasl.json")
                            return
                        except Exception:
                            out = txt if txt.endswith("\n") else (txt + "\n")
                elif fmt == "toml":
                    if _toml is not None:
                        try:
                            _ = _toml.loads(txt)
                            out = txt if txt.endswith("\n") else (txt + "\n")
                        except Exception:
                            # Attempt JSON fallback -> save as acasl.json
                            try:
                                data = _json.loads(txt)
                                new_target = workspace_root / "acasl.json"
                                new_target.write_text(_json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                                target_path = new_target
                                target_name = new_target.name
                                if hasattr(self, 'log') and self.log is not None:
                                    self.log.append("⚠️ TOML invalide; contenu JSON détecté -> sauvegarde dans acasl.json")
                                return
                            except Exception as conv_err:
                                raise conv_err
                    else:
                        out = txt if txt.endswith("\n") else (txt + "\n")
                elif fmt in ("ini", "cfg"):
                    try:
                        import configparser as _cp
                        cp = _cp.ConfigParser()
                        cp.read_string(txt)
                        out = txt if txt.endswith("\n") else (txt + "\n")
                    except Exception:
                        # Attempt JSON fallback -> save as acasl.json
                        try:
                            data = _json.loads(txt)
                            new_target = workspace_root / "acasl.json"
                            new_target.write_text(_json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                            target_path = new_target
                            target_name = new_target.name
                            if hasattr(self, 'log') and self.log is not None:
                                self.log.append("⚠️ INI/CFG invalide; contenu JSON détecté -> sauvegarde dans acasl.json")
                            return
                        except Exception as conv_err:
                            raise conv_err
                else:
                    out = txt if txt.endswith("\n") else (txt + "\n")
            except Exception as e:
                QMessageBox.critical(dlg, "Erreur / Error", f"Contenu invalide / Invalid content for format {fmt.upper()}: {e}")
                return
            try:
                target_path.write_text(out, encoding="utf-8")
                if hasattr(self, 'log') and self.log is not None:
                    self.log.append(f"✅ Configuration brute enregistrée dans {target_name} (la boîte reste ouverte)")
            except Exception as e:
                QMessageBox.critical(dlg, "Erreur / Error", f"Échec d'écriture / Failed to write {target_name}: {e}")
        btn_save_raw.clicked.connect(_save_raw)
        layout.addWidget(raw_box)
        # Buttons
        btns = QHBoxLayout()
        btn_up = QPushButton("⬆️")
        btn_down = QPushButton("⬇️")
        btn_cancel = QPushButton("Annuler / Cancel")
        btn_save = QPushButton("Enregistrer / Save")
        def _move(delta: int):
            row = lst.currentRow()
            if row < 0:
                return
            new_row = max(0, min(lst.count() - 1, row + delta))
            if new_row == row:
                return
            it = lst.takeItem(row)
            lst.insertItem(new_row, it)
            lst.setCurrentRow(new_row)
        btn_up.clicked.connect(lambda: _move(-1))
        btn_down.clicked.connect(lambda: _move(1))
        btns.addWidget(btn_up)
        btns.addWidget(btn_down)
        btns.addStretch(1)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)
        def do_save():
            out_plugins = {}
            order_ids = []
            for i in range(lst.count()):
                it = lst.item(i)
                pid = it.data(0x0100) or it.text()
                en = (it.checkState() == Qt.Checked)
                out_plugins[str(pid)] = {"enabled": bool(en), "priority": i}
                order_ids.append(str(pid))
            cfg_out = dict(cfg) if isinstance(cfg, dict) else {}
            cfg_out["plugins"] = out_plugins
            cfg_out["plugin_order"] = order_ids
            try:
                cfg_norm, _ = _sanitize_acasl_cfg(plugin_ids, cfg_out)
                new_path = _write_acasl_cfg(cfg_path, cfg_norm)
                if hasattr(self, 'log') and self.log is not None:
                    self.log.append(f"✅ ACASL plugins enregistrés dans {new_path.name}")
                dlg.accept()
            except Exception as e:
                QMessageBox.critical(dlg, "Erreur / Error", f"Impossible d'écrire / Failed to write {cfg_path.name}: {e}")
        btn_save.clicked.connect(do_save)
        btn_cancel.clicked.connect(dlg.reject)
        try:
            dlg.setModal(False)
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
            # Keep a reference to avoid GC and ensure non-blocking behavior
            try:
                setattr(self, "_acasl_loader_dlg", dlg)
            except Exception:
                pass
            dlg.show()
        except Exception:
            try:
                dlg.show()
            except Exception:
                pass
    except Exception as e:
        try:
            if hasattr(self, 'log') and self.log:
                self.log.append(f"⚠️ ACASL UI error: {e}")
        except Exception:
            pass
