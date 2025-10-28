# SPDX-License-Identifier: GPL-3.0-only
"""
ACASL loader (simplifié, découverte via acasl_register uniquement)

Objectifs de simplification (parité avec BCASL):
- Config JSON uniquement (acasl.json ou .acasl.json)
- Découverte FORCÉE: packages dans Plugins/ UNIQUEMENT ayant __init__.py et exposant acasl_register(manager)
  Le manager temporaire collecte des objets plugins avec métadonnées et un runner (callable).
- Ordre: plugin_order depuis config sinon alphabétique
- UI minimale pour activer/désactiver et réordonner (pas d'éditeur brut multi-format)
- Async via QThread si QtCore dispo, sinon repli synchrone
- Journalisation concise dans gui.log si disponible
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Optional

# Qt (facultatif). Ne pas importer QtWidgets au niveau module pour compatibilité headless.
try:  # pragma: no cover
    from PySide6.QtCore import QObject, QThread, Signal, Slot
except Exception:  # pragma: no cover
    QObject = None  # type: ignore
    QThread = None  # type: ignore
    Signal = None  # type: ignore
    Slot = None  # type: ignore

# -----------------
# Contexte ACASL
# -----------------
class ACASLContext:
    def __init__(
        self, gui, artifacts: list[str], output_dir: Optional[str] = None
    ) -> None:
        self.gui = gui
        try:
            ws = getattr(gui, "workspace_dir", None)
            self.workspace_root = Path(ws if ws else os.getcwd()).resolve()
        except Exception:
            self.workspace_root = Path(os.getcwd()).resolve()
        self.artifacts = [str(Path(a)) for a in artifacts or []]
        self.output_dir = str(output_dir).strip() if output_dir else None
    # Logging helpers (post to GUI thread via Qt when available)
    def _post_ui(self, fn) -> None:
        try:
            if hasattr(self.gui, "_closing") and bool(getattr(self.gui, "_closing")):
                return
        except Exception:
            pass
        try:
            from PySide6.QtCore import QTimer  # type: ignore

            QTimer.singleShot(0, fn)
        except Exception:
            try:
                fn()
            except Exception:
                pass

    def log_info(self, msg: str) -> None:
        try:
            if hasattr(self.gui, "log") and self.gui.log:
                self._post_ui(lambda: self.gui.log.append(msg))
        except Exception:
            pass

    def log_warn(self, msg: str) -> None:
        self.log_info(f"⚠️ {msg}")

    def log_error(self, msg: str) -> None:
        self.log_info(f"❌ {msg}")

# -----------------
# Découverte plugins via acasl_register
# -----------------

class _ACASLTempManager:
    """Manager temporaire passé à acasl_register(manager) pour collecter les plugins.
    Attend un objet 'plugin' avec métadonnées et méthode d'exécution post-compilation.
    - Métadonnées supportées: plugin.meta.id/name/version/description OU attributs plugin.id/name/version/description
    - Méthode de run: on_post_compile(ctx) ou run(ctx) ou execute(ctx) ou acasl_run(ctx)
    """

    def __init__(self) -> None:
        self._plugins: list[Any] = []

    def add_plugin(self, plugin: Any) -> None:
        self._plugins.append(plugin)
    # Compat API (si certains plugins utilisent une autre méthode)
    def add_task(self, plugin: Any) -> None:  # alias permissif
        self.add_plugin(plugin)

def _extract_meta_from_plugin(plg: Any) -> Optional[dict[str, Any]]:
    def _get_attr_chain(obj: Any, chain: list[str]) -> Optional[Any]:
        for name in chain:
            try:
                obj = getattr(obj, name)
            except Exception:
                return None
        return obj
    try:
        pid = (
            _get_attr_chain(plg, ["meta", "id"])
            or getattr(plg, "id", None)
            or getattr(plg, "ID", None)
        )
        if not pid:
            # derive from class name
            try:
                pid = plg.__class__.__name__.lower()
            except Exception:
                return None
        name = (
            _get_attr_chain(plg, ["meta", "name"])
            or getattr(plg, "name", "")
            or str(pid)
        )
        version = (
            _get_attr_chain(plg, ["meta", "version"])
            or getattr(plg, "version", "")
            or ""
        )
        desc = (
            _get_attr_chain(plg, ["meta", "description"])
            or getattr(plg, "description", "")
            or ""
        )
        # Resolve runner
        runner = (
            getattr(plg, "on_post_compile", None)
            or getattr(plg, "run", None)
            or getattr(plg, "execute", None)
            or getattr(plg, "acasl_run", None)
        )
        if not callable(runner):
            return None
        return {
            "id": str(pid),
            "name": str(name) if name else str(pid),
            "version": str(version) if version else "",
            "description": str(desc) if desc else "",
            "plugin": plg,
            "runner": runner,
        }
    except Exception:
        return None

def _discover_acasl_meta(plugins_dir: Path) -> dict[str, dict[str, Any]]:
    """Importe chaque package Plugins, appelle acasl_register(manager) et construit un mapping id -> meta.
    Ne lit plus de constantes ACASL_* ni n'exécute acasl_run directement.
    """
    meta: dict[str, dict[str, Any]] = {}
    try:
        for pkg_dir in sorted(plugins_dir.iterdir(), key=lambda p: p.name):
            try:
                if not pkg_dir.is_dir():
                    continue
                init_py = pkg_dir / "__init__.py"
                if not init_py.exists():
                    continue
                mod_name = f"acasl_meta_{pkg_dir.name}"
                spec = importlib.util.spec_from_file_location(
                    mod_name, str(init_py), submodule_search_locations=[str(pkg_dir)]
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = module
                try:
                    spec.loader.exec_module(module)  # type: ignore[attr-defined]
                except Exception:
                    try:
                        del sys.modules[mod_name]
                    except Exception:
                        pass
                    continue
                reg = getattr(module, "acasl_register", None)
                if not callable(reg):
                    continue
                mgr = _ACASLTempManager()
                try:
                    reg(mgr)
                except Exception:
                    continue
                for plg in getattr(mgr, "_plugins", []):
                    meta_rec = _extract_meta_from_plugin(plg)
                    if not meta_rec:
                        continue
                    pid = meta_rec.get("id")
                    if not pid or pid in meta:
                        continue
                    meta[pid] = meta_rec
            except Exception:
                continue
    except Exception:
        pass
    return meta

# -----------------
# Config JSON-only
# -----------------

def _load_workspace_config(workspace_root: Path) -> dict[str, Any]:
    """Charge acasl.json si présent; sinon génère un défaut minimal et l'écrit."""

    def _read_json(p: Path) -> dict[str, Any]:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    for name in ("acasl.json", ".acasl.json"):
        p = workspace_root / name
        if p.exists() and p.is_file():
            data = _read_json(p)
            if isinstance(data, dict) and data:
                return data

    # Génération défaut
    default_cfg: dict[str, Any] = {}
    try:
        repo_root = Path(__file__).resolve().parents[1]
        plugins_dir = repo_root / "Plugins"
        meta_map = _discover_acasl_meta(plugins_dir) if plugins_dir.exists() else {}
        order = sorted(meta_map.keys())
        plugins = {pid: {"enabled": True, "priority": i} for i, pid in enumerate(order)}
        default_cfg = {
            "plugins": plugins,
            "plugin_order": order,
            "options": {
                "enabled": True,
                "plugin_timeout_s": 0.0,
            },
        }
        try:
            target = workspace_root / "acasl.json"
            target.write_text(
                json.dumps(default_cfg, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
    except Exception:
        pass
    return default_cfg

# -----------------
# Worker Qt
# -----------------
if QObject is not None and Signal is not None:  # pragma: no cover
    class _ACASLWorker(QObject):
        finished = Signal(object)  # report dict or None
        log = Signal(str)

        def __init__(
            self,
            gui,
            workspace_root: Path,
            plugins_dir: Path,
            cfg: dict[str, Any],
            plugin_timeout: float,
            artifacts: list[str],
        ) -> None:
            super().__init__()
            self.gui = gui
            self.workspace_root = workspace_root
            self.plugins_dir = plugins_dir
            self.cfg = cfg
            self.plugin_timeout = plugin_timeout
            self.artifacts = list(artifacts or [])

        @Slot()
        def run(self) -> None:
            try:
                meta_map = _discover_acasl_meta(self.plugins_dir)
                try:
                    self.log.emit(
                        f"🧩 ACASL: {len(meta_map)} plugin(s) détecté(s) dans Plugins/\n"
                    )
                except Exception:
                    pass
                # Déterminer liste activée et ordre
                available = list(meta_map.keys())
                pmap = self.cfg.get("plugins", {}) if isinstance(self.cfg, dict) else {}
                order = []
                try:
                    order = [
                        pid
                        for pid in (self.cfg.get("plugin_order", []) or [])
                        if pid in available
                    ]
                except Exception:
                    order = []
                if not order:
                    order = sorted(available)
                final_ids: list[str] = []
                for pid in order:
                    enabled = True
                    try:
                        v = pmap.get(pid, {})
                        enabled = (
                            bool(v.get("enabled", True))
                            if isinstance(v, dict)
                            else bool(v) if isinstance(v, bool) else True
                        )
                    except Exception:
                        enabled = True
                    if enabled:
                        final_ids.append(pid)
                # Timeout
                plugin_timeout = (
                    float(self.plugin_timeout)
                    if (self.plugin_timeout and self.plugin_timeout > 0)
                    else 0.0
                )
                # Exécution séquentielle
                report = {"status": "ok", "plugins": []}
                ctx = ACASLContext(self.gui, self.artifacts, output_dir=None)
                import time as _time

                for pid in final_ids:
                    meta = meta_map.get(pid) or {}
                    runner = meta.get("runner")
                    name = meta.get("name") or pid
                    if not callable(runner):
                        try:
                            self.log.emit(f"⚠️ ACASL: runner manquant pour {pid}\n")
                        except Exception:
                            pass
                        report["plugins"].append(
                            {
                                "id": pid,
                                "name": name,
                                "ok": False,
                                "error": "runner missing",
                                "duration_ms": 0.0,
                            }
                        )
                        continue
                    start = _time.perf_counter()
                    ok = False
                    err: Optional[str] = None
                    try:
                        if plugin_timeout > 0:
                            holder = {"err": None}

                            def _call():
                                try:
                                    runner(ctx)
                                except Exception as e:
                                    holder["err"] = e
                            th = threading.Thread(
                                target=_call, name=f"ACASL-{pid}", daemon=True
                            )
                            th.start()
                            th.join(plugin_timeout)
                            if th.is_alive():
                                err = f"timeout après {plugin_timeout:.1f}s"
                            else:
                                ok = holder["err"] is None
                                if not ok:
                                    err = str(holder["err"]) or repr(holder["err"])  # type: ignore
                        else:
                            runner(ctx)
                            ok = True
                    except Exception as e:
                        err = str(e)
                    dur_ms = (_time.perf_counter() - start) * 1000.0
                    if ok:
                        report["plugins"].append(
                            {"id": pid, "name": name, "ok": True, "duration_ms": dur_ms}
                        )
                    else:
                        try:
                            self.log.emit(f"ACASL plugin '{pid}' a échoué: {err}\n")
                        except Exception:
                            pass
                        report["plugins"].append(
                            {
                                "id": pid,
                                "name": name,
                                "ok": False,
                                "error": err or "unknown",
                                "duration_ms": dur_ms,
                            }
                        )
                self.finished.emit(report)
            except Exception as e:
                try:
                    self.log.emit(f"⚠️ ACASL erreur: {e}\n")
                except Exception:
                    pass
                self.finished.emit(None)

# -----------------
# API publique
# -----------------

def ensure_acasl_thread_stopped(gui=None) -> None:
    """Arrêt propre d'un thread ACASL actif (Qt)."""
    try:
        if gui is None:
            return
        t = getattr(gui, "_acasl_thread", None)
        if t is not None:
            try:
                if t.isRunning():
                    t.quit()
            except Exception:
                pass
        try:
            gui._acasl_thread = None
            gui._acasl_worker = None
        except Exception:
            pass
    except Exception:
        pass

def resolve_acasl_timeout(self) -> float:
    """Résout le timeout effectif des plugins ACASL (secondes) à partir de la config et de l'env.
    <= 0 => illimité (0.0 renvoyé)
    """
    try:
        if not getattr(self, "workspace_dir", None):
            return 0.0
        workspace_root = Path(self.workspace_dir).resolve()
        cfg = _load_workspace_config(workspace_root)
        try:
            env_timeout = float(os.environ.get("PYCOMPILER_ACASL_PLUGIN_TIMEOUT", "0"))
        except Exception:
            env_timeout = 0.0
        try:
            opt = cfg.get("options", {}) if isinstance(cfg, dict) else {}
            cfg_timeout = (
                float(opt.get("plugin_timeout_s", 0.0))
                if isinstance(opt, dict)
                else 0.0
            )
        except Exception:
            cfg_timeout = 0.0
        raw = cfg_timeout if cfg_timeout != 0.0 else env_timeout
        return float(raw) if raw and raw > 0 else 0.0
    except Exception:
        return 0.0

def open_acasl_loader_dialog(self) -> None:
    """UI minimale pour activer/désactiver et réordonner les plugins ACASL (JSON-only)."""
    try:
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QDialog,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPushButton,
            QVBoxLayout,
        )
        from PySide6.QtCore import Qt
    except Exception:  # pragma: no cover
        return

    try:
        if not getattr(self, "workspace_dir", None):
            QMessageBox.warning(
                self,
                "ACASL",
                "Sélectionnez un dossier workspace / Select a workspace folder first.",
            )
            return

        workspace_root = Path(self.workspace_dir).resolve()
        repo_root = Path(__file__).resolve().parents[1]
        plugins_dir = repo_root / "Plugins"

        if not plugins_dir.exists():
            QMessageBox.information(
                self,
                "ACASL",
                "Aucun répertoire Plugins trouvé / No Plugins directory found.",
            )
            return

        # Utiliser le système ACASL complet pour découvrir les plugins
        from acasl import ACASL

        manager = ACASL(workspace_root)
        loaded, errors = manager.load_plugins_from_directory(plugins_dir)

        if loaded == 0:
            QMessageBox.information(
                self, "ACASL", "Aucun plugin ACASL détecté / No ACASL plugin detected."
            )
            return

        cfg = _load_workspace_config(workspace_root)
        plugins_cfg = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}

        # Récupérer les IDs des plugins chargés
        plugin_ids = list(manager.list_plugins(include_inactive=True))
        plugin_ids_only = [pid for pid, _, _, _ in plugin_ids]

        dlg = QDialog(self)
        dlg.setWindowTitle("ACASL Loader")
        layout = QVBoxLayout(dlg)
        layout.addWidget(
            QLabel("Activez/désactivez les plugins et réordonnez (haut=d'abord).")
        )

        lst = QListWidget(dlg)
        lst.setSelectionMode(QAbstractItemView.SingleSelection)
        lst.setDragDropMode(QAbstractItemView.InternalMove)

        order = []
        try:
            order = [
                pid
                for pid in (cfg.get("plugin_order", []) or [])
                if pid in plugin_ids_only
            ]
        except Exception:
            order = []

        remaining = [pid for pid in plugin_ids_only if pid not in order]

        for pid in order + remaining:
            # Récupérer les métadonnées du plugin
            plugin_info = next((p for p in plugin_ids if p[0] == pid), None)
            if not plugin_info:
                continue

            _, meta, _, _ = plugin_info
            label = f"{meta.name} ({pid})"
            if meta.version:
                label += f" v{meta.version}"

            item = QListWidgetItem(label)
            item.setData(0x0100, pid)

            en = True
            try:
                entry = plugins_cfg.get(pid, {})
                en = (
                    bool(entry.get("enabled", True))
                    if isinstance(entry, dict)
                    else bool(entry) if isinstance(entry, bool) else True
                )
            except Exception:
                en = True

            item.setFlags(
                item.flags()
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
                | Qt.ItemIsDragEnabled
            )
            item.setCheckState(Qt.Checked if en else Qt.Unchecked)
            lst.addItem(item)

        layout.addWidget(lst)

        btns = QHBoxLayout()
        btn_up = QPushButton("⬆️")
        btn_down = QPushButton("⬇️")
        btn_save = QPushButton("Enregistrer / Save")
        btn_cancel = QPushButton("Annuler / Cancel")

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
            new_plugins: dict[str, Any] = {}
            order_ids: list[str] = []
            for i in range(lst.count()):
                it = lst.item(i)
                pid = it.data(0x0100) or it.text()
                en = it.checkState() == Qt.Checked
                new_plugins[str(pid)] = {"enabled": bool(en), "priority": i}
                order_ids.append(str(pid))
            cfg_out: dict[str, Any] = dict(cfg) if isinstance(cfg, dict) else {}
            cfg_out["plugins"] = new_plugins
            cfg_out["plugin_order"] = order_ids
            target = workspace_root / "acasl.json"
            try:
                target.write_text(
                    json.dumps(cfg_out, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                if hasattr(self, "log") and self.log is not None:
                    self.log.append("✅ ACASL: configuration enregistrée (acasl.json)")
                dlg.accept()
            except Exception as e:
                QMessageBox.critical(
                    dlg, "Erreur", f"Impossible d'écrire acasl.json: {e}"
                )
        btn_save.clicked.connect(do_save)
        btn_cancel.clicked.connect(dlg.reject)
        try:
            dlg.setModal(False)
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
            if hasattr(self, "log") and self.log:
                self.log.append(f"❌ ACASL Loader Error: {e}")
        except Exception:
            pass

def run_post_compile_async(
    gui, artifacts: list[str], finished_cb: Optional[Callable[[dict], None]] = None
) -> None:
    """Exécute les plugins ACASL en arrière-plan (Qt) ou de façon synchrone en repli."""
    try:
        from acasl import ACASL, PostCompileContext

        try:
            ws = getattr(gui, "workspace_dir", None)
            workspace_root = Path(ws if ws else os.getcwd()).resolve()
        except Exception:
            workspace_root = Path(os.getcwd()).resolve()

        repo_root = Path(__file__).resolve().parents[1]
        plugins_dir = repo_root / "Plugins"

        cfg = _load_workspace_config(workspace_root)

        # Timeout (<=0 illimité)
        try:
            env_timeout = float(os.environ.get("PYCOMPILER_ACASL_PLUGIN_TIMEOUT", "0"))
        except Exception:
            env_timeout = 0.0
        try:
            opt = cfg.get("options", {}) if isinstance(cfg, dict) else {}
            cfg_timeout = (
                float(opt.get("plugin_timeout_s", 0.0))
                if isinstance(opt, dict)
                else 0.0
            )
        except Exception:
            cfg_timeout = 0.0
        plugin_timeout = cfg_timeout if cfg_timeout != 0.0 else env_timeout
        plugin_timeout = (
            plugin_timeout if plugin_timeout and plugin_timeout > 0 else 0.0
        )

        # Global enabled flag
        try:
            opt = cfg.get("options", {}) if isinstance(cfg, dict) else {}
            acasl_enabled = (
                bool(opt.get("enabled", True)) if isinstance(opt, dict) else True
            )
        except Exception:
            acasl_enabled = True

        if not acasl_enabled:
            try:
                if hasattr(gui, "log") and gui.log:
                    gui.log.append(
                        "⏹️ ACASL désactivé dans la configuration. Exécution ignorée"
                    )
            except Exception:
                pass
            if callable(finished_cb):
                try:
                    finished_cb({"status": "disabled", "plugins": []})
                except Exception:
                    pass
            return

        # Qt worker
        if QThread is not None and "_ACASLWorker" in globals():
            thread = QThread()
            worker = _ACASLWorker(gui, workspace_root, plugins_dir, cfg, plugin_timeout, list(artifacts or []))  # type: ignore[name-defined]
            try:
                gui._acasl_thread = thread
                gui._acasl_worker = worker
            except Exception:
                pass
            # Bridge
            if hasattr(gui, "log") and gui.log:
                worker.log.connect(lambda s: gui.log.append(s))

            def _on_finished(rep):
                try:
                    if callable(finished_cb):
                        finished_cb(rep)
                except Exception:
                    pass
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
            return

        # Repli synchrone
        manager = ACASL(workspace_root, config=cfg, plugin_timeout_s=plugin_timeout)
        loaded, errors = manager.load_plugins_from_directory(plugins_dir)

        try:
            if hasattr(gui, "log") and gui.log:
                gui.log.append(
                    f"🧩 ACASL: {loaded} plugin(s) chargé(s) depuis Plugins/\n"
                )
                for mod, msg in errors or []:
                    gui.log.append(f"⚠️ Plugin '{mod}': {msg}\n")
        except Exception:
            pass

        # Appliquer config
        pmap = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
        if isinstance(pmap, dict):
            for pid, val in pmap.items():
                try:
                    enabled = (
                        val
                        if isinstance(val, bool)
                        else bool((val or {}).get("enabled", True))
                    )
                    if not enabled:
                        manager.disable_plugin(pid)
                except Exception:
                    pass
                try:
                    if isinstance(val, dict) and "priority" in val:
                        manager.set_priority(pid, int(val.get("priority", 0)))
                except Exception:
                    pass

        # Exécuter
        ctx = PostCompileContext(
            workspace_root, artifacts=list(artifacts or []), config=cfg
        )
        report = manager.run_post_compile(ctx)

        if callable(finished_cb):
            try:
                finished_cb(report)
            except Exception:
                pass
    except Exception as e:
        try:
            if callable(finished_cb):
                finished_cb({"status": "error", "error": str(e)})
        except Exception:
            pass
