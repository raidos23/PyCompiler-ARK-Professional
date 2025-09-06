# Guide de Contribution - PyCompiler ARK++ 3.2.3

Merci de votre intérêt pour contribuer à PyCompiler ARK++ ! Ce guide vous aidera à comprendre comment participer efficacement au développement du projet.

## Table des Matières

- [Code de Conduite](#code-de-conduite)
- [Comment Contribuer](#comment-contribuer)
- [Configuration de l'Environnement](#configuration-de-lenvironnement)
- [Processus de Développement](#processus-de-développement)
- [Standards de Code](#standards-de-code)
- [Tests](#tests)
- [Documentation](#documentation)
- [Processus de Review](#processus-de-review)
- [Types de Contributions](#types-de-contributions)

## Code de Conduite

Ce projet adhère au [Code de Conduite du Contributeur](CODE_OF_CONDUCT.md). En participant, vous vous engagez à respecter ce code. Veuillez signaler tout comportement inacceptable à conduct@pycompiler-ark.org.

## Comment Contribuer

### Signaler des Bugs

Avant de créer un rapport de bug :
- Vérifiez que le bug n'a pas déjà été signalé dans les [Issues](https://github.com/your-org/pycompiler-ark/issues)
- Vérifiez que vous utilisez une version supportée (voir [SUPPORTED_MATRIX.md](SUPPORTED_MATRIX.md))

Pour signaler un bug :
1. Utilisez le template d'issue "Bug Report"
2. Incluez des informations détaillées sur votre environnement
3. Fournissez des étapes de reproduction claires
4. Ajoutez des logs ou captures d'écran si pertinents

### Proposer des Fonctionnalités

Pour proposer une nouvelle fonctionnalité :
1. Vérifiez qu'elle n'existe pas déjà dans les issues ou la roadmap
2. Créez une issue avec le template "Feature Request"
3. Décrivez clairement le problème que cela résoudrait
4. Proposez une solution ou des alternatives
5. Discutez avec la communauté avant de commencer l'implémentation

### Contribuer au Code

1. **Fork** le repository
2. **Clone** votre fork localement
3. **Créez** une branche pour votre fonctionnalité (`git checkout -b feature/ma-fonctionnalite`)
4. **Commitez** vos changements (`git commit -am 'Ajoute ma fonctionnalité'`)
5. **Push** vers la branche (`git push origin feature/ma-fonctionnalite`)
6. **Créez** une Pull Request

## Configuration de l'Environnement

### Prérequis

- Python 3.10+ (recommandé : 3.11)
- Git
- Un éditeur de code (VS Code recommandé)

### Installation

```bash
# Cloner le repository
git clone https://github.com/your-org/pycompiler-ark.git
cd pycompiler-ark

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou
.venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt -c constraints.txt

# Installer les outils de développement
pip install pre-commit black ruff mypy pytest

# Configurer pre-commit
pre-commit install
```

### Vérification de l'Installation

```bash
# Tester que tout fonctionne
python main.py --version
python -m pytest tests/ -v
```

## Processus de Développement

### Workflow Git

1. **Branches principales** :
   - `main` : Code stable et prêt pour la production
   - `develop` : Branche de développement active

2. **Branches de fonctionnalités** :
   - Format : `feature/description-courte`
   - Basées sur `develop`
   - Mergées via Pull Request

3. **Branches de correction** :
   - Format : `fix/description-du-bug`
   - Basées sur `main` pour les hotfixes critiques
   - Basées sur `develop` pour les corrections normales

4. **Branches de release** :
   - Format : `release/x.y.z`
   - Créées depuis `develop`
   - Mergées dans `main` et `develop`

### Messages de Commit

Utilisez le format [Conventional Commits](https://www.conventionalcommits.org/) :

```
type(scope): description courte

Description plus détaillée si nécessaire.

Fixes #123
```

Types acceptés :
- `feat`: Nouvelle fonctionnalité
- `fix`: Correction de bug
- `docs`: Documentation uniquement
- `style`: Changements de formatage
- `refactor`: Refactoring sans changement fonctionnel
- `test`: Ajout ou modification de tests
- `chore`: Maintenance, outils, etc.

Exemples :
```
feat(acasl): ajoute support pour la signature de code Windows
fix(bcasl): corrige le chargement des plugins sur macOS
docs(api): met à jour la documentation de l'API SDK
```

## Standards de Code

### Formatage

- **Black** : Formatage automatique du code Python
- **Ruff** : Linting et vérifications de style
- **isort** : Tri des imports (intégré dans Ruff)

```bash
# Formater le code
black .
ruff format .

# Vérifier le style
ruff check .
```

### Type Hints

- Utilisez les type hints pour toutes les fonctions publiques
- Utilisez `mypy` pour la vérification des types
- Préférez les types génériques modernes (`list[str]` au lieu de `List[str]`)

```python
def process_files(files: list[str]) -> dict[str, bool]:
    """Traite une liste de fichiers et retourne le statut."""
    return {file: True for file in files}
```

### Documentation

- Docstrings au format Google/NumPy
- Documentation des paramètres et valeurs de retour
- Exemples d'utilisation pour les fonctions complexes

```python
def compile_project(source_path: str, output_path: str, options: dict[str, Any]) -> bool:
    """Compile un projet Python.

    Args:
        source_path: Chemin vers le code source
        output_path: Chemin de sortie pour les artefacts
        options: Options de compilation

    Returns:
        True si la compilation réussit, False sinon

    Raises:
        CompilationError: Si la compilation échoue

    Example:
        >>> compile_project("/src", "/dist", {"optimize": True})
        True
    """
```

### Structure du Code

- Suivez les principes SOLID
- Préférez la composition à l'héritage
- Utilisez des noms descriptifs
- Gardez les fonctions courtes et focalisées
- Séparez les préoccupations

## Tests

### Types de Tests

1. **Tests unitaires** : Testent des fonctions/classes isolées
2. **Tests d'intégration** : Testent l'interaction entre composants
3. **Tests fonctionnels** : Testent des scénarios utilisateur complets

### Écriture des Tests

```python
import pytest
from unittest.mock import Mock, patch

def test_compile_project_success():
    """Test que la compilation réussit avec des paramètres valides."""
    # Arrange
    source_path = "/valid/source"
    output_path = "/valid/output"
    options = {"optimize": True}

    # Act
    result = compile_project(source_path, output_path, options)

    # Assert
    assert result is True

def test_compile_project_invalid_source():
    """Test que la compilation échoue avec un chemin source invalide."""
    with pytest.raises(CompilationError):
        compile_project("/invalid/source", "/output", {})
```

### Exécution des Tests

```bash
# Tous les tests
pytest

# Tests avec couverture
pytest --cov=utils --cov=API_SDK --cov=engine_sdk --cov=bcasl --cov=acasl

# Tests spécifiques
pytest tests/test_bcasl.py::test_plugin_loading

# Tests en mode verbose
pytest -v
```

### Couverture de Code

- Objectif : ≥ 80% de couverture
- Focalisez sur la couverture des branches critiques
- Excluez les fichiers de test et d'interface utilisateur

## Documentation

### Types de Documentation

1. **Code** : Docstrings et commentaires inline
2. **API** : Documentation des interfaces publiques
3. **Guides** : Tutoriels et guides d'utilisation
4. **Architecture** : Documentation technique interne

### Mise à Jour de la Documentation

- Mettez à jour la documentation avec chaque changement d'API
- Ajoutez des exemples pour les nouvelles fonctionnalités
- Vérifiez que les liens fonctionnent
- Testez les exemples de code

## Processus de Review

### Avant de Soumettre

- [ ] Les tests passent localement
- [ ] Le code est formaté (black, ruff)
- [ ] Les types sont vérifiés (mypy)
- [ ] La documentation est mise à jour
- [ ] Les commits suivent les conventions
- [ ] La branche est à jour avec develop

### Critères de Review

Les reviewers vérifieront :
- **Fonctionnalité** : Le code fait-il ce qu'il est censé faire ?
- **Tests** : Y a-t-il des tests appropriés ?
- **Performance** : Y a-t-il des problèmes de performance ?
- **Sécurité** : Y a-t-il des vulnérabilités potentielles ?
- **Maintenabilité** : Le code est-il lisible et maintenable ?
- **Compatibilité** : Cela casse-t-il la compatibilité existante ?

### Processus de Review

1. **Soumission** : Créez une PR avec une description claire
2. **CI/CD** : Attendez que tous les checks passent
3. **Review** : Les mainteneurs examinent le code
4. **Feedback** : Adressez les commentaires des reviewers
5. **Approbation** : Au moins un mainteneur doit approuver
6. **Merge** : Un mainteneur merge la PR

## Types de Contributions

### Code

- Nouvelles fonctionnalités
- Corrections de bugs
- Améliorations de performance
- Refactoring

### Documentation

- Guides d'utilisation
- Documentation API
- Exemples de code
- Traductions

### Tests

- Tests unitaires
- Tests d'intégration
- Tests de performance
- Tests de sécurité

### Plugins

- Plugins BCASL
- Plugins ACASL
- Engines de compilation
- Thèmes UI

### Infrastructure

- Scripts de build
- Configuration CI/CD
- Outils de développement
- Automatisation

## Ressources Utiles

### Documentation
- [Architecture Overview](docs/architecture.md)
- [Plugin Development](docs/plugin_development.md)
- [API Reference](docs/api_reference.md)

### Outils
- [GitHub Issues](https://github.com/your-org/pycompiler-ark/issues)
- [Project Board](https://github.com/your-org/pycompiler-ark/projects)
- [Discussions](https://github.com/your-org/pycompiler-ark/discussions)

### Communication
- Email : contribute@pycompiler-ark.org
- Discord : [PyCompiler Community](https://discord.gg/pycompiler)
- Matrix : #pycompiler:matrix.org

## Questions Fréquentes

### Comment puis-je commencer à contribuer ?
Regardez les issues étiquetées "good first issue" ou "help wanted".

### Puis-je contribuer sans savoir programmer ?
Oui ! Vous pouvez aider avec la documentation, les tests, les traductions, ou signaler des bugs.

### Combien de temps faut-il pour qu'une PR soit reviewée ?
Généralement 2-5 jours ouvrables, selon la complexité.

### Comment puis-je devenir mainteneur ?
Contribuez régulièrement et de manière significative, puis contactez l'équipe.

---

Merci de contribuer à PyCompiler ARK++ ! Votre aide est précieuse pour améliorer l'outil pour toute la communauté.

*Dernière mise à jour : 06 septembre 2025*
