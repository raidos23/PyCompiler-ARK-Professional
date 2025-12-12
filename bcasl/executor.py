from .Base import (
    BCASL_PLUGIN_REGISTER_FUNC,
    _PluginRecord,
    BcPluginBase,
    ExecutionItem,
    ExecutionReport,
    PluginMeta,
    PreCompileContext,
    _logger,
)

import heapq
import importlib.util
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional


class BCASL:
    """Gestionnaire principal des plugins et de leur exécution avant compilation."""

    def __init__(
        self,
        project_root: Path,
        config: Optional[dict[str, Any]] = None,
        *,
        sandbox: bool = True,
        plugin_timeout_s: float = 3.0,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.config = dict(config or {})
        self._registry: dict[str, _PluginRecord] = {}
        self._insert_counter = 0
        # Sandbox settings
        self.sandbox = bool(sandbox)
        self.plugin_timeout_s = float(plugin_timeout_s)

    # API publique
    def add_plugin(self, plugin: BcPluginBase) -> None:
        if not isinstance(plugin, BcPluginBase):
            raise TypeError("Le plugin doit être une instance de BcPluginBase")
        pid = plugin.meta.id
        if pid in self._registry:
            raise ValueError(f"Plugin id déjà enregistré: {pid}")
        rec = _PluginRecord(plugin, self._insert_counter)
        self._registry[pid] = rec
        self._insert_counter += 1
        _logger.debug("Plugin ajouté: %s", plugin)

    def remove_plugin(self, plugin_id: str) -> bool:
        return self._registry.pop(plugin_id, None) is not None

    def list_plugins(
        self, include_inactive: bool = True
    ) -> list[tuple[str, PluginMeta, bool, int]]:
        out = []
        for pid, rec in self._registry.items():
            if include_inactive or rec.active:
                out.append((pid, rec.plugin.meta, rec.active, rec.priority))
        out.sort(key=lambda x: (x[3], x[0]))
        return out

    def enable_plugin(self, plugin_id: str) -> bool:
        rec = self._registry.get(plugin_id)
        if not rec:
            return False
        rec.active = True
        return True

    def disable_plugin(self, plugin_id: str) -> bool:
        rec = self._registry.get(plugin_id)
        if not rec:
            return False
        rec.active = False
        return True

    def set_priority(self, plugin_id: str, priority: int) -> bool:
        rec = self._registry.get(plugin_id)
        if not rec:
            return False
        rec.priority = int(priority)
        rec.plugin.priority = int(priority)
        return True

    # Chargement automatique
    def load_plugins_from_directory(
        self, directory: Path
    ) -> tuple[int, list[tuple[str, str]]]:
        """Charge automatiquement tous les plugins depuis un dossier.

        Retourne (nombre_plugins_enregistrés, liste_erreurs[(module, message)]).
        """
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            _logger.warning("Dossier plugins introuvable: %s", directory)
            return 0, [(str(directory), "non trouvé ou non répertoire")]

        count = 0
        errors: list[tuple[str, str]] = []
        # Parcourt uniquement les packages Python (dossiers contenant __init__.py)
        try:
            pkg_dirs = sorted(
                [p for p in directory.iterdir() if p.is_dir()], key=lambda p: p.name
            )
        except Exception:
            pkg_dirs = []
        for pkg_dir in pkg_dirs:
            if pkg_dir.name.startswith("__"):
                continue
            init_file = pkg_dir / "__init__.py"
            if not init_file.exists():
                continue
            mod_name = f"bcasl_api_{pkg_dir.name}"
            try:
                spec = importlib.util.spec_from_file_location(
                    mod_name, str(init_file), submodule_search_locations=[str(pkg_dir)]
                )
                if spec is None or spec.loader is None:
                    raise ImportError("spec invalide")
                module = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = module
                spec.loader.exec_module(module)  # type: ignore[attr-defined]

                # Recherche et appel de la fonction d'enregistrement si présente
                reg = getattr(module, BCASL_PLUGIN_REGISTER_FUNC, None)
                if not callable(reg):
                    _logger.debug(
                        "Package %s: aucune fonction %s, ignoré",
                        pkg_dir.name,
                        BCASL_PLUGIN_REGISTER_FUNC,
                    )
                    continue
                # Appeler l'enregistrement
                before_ids = set(self._registry.keys())
                reg(self)  # le package appelle self.add_plugin(...)
                new_ids = [k for k in self._registry.keys() if k not in before_ids]
                for pid in new_ids:
                    rec = self._registry.get(pid)
                    if rec is not None:
                        rec.module_path = init_file
                        rec.module_name = mod_name
                # Validation de signature supprimée (simplification)
                added = len(new_ids)
                if added <= 0:
                    _logger.warning(
                        "Aucun plugin enregistré par package %s", pkg_dir.name
                    )
                else:
                    count += added
                    _logger.info("Plugin chargé depuis package %s", pkg_dir.name)
            except Exception as exc:  # isolation
                msg = f"échec chargement: {exc}"
                errors.append((pkg_dir.name, msg))
                _logger.error("%s: %s", pkg_dir.name, msg)
        return count, errors

    # Ordonnancement et exécution
    def _resolve_order(self) -> list[str]:
        """Résout l'ordre d'exécution en respectant dépendances et priorités.

        - Filtre les plugins inactifs
        - Ignore les dépendances inconnues (log warning)
        - Kahn + file de priorité (priority, insert_idx) pour stabilité
        - En cas de cycle, journalise et insère les restants par priorité
        """
        active_items = {pid: rec for pid, rec in self._registry.items() if rec.active}
        if not active_items:
            return []

        # Construire graphe
        indeg: dict[str, int] = {pid: 0 for pid in active_items}
        children: dict[str, list[str]] = {pid: [] for pid in active_items}

        for pid, rec in active_items.items():
            for dep in rec.requires:
                if dep not in active_items:
                    _logger.warning(
                        "Dépendance manquante pour %s: '%s' (ignorée)", pid, dep
                    )
                    continue
                indeg[pid] += 1
                children[dep].append(pid)

        # File de départ (indeg=0) triée par priorité puis ordre d'insertion
        roots = sorted(
            [pid for pid, d in indeg.items() if d == 0],
            key=lambda x: (active_items[x].priority, active_items[x].insert_idx, x),
        )
        order: list[str] = []
        import heapq

        heap: list[tuple[int, int, str]] = []
        for pid in roots:
            rec = active_items[pid]
            heapq.heappush(heap, (rec.priority, rec.insert_idx, pid))

        while heap:
            _, _, pid = heapq.heappop(heap)
            order.append(pid)
            for ch in children[pid]:
                indeg[ch] -= 1
                if indeg[ch] == 0:
                    rch = active_items[ch]
                    heapq.heappush(heap, (rch.priority, rch.insert_idx, ch))

        if len(order) != len(active_items):
            # Cycle détecté; insérer les restants par priorité pour ne pas bloquer
            remaining = [pid for pid in active_items if pid not in order]
            _logger.error("Cycle de dépendances détecté: %s", ", ".join(remaining))
            remaining.sort(
                key=lambda x: (active_items[x].priority, active_items[x].insert_idx, x)
            )
            order.extend(remaining)
        return order

    def run_pre_compile(
        self, ctx: Optional[PreCompileContext] = None
    ) -> ExecutionReport:
        """Exécute le hook 'on_pre_compile' de tous les plugins actifs.

        Optimisations de performance:
        - Exécution parallèle des plugins sandboxés en respectant dépendances/priorités
        - Cache optionnel des itérations de fichiers (voir PreCompileContext.iter_files)
        - Paramètres via options.sandbox, options.plugin_parallelism et env PYCOMPILER_BCASL_PARALLELISM
        """
        if ctx is None:
            ctx = PreCompileContext(self.project_root, self.config)
        else:
            ctx.project_root = Path(ctx.project_root).resolve()
            ctx.config = dict(self.config) | dict(ctx.config or {})

        report = ExecutionReport()
        # Options d'exécution
        try:
            opts = (
                dict(self.config or {}).get("options", {})
                if isinstance(self.config, dict)
                else {}
            )
        except Exception:
            opts = {}
        eff_sandbox = bool(opts.get("sandbox", self.sandbox))
        # Déterminer le parallélisme cible
        try:
            par_env = int(os.environ.get("PYCOMPILER_BCASL_PARALLELISM", "0"))
        except Exception:
            par_env = 0
        try:
            par_opt = int(opts.get("plugin_parallelism", 0))
        except Exception:
            par_opt = 0
        try:
            cpu_def = max(1, (mp.cpu_count() or 2) - 1)
        except Exception:
            cpu_def = 2
        parallelism = par_env or par_opt or cpu_def
        if parallelism < 1:
            parallelism = 1

        # Construire graphe des dépendances des plugins actifs
        active_items = {pid: rec for pid, rec in self._registry.items() if rec.active}
        if not active_items:
            _logger.info("Aucun plugin actif")
            return report
        indeg: dict[str, int] = {pid: 0 for pid in active_items}
        children: dict[str, list[str]] = {pid: [] for pid in active_items}
        for pid, rec in active_items.items():
            for dep in rec.requires:
                if dep not in active_items:
                    _logger.warning(
                        "Dépendance manquante pour %s: '%s' (ignorée)", pid, dep
                    )
                    continue
                indeg[pid] += 1
                children[dep].append(pid)

        # File d'attente initiale (indeg=0) triée par (priority, insert_idx, pid)
        import heapq

        ready: list[tuple[int, int, str]] = []
        for pid, rec in active_items.items():
            if indeg[pid] == 0:
                heapq.heappush(ready, (rec.priority, rec.insert_idx, pid))

        # Fallback: si pas de sandbox ou parallélisme=1, revient au mode séquentiel
        if not eff_sandbox or parallelism <= 1:
            order: list[str] = []
            tmp_ready = list(ready)
            heapq.heapify(tmp_ready)
            while tmp_ready:
                _, _, pid = heapq.heappop(tmp_ready)
                order.append(pid)
                for ch in children[pid]:
                    indeg[ch] -= 1
                    if indeg[ch] == 0:
                        rch = active_items[ch]
                        heapq.heappush(tmp_ready, (rch.priority, rch.insert_idx, ch))
            # Séquentiel sandbox/non-sandbox
            for pid in order:
                rec = active_items[pid]
                plg = rec.plugin
                start = time.perf_counter()
                if eff_sandbox and getattr(rec, "module_path", None):
                    _ctx = mp.get_context("spawn")
                    q = _ctx.Queue()
                    p = _ctx.Process(
                        target=_plugin_worker,
                        args=(
                            str(rec.module_path),
                            pid,
                            str(self.project_root),
                            ctx.config,
                            q,
                        ),
                    )
                    p.start()
                    timeout = self.plugin_timeout_s
                    if timeout and timeout > 0:
                        p.join(timeout)
                    else:
                        p.join()
                    if p.is_alive():
                        try:
                            p.terminate()
                        except Exception:
                            pass
                        try:
                            p.join(1.0)
                        except Exception:
                            pass
                        duration_ms = (time.perf_counter() - start) * 1000.0
                        report.add(
                            ExecutionItem(
                                plugin_id=pid,
                                name=plg.meta.name,
                                success=False,
                                duration_ms=duration_ms,
                                error=f"timeout après {self.plugin_timeout_s:.1f}s",
                            )
                        )
                        _logger.error(
                            "Plugin %s timeout après %.1fs", pid, self.plugin_timeout_s
                        )
                    else:
                        try:
                            res = q.get_nowait()
                        except Exception:
                            res = {
                                "ok": False,
                                "error": "aucun résultat renvoyé (crash du processus enfant ?)",
                                "duration_ms": (time.perf_counter() - start) * 1000.0,
                            }
                        duration_ms = float(
                            res.get(
                                "duration_ms", (time.perf_counter() - start) * 1000.0
                            )
                        )
                        if res.get("ok"):
                            report.add(
                                ExecutionItem(
                                    plugin_id=pid,
                                    name=plg.meta.name,
                                    success=True,
                                    duration_ms=duration_ms,
                                )
                            )
                        else:
                            report.add(
                                ExecutionItem(
                                    plugin_id=pid,
                                    name=plg.meta.name,
                                    success=False,
                                    duration_ms=duration_ms,
                                    error=str(res.get("error", "")),
                                )
                            )
                else:
                    try:
                        plg.on_pre_compile(ctx)
                        duration_ms = (time.perf_counter() - start) * 1000.0
                        report.add(
                            ExecutionItem(
                                plugin_id=pid,
                                name=plg.meta.name,
                                success=True,
                                duration_ms=duration_ms,
                            )
                        )
                    except Exception as exc:
                        duration_ms = (time.perf_counter() - start) * 1000.0
                        report.add(
                            ExecutionItem(
                                plugin_id=pid,
                                name=plg.meta.name,
                                success=False,
                                duration_ms=duration_ms,
                                error=str(exc),
                            )
                        )
            _logger.info(report.summary())
            return report

        # Exécution parallèle (sandbox True)
        _ctx = mp.get_context("spawn")
        running: dict[str, tuple[mp.Process, mp.Queue, float]] = {}
        # Scheduler principal
        while ready or running:
            # Lancer tant que possible
            while ready and len(running) < parallelism:
                _, _, pid = heapq.heappop(ready)
                rec = active_items[pid]
                q = _ctx.Queue()
                p = _ctx.Process(
                    target=_plugin_worker,
                    args=(
                        str(rec.module_path),
                        pid,
                        str(self.project_root),
                        ctx.config,
                        q,
                    ),
                )
                p.start()
                running[pid] = (p, q, time.perf_counter())
            # Collecte non bloquante et gestion timeouts
            to_remove: list[str] = []
            for pid, (proc, q, start_t) in list(running.items()):
                timeout = self.plugin_timeout_s
                alive = proc.is_alive()
                timed_out = False
                if timeout and timeout > 0 and alive:
                    if (time.perf_counter() - start_t) >= timeout:
                        timed_out = True
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        try:
                            proc.join(1.0)
                        except Exception:
                            pass
                if not alive or timed_out:
                    rec = active_items[pid]
                    plg = rec.plugin
                    if not timed_out:
                        try:
                            res = q.get_nowait()
                        except Exception:
                            res = {
                                "ok": False,
                                "error": "aucun résultat renvoyé (crash du processus enfant ?)",
                                "duration_ms": (time.perf_counter() - start_t) * 1000.0,
                            }
                        duration_ms = float(
                            res.get(
                                "duration_ms", (time.perf_counter() - start_t) * 1000.0
                            )
                        )
                        if res.get("ok"):
                            report.add(
                                ExecutionItem(
                                    plugin_id=pid,
                                    name=plg.meta.name,
                                    success=True,
                                    duration_ms=duration_ms,
                                )
                            )
                        else:
                            report.add(
                                ExecutionItem(
                                    plugin_id=pid,
                                    name=plg.meta.name,
                                    success=False,
                                    duration_ms=duration_ms,
                                    error=str(res.get("error", "")),
                                )
                            )
                    else:
                        duration_ms = (time.perf_counter() - start_t) * 1000.0
                        report.add(
                            ExecutionItem(
                                plugin_id=pid,
                                name=plg.meta.name,
                                success=False,
                                duration_ms=duration_ms,
                                error=f"timeout après {self.plugin_timeout_s:.1f}s",
                            )
                        )
                        _logger.error(
                            "Plugin %s timeout après %.1fs", pid, self.plugin_timeout_s
                        )
                    # Débloquer les enfants
                    for ch in children[pid]:
                        indeg[ch] -= 1
                        if indeg[ch] == 0:
                            rch = active_items[ch]
                            heapq.heappush(ready, (rch.priority, rch.insert_idx, ch))
                    to_remove.append(pid)
            for pid in to_remove:
                try:
                    proc, _q, _t = running.pop(pid)
                    if proc.is_alive():
                        try:
                            proc.join(0.1)
                        except Exception:
                            pass
                except Exception:
                    pass
            if running and not ready:
                # Attendre un court instant avant prochain tour pour éviter busy-wait
                time.sleep(0.01)
        _logger.info(report.summary())
        return report


def _plugin_worker(
    module_path: str, plugin_id: str, project_root: str, config: dict[str, Any], q
) -> None:
    """Charge un module de plugin depuis son chemin et exécute on_pre_compile dans un processus isolé.

    Renvoie un dict via la queue: {ok: bool, error: str, duration_ms: float}
    """
    import importlib.util as _ilu
    import os as _os
    import sys as _sys
    import time as _time
    import traceback as _tb
    from pathlib import Path as _Path

    # Configure interactivity and Qt platform for sandbox worker based on config/env
    try:
        _opts = (
            dict(config or {}).get("options", {}) if isinstance(config, dict) else {}
        )
        _env_nonint = _os.environ.get("PYCOMPILER_NONINTERACTIVE_PLUGINS")
        _env_offscreen = _os.environ.get("PYCOMPILER_OFFSCREEN_PLUGINS")
        _noninteractive = (
            (str(_env_nonint).strip().lower() in ("1", "true", "yes"))
            if (_env_nonint is not None)
            else bool(_opts.get("noninteractive_plugins", False))
        )
        _offscreen = (
            (str(_env_offscreen).strip().lower() in ("1", "true", "yes"))
            if (_env_offscreen is not None)
            else bool(_opts.get("offscreen_plugins", False))
        )
        # Headless auto-detect (Linux/macOS only): if no DISPLAY and no WAYLAND_DISPLAY, force non-interactive (no Qt)
        try:
            import platform as _plat

            _is_windows = _plat.system().lower().startswith("win")
        except Exception:
            _is_windows = False
        if not _is_windows and (
            not _os.environ.get("DISPLAY") and not _os.environ.get("WAYLAND_DISPLAY")
        ):
            _noninteractive = True
        if _noninteractive:
            _os.environ["PYCOMPILER_NONINTERACTIVE"] = "1"
        # Offscreen is opt-in only (config/env). No auto-offscreen by default.
        if _offscreen and "QT_QPA_PLATFORM" not in _os.environ:
            _os.environ["QT_QPA_PLATFORM"] = "offscreen"
    except Exception:
        pass
    # Optionally initialize a minimal Qt application so plugins can show message boxes in sandbox
    try:
        _opts2 = (
            dict(config or {}).get("options", {}) if isinstance(config, dict) else {}
        )
        _env_allow = _os.environ.get("PYCOMPILER_SANDBOX_DIALOGS")
        _allow_dialogs = (
            (str(_env_allow).strip().lower() in ("1", "true", "yes"))
            if (_env_allow is not None)
            else bool(_opts2.get("allow_sandbox_dialogs", True))
        )
        # Respect non-interactive/headless
        if _allow_dialogs and (
            str(_os.environ.get("PYCOMPILER_NONINTERACTIVE", ""))
        ).strip().lower() not in (
            "1",
            "true",
            "yes",
        ):
            # Wayland fractional scaling safety
            _os.environ.setdefault("QT_WAYLAND_DISABLE_FRACTIONAL_SCALE", "1")
            try:
                from PySide6.QtWidgets import QApplication as _QApp  # type: ignore
            except Exception:
                try:
                    from PyQt5.QtWidgets import QApplication as _QApp  # type: ignore
                except Exception:
                    _QApp = None  # type: ignore
            if _QApp is not None:
                try:
                    if _QApp.instance() is None:
                        _sandbox_qapp = _QApp(
                            []
                        )  # noqa: F841 - keep reference alive during worker
                except Exception:
                    pass
    except Exception:
        pass
    # Enforce API_SDK.progress usage: block direct Qt QProgressDialog in plugins
    try:
        _os.environ["PYCOMPILER_ENFORCE_SDK_PROGRESS"] = "1"
    except Exception:
        pass
    try:
        from PySide6 import QtWidgets as _QtW2  # type: ignore

        class _NoDirectProgressDialog:  # type: ignore
            def __init__(self, *args, **kwargs) -> None:
                raise RuntimeError(
                    "Plugins must use API_SDK.progress(...) instead of PySide6.QProgressDialog"
                )

        try:
            _QtW2.QProgressDialog = _NoDirectProgressDialog  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        try:
            from PyQt5 import QtWidgets as _QtW2  # type: ignore

            class _NoDirectProgressDialog:  # type: ignore
                def __init__(self, *args, **kwargs) -> None:
                    raise RuntimeError(
                        "Plugins must use API_SDK.progress(...) instead of PyQt.QProgressDialog"
                    )

            try:
                _QtW2.QProgressDialog = _NoDirectProgressDialog  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            pass
    # Apply resource limits (POSIX) if configured
    try:
        _opts3 = (
            dict(config or {}).get("options", {}) if isinstance(config, dict) else {}
        )
        _limits = _opts3.get("plugin_limits", {}) if isinstance(_opts3, dict) else {}
        _mem_mb = int(_limits.get("mem_mb", 0))
        _cpu_s = int(_limits.get("cpu_time_s", 0))
        _nofile = int(_limits.get("nofile", 0))
        _fsize_mb = int(_limits.get("fsize_mb", 0))
        try:
            import resource as _res  # POSIX only

            def _set(limit, soft, hard):
                try:
                    _res.setrlimit(limit, (soft, hard))
                except Exception:
                    pass

            if _mem_mb > 0:
                _set(_res.RLIMIT_AS, _mem_mb * 1024 * 1024, _mem_mb * 1024 * 1024)
            if _cpu_s > 0:
                _set(_res.RLIMIT_CPU, _cpu_s, _cpu_s)
            if _nofile > 0:
                _set(_res.RLIMIT_NOFILE, _nofile, _nofile)
            if _fsize_mb > 0:
                _set(
                    _res.RLIMIT_FSIZE,
                    _fsize_mb * 1024 * 1024,
                    _fsize_mb * 1024 * 1024,
                )
        except Exception:
            pass
    except Exception:
        pass
    try:
        spec = _ilu.spec_from_file_location(
            "bcasl_sandbox_module",
            module_path,
            submodule_search_locations=[str(_Path(module_path).parent)],
        )
        if spec is None or spec.loader is None:
            raise ImportError("spec invalide")
        module = _ilu.module_from_spec(spec)
        _sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        # Récupérer PLUGIN ou fallback via bcasl_register
        plg = getattr(module, "PLUGIN", None)
        if plg is None or getattr(getattr(plg, "meta", None), "id", None) != plugin_id:
            try:
                # Fallback: ré-enregistrer dans un gestionnaire temporaire
                from bcasl import PreCompileContext as _PCC

                mgr = BCASL(
                    _Path(project_root), config=config, sandbox=False
                )  # pas de sandbox récursif
                if hasattr(module, "bcasl_register") and callable(
                    getattr(module, "bcasl_register")
                ):
                    module.bcasl_register(mgr)
                rec = getattr(mgr, "_registry", {}).get(plugin_id)
                if rec is None:
                    raise RuntimeError(
                        f"Plugin '{plugin_id}' introuvable dans le module"
                    )
                plg = rec.plugin
            except Exception as ex:
                raise RuntimeError(f"Impossible d'instancier le plugin: {ex}")
        # Exécution
        from bcasl import PreCompileContext as _PCC

        ctx = _PCC(_Path(project_root), config=dict(config or {}))
        t0 = _time.perf_counter()
        plg.on_pre_compile(ctx)
        dur = (_time.perf_counter() - t0) * 1000.0
        q.put({"ok": True, "error": "", "duration_ms": dur})
    except Exception:
        q.put({"ok": False, "error": _tb.format_exc(), "duration_ms": 0.0})
