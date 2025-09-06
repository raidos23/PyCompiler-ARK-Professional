# Guide de Mise à Niveau - PyCompiler ARK++ 3.2.3

Ce guide vous aide à mettre à niveau votre environnement de développement et vos projets pour tirer parti des nouvelles fonctionnalités de qualité et de sécurité.

## Résumé des Améliorations

### 🔧 CI/CD et Qualité
- Pipeline CI/CD restructuré avec jobs séparés (lint, format, types, tests)
- Pre-commit hooks avec black, ruff, mypy, bandit
- Couverture de code améliorée avec Codecov
- Scanning de sécurité automatisé

### 🔒 Sécurité et Dépendances
- Gestion des dépendances avec constraints.txt
- Génération SBOM (Software Bill of Materials)
- Audit de sécurité avec pip-audit, safety, bandit
- Plugins ACASL pour signature de code

### 📋 Gouvernance
- Documentation de sécurité (SECURITY.md)
- Code de conduite (CODE_OF_CONDUCT.md)
- Guide de contribution (CONTRIBUTING.md)
- Matrice de support officielle

## Migration Étape par Étape

### 1. Mise à Jour de l'Environnement de Développement

#### Installation des Nouveaux Outils
```bash
# Mettre à jour pip
python -m pip install --upgrade pip

# Installer les nouveaux outils de qualité
pip install black ruff mypy bandit pip-audit safety cyclonedx-py pre-commit

# Configurer pre-commit
pre-commit install
```

#### Mise à Jour des Dépendances
```bash
# Installer avec les nouvelles contraintes
pip install -r requirements.txt -c constraints.txt

# Vérifier les vulnérabilités
pip-audit -r requirements.txt
safety check -r requirements.txt
```

### 2. Configuration des Outils de Qualité

#### Pre-commit Hooks
Les hooks pre-commit sont maintenant configurés automatiquement. Pour les exécuter manuellement :
```bash
# Exécuter tous les hooks
pre-commit run --all-files

# Exécuter un hook spécifique
pre-commit run black --all-files
pre-commit run ruff --all-files
```

#### Formatage du Code
```bash
# Formater tout le code
black .
ruff format .

# Vérifier le style
ruff check .
mypy utils API_SDK engine_sdk bcasl acasl
```

### 3. Mise à Jour des Projets Existants

#### Configuration pyproject.toml
Si vous avez un projet existant, ajoutez ces sections à votre `pyproject.toml` :

```toml
[tool.black]
line-length = 120
target-version = ['py310', 'py311', 'py312']

[tool.ruff]
line-length = 120
target-version = "py310"
select = ["E", "F", "I", "W", "UP"]

[tool.mypy]
python_version = "3.10"
ignore_missing_imports = true
warn_unused_ignores = true

[tool.bandit]
exclude_dirs = ["tests", "venv", ".venv"]
```

#### Mise à Jour des Workflows GitHub Actions
Si vous utilisez GitHub Actions, mettez à jour vos workflows pour utiliser la nouvelle structure :

```yaml
# Exemple de job de qualité
quality:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        cache: 'pip'
    - run: pip install -r requirements.txt -c constraints.txt
    - run: ruff check .
    - run: black --check .
    - run: mypy .
```

### 4. Sécurité et Conformité

#### Audit de Sécurité
Exécutez régulièrement ces commandes :
```bash
# Audit des dépendances
pip-audit -r requirements.txt

# Vérification de sécurité du code
bandit -r utils API_SDK engine_sdk bcasl acasl

# Vérification des vulnérabilités
safety check -r requirements.txt
```

#### Génération SBOM
Pour générer un SBOM de votre projet :
```bash
# SBOM CycloneDX
cyclonedx-py -r requirements.txt -o sbom.json

# Ou utiliser le plugin ACASL
# Configurez le plugin sbom_generator dans votre configuration
```

### 5. Développement de Plugins

#### Nouveaux Plugins ACASL
Deux nouveaux plugins sont disponibles :

1. **Code Signing** (`acasl/code_signing`)
   - Signature multi-plateforme (Windows, macOS, Linux)
   - Support pour Authenticode, codesign, GPG

2. **SBOM Generator** (`acasl/sbom_generator`)
   - Génération automatique de SBOM
   - Formats CycloneDX, SPDX, et personnalisé

#### Configuration des Plugins
Ajoutez à votre configuration :
```yaml
acasl:
  plugins:
    - code_signing
    - sbom_generator
  
  code_signing:
    enabled: true
    windows:
      certificate_path: "path/to/cert.p12"
    macos:
      signing_identity: "Developer ID Application: Your Name"
    linux:
      gpg_key_id: "your-key-id"
  
  sbom:
    enabled: true
    cyclonedx: true
    custom: true
```

### 6. Tests et Validation

#### Nouveaux Tests de Sécurité
Ajoutez des tests de sécurité à votre suite :
```python
# tests/test_security.py
def test_no_hardcoded_secrets():
    """Vérifier qu'il n'y a pas de secrets en dur."""
    # Utiliser bandit ou des regex personnalisées
    pass

def test_input_validation():
    """Tester la validation des entrées."""
    pass
```

#### Tests de Conformité
```bash
# Exécuter tous les tests avec couverture
pytest --cov=utils --cov=API_SDK --cov=engine_sdk --cov=bcasl --cov=acasl

# Tests de sécurité spécifiques
pytest tests/security/
```

## Résolution des Problèmes Courants

### Erreurs de Formatage
```bash
# Si black ou ruff échouent
black --diff .  # Voir les changements
ruff check --fix .  # Corriger automatiquement
```

### Erreurs de Type MyPy
```bash
# Ignorer temporairement des erreurs
# type: ignore

# Ou configurer dans pyproject.toml
[tool.mypy]
ignore_missing_imports = true
```

### Problèmes de Pre-commit
```bash
# Réinstaller les hooks
pre-commit uninstall
pre-commit install

# Mettre à jour les hooks
pre-commit autoupdate
```

### Erreurs de Sécurité Bandit
```bash
# Voir les détails
bandit -r . -f json

# Ignorer des règles spécifiques
# nosec B101
```

## Bonnes Pratiques

### Développement Quotidien
1. **Avant chaque commit** : Les hooks pre-commit s'exécutent automatiquement
2. **Tests réguliers** : `pytest` avant de pousser
3. **Audit de sécurité** : Hebdomadaire avec `pip-audit` et `safety`
4. **Mise à jour des dépendances** : Mensuelle avec vérification de sécurité

### Gestion des Dépendances
1. **Utilisez constraints.txt** pour des builds reproductibles
2. **Auditez régulièrement** les nouvelles dépendances
3. **Documentez les changements** dans CHANGELOG.md
4. **Testez sur toutes les plateformes** supportées

### Sécurité
1. **Ne jamais committer de secrets** (utilisez .gitignore)
2. **Signer le code** en production
3. **Générer des SBOM** pour la traçabilité
4. **Suivre les alertes de sécurité** GitHub

## Ressources Supplémentaires

### Documentation
- [SECURITY.md](../SECURITY.md) - Politique de sécurité
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Guide de contribution
- [SUPPORTED_MATRIX.md](../SUPPORTED_MATRIX.md) - Plateformes supportées

### Outils
- [Black](https://black.readthedocs.io/) - Formatage de code
- [Ruff](https://docs.astral.sh/ruff/) - Linting rapide
- [MyPy](https://mypy.readthedocs.io/) - Vérification de types
- [Bandit](https://bandit.readthedocs.io/) - Sécurité Python
- [Pre-commit](https://pre-commit.com/) - Hooks Git

### Support
- **Issues GitHub** : Pour les bugs et demandes de fonctionnalités
- **Discussions** : Pour les questions générales
- **Security** : security@pycompiler-ark.org pour les vulnérabilités

## Checklist de Migration

- [ ] Environnement de développement mis à jour
- [ ] Pre-commit hooks installés et configurés
- [ ] Code formaté avec black et ruff
- [ ] Types vérifiés avec mypy
- [ ] Tests de sécurité ajoutés
- [ ] SBOM généré et vérifié
- [ ] Documentation mise à jour
- [ ] CI/CD configuré avec nouveaux jobs
- [ ] Équipe formée aux nouveaux outils
- [ ] Processus de release mis à jour

---

*Ce guide sera mis à jour avec chaque version majeure. Pour des questions spécifiques, consultez la documentation ou créez une issue.*