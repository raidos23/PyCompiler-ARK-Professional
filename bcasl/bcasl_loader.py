# SPDX-License-Identifier: GPL-3.0-only
"""
BCASL loader (simplifié)

Objectifs de simplification:
- Config JSON uniquement (bcasl.json ou .bcasl.json)
- Détection de plugins minimale: packages dans Plugins/ ayant __init__.py
- Ordre: plugin_order depuis config sinon basé sur tags simples, sinon alphabétique
- UI minimale pour activer/désactiver et réordonner (pas d'éditeur brut multi-format)
- Async via QThread si QtCore dispo, sinon repli synchrone
- Journalisation concise dans self.log si disponible
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from bcasl import BCASL, PreCompileContext

# Qt (facultatif). Ne pas importer QtWidgets au niveau module pour compatibilité headless.
try:  # pragma: no cover
    from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
except Exception:  # pragma: no cover
    QObject = None  # type: ignore
    QThread = None  # type: ignore
    Signal = None  # type: ignore
    Slot = None  # type: ignore
    Qt = None  # type: ignore


# --- Utilitaires ---

def _has_bcasl_marker(pkg_dir: Path) -> bool:
    try:
        return (pkg_dir / "__init__.py").exists()
    except Exception:
        return False


def _discover_bcasl_meta(api_dir: Path) -> dict[str, dict[str, Any]]:
    """Découvre les plugins en important chaque package et en appelant bcasl_register(manager).
    Retourne un mapping plugin_id -> meta dict {id, name, version, description, author}
    """
    meta: dict[str, dict[str, Any]] = {}
    try:
        import importlib.util as _ilu
        import sys as _sys
        for pkg_dir in sorted(api_dir.iterdir(), key=lambda p: p.name):
            try:
                if not pkg_dir.is_dir():
                    continue
                init_py = pkg_dir / "__init__.py"
                if not init_py.exists():
                    continue
                mod_name = f"bcasl_meta_{pkg_dir.name}"
                spec = _ilu.spec_from_file_location(mod_name, str(init_py), submodule_search_locations=[str(pkg_dir)])
                if spec is None or spec.loader is None:
                    continue
                module = _ilu.module_from_spec(spec)
                _sys.modules[mod_name] = module
                spec.loader.exec_module(module)  # type: ignore[attr-defined]
                reg = getattr(module, "bcasl_register", None)
                if not callable(reg):
                    continue
                # Utilise un gestionnaire temporaire pour enregistrer et lire les métadonnées
                mgr = BCASL(api_dir, config={}, sandbox=False, plugin_timeout_s=0.0)  # type: ignore[call-arg]
                reg(mgr)
                # Récupère les plugins enregistrés
                for pid, rec in getattr(mgr, "_registry", {}).items():
                    try:
                        plg = rec.plugin
                        # Collect optional tags from plugin attribute or module-level BCASL_TAGS
                        tags: list[str] = []
                        try:
                            t = getattr(plg, "tags", None)
                            if isinstance(t, (list, tuple)):
                                tags = [str(x) for x in t]
                        except Exception:
                            tags = []
                        if not tags:
                            try:
                                mt = getattr(module, "BCASL_TAGS", [])
                                if isinstance(mt, (list, tuple)):
                                    tags = [str(x) for x in mt]
                            except Exception:
                                tags = []
                        m = {
                            "id": plg.meta.id,
                            "name": plg.meta.name,
                            "version": plg.meta.version,
                            "description": plg.meta.description,
                            "author": plg.meta.author,
                            "tags": tags,
                        }
                        meta[plg.meta.id] = m
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass
    return meta




def _compute_tag_order(meta_map: dict[str, dict[str, Any]]) -> list[str]:
    """Trie les plugins par score de tag (plus petit d'abord), puis par id.
    Tags pris depuis meta_map[pid]["tags"]. Inconnu => 100.
    """
    tag_score = {
        # Clean early (workspace hygiene)
        "clean": 0, "cleanup": 0, "sanitize": 0, "prune": 0, "tidy": 0,
        # Validation / presence of inputs
        "validation": 10, "presence": 10, "check": 10, "requirements": 10,
        # Prepare / generate inputs and resources
        "prepare": 20, "codegen": 20, "generate": 20, "fetch": 20, "resources": 20,
        "download": 20, "install": 20, "bootstrap": 20, "configure": 20,
        # Conformity / headers before linters
        "license": 30, "header": 30, "normalize": 30, "inject": 30, "spdx": 30, "banner": 30, "copyright": 30,
        # Lint / format / typing
        "lint": 40, "format": 40, "typecheck": 40, "mypy": 40, "flake8": 40, "ruff": 40, "pep8": 40, "black": 40, "isort": 40, "sort-imports": 40,
        # Obfuscation / protect / transpile (final pre-compile passes)
        "obfuscation": 50, "obfuscate": 50, "transpile": 50, "protect": 50, "encrypt": 50,
    }

    def _score(pid: str) -> int:
        try:
            tags = meta_map.get(pid, {}).get("tags") or []
            if isinstance(tags, list) and tags:
                return int(min((tag_score.get(str(t).lower(), 100) for t in tags), default=100))
        except Exception:
            pass
        return 100

    return sorted(meta_map.keys(), key=lambda x: (_score(x), x))


# --- Chargement config (JSON uniquement) ---

def _load_workspace_config(workspace_root: Path) -> dict[str, Any]:
    """Charge bcasl.json si présent, sinon génère une config par défaut minimale et l'écrit."""
    def _read_json(p: Path) -> dict[str, Any]:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    # 1) Fichiers candidats (JSON uniquement)
    for name in ("bcasl.json", ".bcasl.json"):
        p = workspace_root / name
        if p.exists() and p.is_file():
            data = _read_json(p)
            if isinstance(data, dict) and data:
                return data

    # 2) Génération défaut
    default_cfg: dict[str, Any] = {}
    try:
        repo_root = Path(__file__).resolve().parents[1]
        api_dir = repo_root / "Plugins"
        detected_plugins: dict[str, Any] = {}
        meta_map = _discover_bcasl_meta(api_dir) if api_dir.exists() else {}
        if meta_map:
            order = _compute_tag_order(meta_map)
            for idx, pid in enumerate(order):
                detected_plugins[pid] = {"enabled": True, "priority": idx}
            plugin_order = order
        else:
            # Fallback alphabétique par dossier
            try:
                names = [p.name for p in sorted(api_dir.iterdir()) if (p.is_dir() and _has_bcasl_marker(p))]
            except Exception:
                names = []
            for idx, pid in enumerate(sorted(names)):
                detected_plugins[pid] = {"enabled": True, "priority": idx}
            plugin_order = sorted(names)

        required_files = []
        for fname in ("main.py", "app.py", "requirements.txt", "pyproject.toml"):
            try:
                if (workspace_root / fname).is_file():
                    required_files.append(fname)
            except Exception:
                pass

        default_cfg = {
            "required_files": required_files,
            "file_patterns": ["**/*.py"],
            "exclude_patterns": [
                "**/__pycache__/**",
                "**/*.pyc",
                ".git/**",
                "venv/**",
                ".venv/**",
            ],
            "options": {
                "enabled": True,
                "plugin_timeout_s": 0.0,  # 0 => illimité
                "sandbox": True,
                "plugin_parallelism": 0,
                "iter_files_cache": True,
            },
            "plugins": detected_plugins,
            "plugin_order": plugin_order,
        }
        # Ecriture best-effort
        try:
            target = workspace_root / "bcasl.json"
            target.write_text(json.dumps(default_cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
    except Exception:
        pass
    return default_cfg


# --- Worker et bridge (Qt) ---
if QObject is not None and Signal is not None:  # pragma: no cover

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
                loaded, errors = manager.load_plugins_from_directory(self.api_dir)
                try:
                    self.log.emit(f"🧩 BCASL: {loaded} package(s) chargé(s) depuis Plugins/\n")
                    for mod, msg in errors or []:
                        self.log.emit(f"⚠️ Plugin '{mod}': {msg}\n")
                except Exception:
                    pass
                # Activer/désactiver + priorités
                pmap = self.cfg.get("plugins", {}) if isinstance(self.cfg, dict) else {}
                if isinstance(pmap, dict):
                    for pid, val in pmap.items():
                        try:
                            enabled = (val if isinstance(val, bool) else bool((val or {}).get("enabled", True)))
                            if not enabled:
                                manager.disable_plugin(pid)
                        except Exception:
                            pass
                        try:
                            if isinstance(val, dict) and "priority" in val:
                                manager.set_priority(pid, int(val.get("priority", 0)))
                        except Exception:
                            pass
                order_list = []
                try:
                    order_list = list(self.cfg.get("plugin_order", [])) if isinstance(self.cfg, dict) else []
                except Exception:
                    order_list = []
                if not order_list:
                    try:
                        meta_en = _discover_bcasl_meta(self.api_dir)
                        order_list = list(_compute_tag_order(meta_en))
                    except Exception:
                        order_list = []
                if order_list:
                    for idx, pid in enumerate(order_list):
                        try:
                            self.log.emit(f"⏫ Priorité {idx} pour {pid}\n")
                            manager.set_priority(pid, int(idx))
                        except Exception:
                            pass
                report = manager.run_pre_compile(PreCompileContext(self.workspace_root, config=self.cfg))
                self.finished.emit(report)
            except Exception as e:
                try:
                    self.log.emit(f"⚠️ Erreur BCASL: {e}\n")
                except Exception:
                    pass
                self.finished.emit(None)


if QObject is not None and Signal is not None:  # pragma: no cover

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
                if rep and hasattr(self._gui, "log") and self._gui.log is not None:
                    self._gui.log.append("BCASL - Rapport:\n")
                    for item in rep:
                        try:
                            state = "OK" if getattr(item, "success", False) else f"FAIL: {getattr(item, 'error', '')}"
                            dur = getattr(item, "duration_ms", 0.0)
                            pid = getattr(item, "plugin_id", "?")
                            self._gui.log.append(f" - {pid}: {state} ({dur:.1f} ms)\n")
                        except Exception:
                            pass
                    try:
                        self._gui.log.append(rep.summary() + "\n")
                    except Exception:
                        pass
                try:
                    if callable(self._on_done):
                        self._on_done(rep)
                except Exception:
                    pass
            finally:
                try:
                    self._thread.quit()
                except Exception:
                    pass


# --- API publique attendue par le reste de l'app ---

def ensure_bcasl_thread_stopped(self, timeout_ms: int = 5000) -> None:
    """Arrête proprement un thread BCASL en cours (si présent)."""
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
        # Nettoyage
        try:
            self._bcasl_thread = None
            self._bcasl_worker = None
            if hasattr(self, "_bcasl_ui_bridge"):
                self._bcasl_ui_bridge = None
        except Exception:
            pass
    except Exception:
        pass


def resolve_bcasl_timeout(self) -> float:
    """Résout le timeout effectif des plugins à partir de la config et de l'env.
    <= 0 => illimité (0.0 renvoyé)
    """
    try:
        if not getattr(self, "workspace_dir", None):
            return 0.0
        workspace_root = Path(self.workspace_dir).resolve()
        cfg = _load_workspace_config(workspace_root)
        try:
            env_timeout = float(os.environ.get("PYCOMPILER_BCASL_PLUGIN_TIMEOUT", "0"))
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


def open_api_loader_dialog(self) -> None:  # UI minimale
    """Fenêtre simple pour activer/désactiver et réordonner les plugins(BCASL).
    Persiste dans <workspace>/bcasl.json uniquement (JSON).
    """
    try:  # Importer QtWidgets à la demande pour compatibilité headless
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
    except Exception:  # pragma: no cover
        return

    try:
        if not getattr(self, "workspace_dir", None):
            QMessageBox.warning(
                self,
                self.tr("Attention", "Warning"),
                self.tr("Veuillez d'abord sélectionner un dossier workspace.", "Please select a workspace folder first."),
            )
            return
        workspace_root = Path(self.workspace_dir).resolve()
        repo_root = Path(__file__).resolve().parents[1]
        api_dir = repo_root / "Plugins"
        if not api_dir.exists():
            QMessageBox.information(
                self,
                self.tr("Information", "Information"),
                self.tr("Aucun répertoire Plugins/ trouvé dans le projet.", "No Plugins/ directory found in the project."),
            )
            return
        meta_map = _discover_bcasl_meta(api_dir)
        plugin_ids = list(sorted(meta_map.keys()))
        if not plugin_ids:
            QMessageBox.information(
                self,
                self.tr("Information", "Information"),
                self.tr("Aucun plugin détecté dans Plugins/.", "No plugins detected in Plugins."),
            )
            return
        cfg = _load_workspace_config(workspace_root)
        plugins_cfg = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("BCASL LOADER", "BCASL LOADER"))
        layout = QVBoxLayout(dlg)
        info = QLabel(
            self.tr(
                "Activez/désactivez les plugins et définissez leur ordre d'exécution (haut = d'abord).",
                "Enable/disable plugins and set their execution order (top = first).",
            )
        )
        layout.addWidget(info)

        # Liste réordonnable avec cases à cocher
        lst = QListWidget(dlg)
        lst.setSelectionMode(QAbstractItemView.SingleSelection)
        lst.setDragDropMode(QAbstractItemView.InternalMove)

        # Ordre initial: plugin_order si présent; sinon heuristique par tags; sinon alphabétique
        order = []
        try:
            order = cfg.get("plugin_order", []) if isinstance(cfg, dict) else []
            order = [pid for pid in order if pid in plugin_ids]
        except Exception:
            order = []
        if not order:
            try:
                order = [pid for pid in _compute_tag_order(meta_map) if pid in plugin_ids]
            except Exception:
                order = sorted(plugin_ids)

        remaining = [pid for pid in plugin_ids if pid not in order]
        ordered_ids = order + remaining
        for pid in ordered_ids:
            meta = meta_map.get(pid, {})
            label = meta.get("name") or pid
            ver = meta.get("version") or ""
            text = f"{label} ({pid})" + (f" v{ver}" if ver else "")
            item = QListWidgetItem(text)
            # Tooltip simple
            try:
                desc = meta.get("description") or ""
                if desc:
                    item.setToolTip(desc)
            except Exception:
                pass
            # Etat
            enabled = True
            try:
                pentry = plugins_cfg.get(pid, {})
                if isinstance(pentry, dict):
                    enabled = bool(pentry.get("enabled", True))
                elif isinstance(pentry, bool):
                    enabled = pentry
            except Exception:
                pass
            try:
                item.setData(0x0100, pid)
            except Exception:
                pass
            if Qt is not None:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if (Qt is not None and enabled) else 2 if enabled else 0)
            lst.addItem(item)
        layout.addWidget(lst)

        # Boutons
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
            # Extraire ordre et états
            new_plugins: dict[str, Any] = {}
            order_ids: list[str] = []
            for i in range(lst.count()):
                it = lst.item(i)
                pid = it.data(0x0100) or it.text()
                en = (it.checkState() == (Qt.Checked if Qt is not None else 2))
                new_plugins[str(pid)] = {"enabled": bool(en), "priority": i}
                order_ids.append(str(pid))
            cfg_out: dict[str, Any] = dict(cfg) if isinstance(cfg, dict) else {}
            cfg_out["plugins"] = new_plugins
            cfg_out["plugin_order"] = order_ids
            # Ecrire JSON uniquement
            target = workspace_root / "bcasl.json"
            try:
                target.write_text(json.dumps(cfg_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                if hasattr(self, "log") and self.log is not None:
                    self.log.append(self.tr("✅ Plugins enregistrés dans bcasl.json", "✅ Plugins plugins saved to bcasl.json"))
                dlg.accept()
            except Exception as e:
                QMessageBox.critical(
                    dlg,
                    self.tr("Erreur", "Error"),
                    self.tr(f"Impossible d'écrire bcasl.json: {e}", f"Failed to write bcasl.json: {e}"),
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
            if hasattr(self, "log") and self.log is not None:
                self.log.append(f"⚠️ Plugins Loader UI error: {e}")
        except Exception:
            pass

#API

def run_pre_compile_async(self, on_done: Optional[callable] = None) -> None:
    """Lance BCASL en arrière-plan si QtCore est dispo; sinon, exécution bloquante rapide.
    on_done(report) appelé à la fin si fourni.
    """
    try:
        if not getattr(self, "workspace_dir", None):
            if callable(on_done):
                try:
                    on_done(None)
                except Exception:
                    pass
            return
        workspace_root = Path(self.workspace_dir).resolve()
        repo_root = Path(__file__).resolve().parents[1]
        api_dir = repo_root / "Plugins"

        cfg = _load_workspace_config(workspace_root)
        # Timeout: <= 0 => illimité
        try:
            env_timeout = float(os.environ.get("PYCOMPILER_BCASL_PLUGIN_TIMEOUT", "0"))
        except Exception:
            env_timeout = 0.0
        opt = cfg.get("options", {}) if isinstance(cfg, dict) else {}
        try:
            cfg_timeout = float(opt.get("plugin_timeout_s", 0.0)) if isinstance(opt, dict) else 0.0
        except Exception:
            cfg_timeout = 0.0
        plugin_timeout = cfg_timeout if cfg_timeout != 0.0 else env_timeout
        plugin_timeout = plugin_timeout if plugin_timeout and plugin_timeout > 0 else 0.0
        # Respect du flag global enabled
        try:
            bcasl_enabled = bool(opt.get("enabled", True)) if isinstance(opt, dict) else True
        except Exception:
            bcasl_enabled = True
        if not bcasl_enabled:
            try:
                if hasattr(self, "log") and self.log is not None:
                    self.log.append(self.tr("⏹️ BCASL désactivé dans la configuration. Exécution ignorée\n", "⏹️ BCASL disabled in configuration. Skipping execution\n"))
            except Exception:
                pass
            if callable(on_done):
                try:
                    on_done({"status": "disabled"})
                except Exception:
                    pass
            return

        if QThread is not None and QObject is not None and Signal is not None:
            thread = QThread()
            worker = _BCASLWorker(workspace_root, api_dir, cfg, plugin_timeout)  # type: ignore[name-defined]
            try:
                self._bcasl_thread = thread
                self._bcasl_worker = worker
            except Exception:
                pass
            bridge = _BCASLUiBridge(self, on_done, thread)  # type: ignore[name-defined]
            try:
                self._bcasl_ui_bridge = bridge
            except Exception:
                pass
            if hasattr(self, "log") and self.log is not None:
                worker.log.connect(bridge.on_log)
            worker.finished.connect(bridge.on_finished)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            thread.start()
            return

        # Repli: exécution synchrone
        try:
            manager = BCASL(workspace_root, config=cfg, plugin_timeout_s=plugin_timeout)
            loaded, errors = manager.load_plugins_from_directory(api_dir)
            if hasattr(self, "log") and self.log is not None:
                self.log.append(f"🧩 BCASL: {loaded} package(s) chargé(s) depuis Plugins/\n")
                for mod, msg in errors or []:
                    self.log.append(f"⚠️ Plugin '{mod}': {msg}\n")
            # Appliquer config
            pmap = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
            if isinstance(pmap, dict):
                for pid, val in pmap.items():
                    try:
                        enabled = (val if isinstance(val, bool) else bool((val or {}).get("enabled", True)))
                        if not enabled:
                            manager.disable_plugin(pid)
                    except Exception:
                        pass
                    try:
                        if isinstance(val, dict) and "priority" in val:
                            manager.set_priority(pid, int(val.get("priority", 0)))
                    except Exception:
                        pass
            order_list = list(cfg.get("plugin_order", [])) if isinstance(cfg, dict) else []
            if not order_list:
                try:
                    meta_en = _discover_bcasl_meta(api_dir)
                    order_list = list(_compute_tag_order(meta_en))
                except Exception:
                    order_list = []
            if order_list:
                for idx, pid in enumerate(order_list):
                    try:
                        if hasattr(self, "log") and self.log is not None:
                            self.log.append(f"⏫ Priorité {idx} pour {pid}\n")
                        manager.set_priority(pid, int(idx))
                    except Exception:
                        pass
            report = manager.run_pre_compile(PreCompileContext(workspace_root, config=cfg))
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
            if callable(on_done):
                on_done(None)
        except Exception:
            pass
        try:
            if hasattr(self, "log") and self.log is not None:
                self.log.append(f"⚠️ Erreur BCASL (async): {e}\n")
        except Exception:
            pass


def run_pre_compile(self) -> Optional[object]:
    """Exécute la phase BCASL de pré-compilation (chemin synchrone, simple)."""
    try:
        if not getattr(self, "workspace_dir", None):
            return None
        workspace_root = Path(self.workspace_dir).resolve()
        repo_root = Path(__file__).resolve().parents[1]
        api_dir = repo_root / "Plugins"

        cfg = _load_workspace_config(workspace_root)
        try:
            env_timeout = float(os.environ.get("PYCOMPILER_BCASL_PLUGIN_TIMEOUT", "0"))
        except Exception:
            env_timeout = 0.0
        try:
            opt = cfg.get("options", {}) if isinstance(cfg, dict) else {}
            cfg_timeout = float(opt.get("plugin_timeout_s", 0.0)) if isinstance(opt, dict) else 0.0
        except Exception:
            cfg_timeout = 0.0
        plugin_timeout = cfg_timeout if cfg_timeout != 0.0 else env_timeout
        plugin_timeout = plugin_timeout if plugin_timeout and plugin_timeout > 0 else 0.0

        try:
            bcasl_enabled = bool(opt.get("enabled", True)) if isinstance(opt, dict) else True
        except Exception:
            bcasl_enabled = True
        if not bcasl_enabled:
            try:
                if hasattr(self, "log") and self.log is not None:
                    self.log.append("⏹️ BCASL désactivé dans la configuration. Exécution ignorée\n")
            except Exception:
                pass
            return None

        manager = BCASL(workspace_root, config=cfg, plugin_timeout_s=plugin_timeout)
        loaded, errors = manager.load_plugins_from_directory(api_dir)
        if hasattr(self, "log") and self.log is not None:
            self.log.append(f"🧩 BCASL: {loaded} package(s) chargé(s) depuis Plugins/\n")
            for mod, msg in errors or []:
                self.log.append(f"⚠️ Plugin '{mod}': {msg}\n")

        # Appliquer activation/priorité
        try:
            pmap = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
            if isinstance(pmap, dict):
                for pid, val in pmap.items():
                    try:
                        enabled = (val if isinstance(val, bool) else bool((val or {}).get("enabled", True)))
                        if not enabled:
                            manager.disable_plugin(pid)
                    except Exception:
                        pass
                    try:
                        if isinstance(val, dict) and "priority" in val:
                            manager.set_priority(pid, int(val.get("priority", 0)))
                    except Exception:
                        pass
            order_list = []
            try:
                order_list = list(cfg.get("plugin_order", [])) if isinstance(cfg, dict) else []
            except Exception:
                order_list = []
            if not order_list:
                try:
                    meta_en = _discover_bcasl_meta(api_dir)
                    order_list = list(_compute_tag_order(meta_en))
                except Exception:
                    order_list = []
            if order_list:
                for idx, pid in enumerate(order_list):
                    try:
                        if hasattr(self, "log") and self.log is not None:
                            self.log.append(f"⏫ Priorité {idx} pour {pid}\n")
                        manager.set_priority(pid, int(idx))
                    except Exception:
                        pass
        except Exception:
            pass

        report = manager.run_pre_compile(PreCompileContext(workspace_root, config=cfg))
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
