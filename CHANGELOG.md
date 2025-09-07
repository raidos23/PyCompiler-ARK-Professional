# Changelog

All notable changes to PyCompiler ARK++ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added
- BCASL: bouton global Activer/Désactiver dans le chargeur API, persistant dans `bcasl.json` (`options.enabled`).
- cx_Freeze: case à cocher « Inclure encodings », normalisation des chemins, création automatique du dossier de sortie si invalide, amélioration du bouton target-dir (répertoire par défaut pertinent et synchro UI globale).
- ACASL: ouverture du dossier de sortie centralisée via l’orchestrateur, avec `get_output_directory` fourni par les moteurs; amélioration de la résolution du dossier de sortie.
- Documentation: mise à jour du guide de création de moteur et précisions i18n.

### Changed
- Installations de dépendances système (Linux/Windows) en arrière‑plan pour éviter le blocage de l’UI, messages utilisateur améliorés.
- Les moteurs n’ouvrent plus directement les dossiers de sortie; responsabilité confiée à ACASL.
- ACASL: logique de filtrage d’artifacts et d’ouverture de dossier rendue plus robuste.

### Fixed
- Bouton target-dir: chemin de départ du sélecteur et synchronisation avec le champ global corrigés.
- Icône cx_Freeze: avertissement propre si le chemin est invalide; pas d’échec silencieux.
- Réduction des doublons dans les arguments générés pour cx_Freeze.

### Security
- Moins de risques de blocage grâce à l’exécution non bloquante des commandes système (QProcess asynchrone).

## 3.2.3 - 2025-09-06

### Added
- Modular architecture with BCASL and ACASL plugin systems
- Comprehensive SDK for engine and API development
- Multi-platform support (Windows, macOS, Linux)
- GUI interface with PySide6
- Extensive documentation and developer guides

### Changed
- Improved plugin loading and management system
- Enhanced error handling and logging
- Better resource management and cleanup

### Fixed
- Various stability improvements
- Memory leak fixes in plugin system
- Cross-platform compatibility issues

### Security
- Input validation improvements
- Secure plugin loading mechanisms
- Enhanced subprocess handling
