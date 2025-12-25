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

from .Base import (
    ACASL_PLUGIN_REGISTER_FUNC,
    _PluginRecord,
    AcPluginBase,
    ExecutionItem,
    ExecutionReport,
    PluginMeta,
    PostCompileContext,
    _logger,
)

import heapq
import importlib.util
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional


class ACASL:
    """Gestionnaire principal des plugins et de leur exécution après compilation."""

    def __init__(
        self,
        project_root: Path,
        config: Optional[dict[str, Any]] = None,
        *,
        sandbox: bool = False,
        plugin_timeout_s: float = 0.0,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.config = dict(config or {})
        self._registry: dict[str, _PluginRecord] = {}
        self._insert_counter = 0
        # Sandbox settings (ACASL n'utilise pas de multiprocessing)
        self.sandbox = bool(sandbox)
        # Timeout settings
        self.plugin_timeout_s = float(plugin_timeout_s)

    # API publique
    def add_plugin(self, plugin: AcPluginBase) -> None:
        if not isinstance(plugin, AcPluginBase):
            raise TypeError("Le plugin doit être une instance de AcPluginBase")
        pid = plugin.meta.id
        if pid in self._registry:
            raise ValueError(f"Plugin id déjà enregistré: {pid}")
        rec = _PluginRecord(plugin, self._insert_counter)
        self._registry[pid] = rec
        self._insert_counter += 1
        _logger.debug("Plugin ACASL ajouté: %s", plugin)

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
            mod_name = f"acasl_plugin_{pkg_dir.name}"
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
                reg = getattr(module, ACASL_PLUGIN_REGISTER_FUNC, None)
                if not callable(reg):
                    _logger.debug(
                        "Package %s: aucune fonction %s, ignoré",
                        pkg_dir.name,
                        ACASL_PLUGIN_REGISTER_FUNC,
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
                    _logger.info("Plugin ACASL chargé depuis package %s", pkg_dir.name)
            except Exception as exc:  # isolation
                msg = f"échec chargement: {exc}"
                errors.append((pkg_dir.name, msg))
                _logger.error("%s: %s", pkg_dir.name, msg)
        return count, errors

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

    def run_post_compile(
        self, ctx: Optional[PostCompileContext] = None
    ) -> ExecutionReport:
        """Exécute le hook 'on_post_compile' de tous les plugins actifs.

        Exécution séquentielle en respectant dépendances et priorités.
        Utilise du threading pour ne pas bloquer l'UI.
        """
        if ctx is None:
            ctx = PostCompileContext(self.project_root, config=self.config)
        else:
            ctx.project_root = Path(ctx.project_root).resolve()
            ctx.config = dict(self.config) | dict(ctx.config or {})

        report = ExecutionReport()

        # Construire graphe des dépendances des plugins actifs
        active_items = {pid: rec for pid, rec in self._registry.items() if rec.active}
        if not active_items:
            _logger.info("Aucun plugin ACASL actif")
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

        # Résoudre l'ordre d'exécution
        order: list[str] = []
        tmp_ready = [pid for pid, d in indeg.items() if d == 0]
        tmp_ready.sort(
            key=lambda x: (active_items[x].priority, active_items[x].insert_idx, x)
        )

        while tmp_ready:
            pid = tmp_ready.pop(0)
            order.append(pid)
            for ch in children[pid]:
                indeg[ch] -= 1
                if indeg[ch] == 0:
                    tmp_ready.append(ch)
                    tmp_ready.sort(
                        key=lambda x: (
                            active_items[x].priority,
                            active_items[x].insert_idx,
                            x,
                        )
                    )

        # Exécution séquentielle avec threading (non-bloquant pour l'UI)
        def _run_plugins():
            for pid in order:
                rec = active_items[pid]
                plg = rec.plugin
                start = time.perf_counter()
                try:
                    # Appeler on_post_compile avec timeout optionnel
                    timeout = self.plugin_timeout_s
                    if timeout and timeout > 0:
                        # Exécuter dans un thread avec timeout
                        holder = {"error": None}

                        def _call():
                            try:
                                plg.on_post_compile(ctx)
                            except Exception as e:
                                holder["error"] = e

                        th = threading.Thread(
                            target=_call, name=f"ACASL-{pid}", daemon=True
                        )
                        th.start()
                        th.join(timeout)
                        if th.is_alive():
                            # Timeout
                            duration_ms = (time.perf_counter() - start) * 1000.0
                            report.add(
                                ExecutionItem(
                                    plugin_id=pid,
                                    name=plg.meta.name,
                                    success=False,
                                    duration_ms=duration_ms,
                                    error=f"timeout après {timeout:.1f}s",
                                )
                            )
                            _logger.error(
                                "Plugin %s timeout après %.1fs", pid, timeout
                            )
                        else:
                            # Complété
                            duration_ms = (time.perf_counter() - start) * 1000.0
                            if holder["error"]:
                                report.add(
                                    ExecutionItem(
                                        plugin_id=pid,
                                        name=plg.meta.name,
                                        success=False,
                                        duration_ms=duration_ms,
                                        error=str(holder["error"]),
                                    )
                                )
                            else:
                                report.add(
                                    ExecutionItem(
                                        plugin_id=pid,
                                        name=plg.meta.name,
                                        success=True,
                                        duration_ms=duration_ms,
                                    )
                                )
                    else:
                        # Pas de timeout - exécution directe
                        plg.on_post_compile(ctx)
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

        # Lancer dans un thread daemon pour ne pas bloquer l'UI
        worker_thread = threading.Thread(
            target=_run_plugins, name="ACASL-Worker", daemon=True
        )
        worker_thread.start()

        return report
