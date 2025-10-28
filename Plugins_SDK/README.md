Plugins_SDK — Documentation rapide

Résumé
------
Plugins_SDK fournit un petit ensemble d'utilitaires destinés aux plugins (BCASL/ACASL) pour PyCompiler:

- gestion de configuration (module `config`)
- contexte d'exécution sûr pour plugins (module `context`)
- affichage de progression et boîtes de dialogue (module `progress`)
- façade principale et helpers (module `__init__`) : version, compat checks, `tr()`, `wrap_context()` etc.

La documentation ci-dessous décrit l'API publique, usages et exemples.

Installation
------------
Le SDK est inclus dans le dépôt sous `Plugins_SDK/`. Pour utiliser dans un plugin, importez:

```python
from Plugins_SDK import ConfigView, SDKContext, ProgressHandle, create_progress, tr, wrap_context
```

Si votre plugin est destiné à être compatible avec l'hôte, utilisez `wrap_context(pre_ctx)` depuis `__init__.py` pour obtenir un `SDKContext` à partir du contexte BCASL.

__init__.py (façade)
-------------------
Principaux éléments exposés:

- `__version__` : version du SDK (ex: "3.2.3").
- `ensure_min_sdk(required: str) -> bool` : vérifier si la version du SDK satisfait semver minimal.
- `tr(key_or_fr: str, en_or_fallback: str = "", *, plugin_file: Optional[str] = None) -> str` : traduction à la volée (mode simple FR/EN ou en utilisant les fichiers `languages/` du plugin).
- `wrap_context(pre_ctx, log_fn=None, engine_id=None) -> SDKContext` : convertir un contexte pré-compilation (BCASL) en `SDKContext` pratique.
- `wrap_post_context(post_ctx, log_fn=None) -> SDKContext` : convertir un contexte post-compilation (ACASL) en `SDKContext`.
- `run_command(cmd, timeout_s=60, cwd=None, env=None, shell=False) -> (rc, stdout, stderr)` : exécute une commande de façon sécurisée et capturée.
- `plugin(...)` : décorateur pour déclarer une classe plugin BCASL.

Exemple d'utilisation minimale (plugin BCASL):

```python
from Plugins_SDK import plugin, wrap_context

@plugin(id="mon_plugin", version="0.1.0", description="Example")
class MonPlugin(...):
    def run(self, pre_ctx):
        sdk = wrap_context(pre_ctx)
        sdk.log_info("Hello from plugin")
```

config.py
---------
Objets et fonctions exposés:

- `ConfigView(data: Optional[dict])` : vue sur un dict de configuration.
  - `get(key, default)` / `set(key, value)`
  - `for_plugin(plugin_id)` : retourne une `ConfigView` limitée au plugin
  - propriétés utilitaires : `required_files`, `file_patterns`, `exclude_patterns`, `engine_id`

- `load_workspace_config(workspace_root: Path) -> dict` : recherche et parse des fichiers `bcasl.*` / `.bcasl.*` (json/yaml/toml/ini/cfg).
- `ensure_settings_file(sctx, subdir='config', basename='settings', fmt='yaml', defaults=None, overwrite=False) -> Path` : crée un fichier de configuration de plugin dans l'espace de travail (utilise `sctx.safe_path` pour sécurité).

Exemple rapide:

```python
from Plugins_SDK.config import load_workspace_config, ConfigView
cfg = load_workspace_config(Path.cwd())
cv = ConfigView(cfg)
plugin_cfg = cv.for_plugin('mon_plugin')
print(plugin_cfg.get('option', 'default'))
```

context.py
----------
Classe principale : `SDKContext`

Constructeur typique (créé via `wrap_context`):

- `workspace_root: Path`
- `config_view: ConfigView` (ou équivalent)
- `log_fn: Optional[Callable[[str], None]]` — callback pour logs
- `engine_id`, `plugin_id`, `artifacts`, `allowed_dir` (ACASL scope)

Méthodes utiles:
- `log(msg)`, `log_info(msg)`, `log_warn(msg)`, `log_error(msg)`
- `show_msgbox(kind, title, text, default=None)` — liaison à `Plugins_SDK.progress.show_msgbox`
- `path(*parts)` / `safe_path(*parts)` — composition de chemins sécurisée
- `is_within_workspace(p)`, `is_within_allowed(p)`, `is_within_scope(p)` — vérifications de sécurité
- `open_text_safe(*parts, max_size_mb=5)` — lire un fichier texte en limitant la taille
- `iter_files(patterns, exclude=(), enforce_workspace=True, max_files=None)` — itérateur sur fichiers
- `iter_project_files(...)` — version optimisée basée sur `config_view.file_patterns`
- `write_text_atomic(*parts, text, create_dirs=True, backup=True)` — écriture atomique
- `replace_in_file(...)`, `batch_replace(...)` — remplacements sûrs
- `parallel_map(func, items, max_workers=None)` — map parallèle utile pour tâches CPU ou I/O

Sécurité et scopes:
- `allowed_dir` limite les opérations de fichiers (utilisé par ACASL post-compile)
- `safe_path` lève si tentative d'accès hors scope

progress.py
-----------
Fournit utilitaires d'UI/console pour feedback utilisateur:

- `show_msgbox(kind, title, text, parent=None, buttons=None, default=None)` — boîte de dialogue ou fallback console
- `ProgressHandle` — gestionnaire de progression (context manager compatible)
  - `create_progress(title, text, maximum=0, cancelable=False)` — crée un `ProgressHandle`
  - `progress(...)` — alias
  - `sys_msgbox_for_installing(subject, explanation=None, title='Installation required')` — demande d'autorisation pour installation nécessitant privilèges

Exemple:

```python
from Plugins_SDK.progress import create_progress
with create_progress('Indexation', 'Scanning files...', maximum=100) as p:
    for i, f in enumerate(files):
        p.update(i, f.name)
```

Traductions (i18n)
------------------
- Utiliser `Plugins_SDK.tr()` pour supporter FR/EN simplement. Pour plugins multi-langues, fournissez un dossier `languages/` avec `en.json`, `fr.json`, etc. et appelez `tr('key', 'Fallback', plugin_file=__file__)`.

Guides rapides
--------------
- Pour créer un plugin BCASL: implémentez la classe attendue par le host, décorez avec `@plugin(...)`, utilisez `wrap_context(pre_ctx)` au début pour obtenir `SDKContext`.
- Pour ACASL (post-compile): utilisez `wrap_post_context(post_ctx)` pour restreindre l'accès aux artefacts.
- Utilisez `SDKContext.safe_path()` et `is_within_scope()` pour éviter toute écriture hors du workspace ou du dossier de sortie.

Contribuer / tests
------------------
- Le SDK est autonome; tests unitaires peuvent simuler `pre_ctx` avec l'attribut `workspace_root`.
- Respecter la sécurité: `safe_path` et `allowed_dir` doivent être utilisés pour toutes opérations fichiers par défaut.

---

Si tu veux, je peux:
- générer automatiquement une doc Sphinx minimale à partir de ces modules,
- ajouter des exemples de tests unitaires pour `ConfigView` et `SDKContext`,
- produire un fichier `plugins_sdk_examples.py` montrant un plugin complet d'exemple.

Dis-moi ce que tu préfères que je fasse ensuite.
