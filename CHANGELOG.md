# Changelog

All notable changes to PyCompiler ARK++ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Enhanced CI/CD pipeline with separate lint, format, types, and tests jobs
- Pre-commit hooks configuration with black, ruff, mypy, and bandit
- Comprehensive dependency management with constraints.txt
- SBOM (Software Bill of Materials) generation using cyclonedx-py
- Security scanning with pip-audit, safety, and bandit
- Supported platform matrix documentation
- Release process documentation with code signing procedures
- Governance documentation (SECURITY.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md)
- CODEOWNERS file for repository governance

### Changed
- Updated GitHub Actions workflows for better separation of concerns
- Enhanced requirements.txt with version ranges and development dependencies
- Improved pyproject.toml configuration for better tool integration

### Security
- Added automated security scanning in CI pipeline
- Implemented dependency vulnerability checking
- Added bandit security linting for Python code

## [3.2.3] - 2025-09-06

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

## [3.2.2] - 2023-12-01

### Fixed
- Critical bug in ACASL plugin execution
- Memory management issues in long-running operations
- UI responsiveness improvements

### Security
- Fixed potential code injection vulnerability in plugin system
- Enhanced input sanitization

## [3.2.1] - 2023-11-15

### Added
- Support for Python 3.12
- New ACASL plugins for code signing and packaging

### Changed
- Improved plugin discovery mechanism
- Better error messages and user feedback

### Fixed
- Plugin loading issues on Windows
- Configuration file parsing edge cases

## [3.2.0] - 2023-11-01

### Added
- ACASL (After Compilation Action Scripting Language) system
- Enhanced BCASL with new built-in functions
- Comprehensive plugin SDK
- Multi-engine support architecture

### Changed
- Major refactoring of core compilation engine
- Improved UI with better theme support
- Enhanced documentation structure

### Deprecated
- Legacy plugin API (will be removed in 4.0.0)

### Removed
- Support for Python 3.9 and below

### Fixed
- Numerous stability and performance improvements

### Security
- Enhanced plugin sandboxing
- Improved input validation across all modules

## [3.1.0] - 2023-06-01

### Added
- BCASL (Before Compilation Action Scripting Language) system
- Plugin architecture foundation
- Basic GUI interface

### Changed
- Complete rewrite of compilation pipeline
- Improved configuration management

## [3.0.0] - 2023-01-01

### Added
- Initial release of PyCompiler ARK++ 3.x series
- Core compilation functionality
- Basic plugin support
- Command-line interface

### Changed
- Complete architectural redesign from 2.x series

### Removed
- Legacy 2.x compatibility layer

---

## Release Notes Format

### Types of Changes
- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

### Version Links
- [Unreleased]: https://github.com/your-org/pycompiler-ark/compare/v3.2.3...HEAD
- [3.2.3]: https://github.com/your-org/pycompiler-ark/compare/v3.2.2...v3.2.3
- [3.2.2]: https://github.com/your-org/pycompiler-ark/compare/v3.2.1...v3.2.2
- [3.2.1]: https://github.com/your-org/pycompiler-ark/compare/v3.2.0...v3.2.1
- [3.2.0]: https://github.com/your-org/pycompiler-ark/compare/v3.1.0...v3.2.0
- [3.1.0]: https://github.com/your-org/pycompiler-ark/compare/v3.0.0...v3.1.0
- [3.0.0]: https://github.com/your-org/pycompiler-ark/releases/tag/v3.0.0
