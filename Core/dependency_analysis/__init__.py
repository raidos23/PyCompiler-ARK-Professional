
"""
Analyse des dépendances Python pour PyCompiler Pro++.
Inclut la détection, la suggestion et l'installation automatique des modules manquants.

Optimisations appliquées:
- Caching des résultats stdlib via @lru_cache
- Parallélisation des vérifications pip via ThreadPoolExecutor
- Utilisation de importlib.metadata au lieu de subprocess pip show
- Async I/O pour les opérations bloquantes

Statut: module utilisable pour une suggestion/installation basique. Les
fonctions d'auto-analyse avancée mentionnées dans la feuille de route ne sont
pas nécessaires à l'exécution et sont désactivées/neutralisées pour éviter tout
impact en production. Les entrées publiques référencées par l'UI (suggest_missing_dependencies)
sont conservées.
"""

from __future__ import annotations
from analyser import ( _install_next_dependency, _check_module_installed,
                      _is_stdlib_module, _on_dep_pip_finished, _on_dep_pip_output, suggest_missing_dependencies)


__all__ = ["_install_next_dependency", "_check_module_installed", "_is_stdlib_module", "_on_dep_pip_finished", "suggest_missing_dependencies", "_on_dep_pip_output"]
