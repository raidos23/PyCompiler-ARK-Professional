# Support Matrix

This document provides comprehensive compatibility information for PyCompiler ARK++.

## Operating Systems

### Officially Supported Platforms

| OS       | Versions                  | Architecture | Status          | Notes |
|----------|---------------------------|--------------|-----------------|-------|
| Ubuntu   | 20.04 LTS                 | x64          | ✅ Supported    | Long-term support, fully tested |
| Ubuntu   | 22.04 LTS                 | x64          | ✅ Supported    | Recommended for production |
| Ubuntu   | 24.04 LTS                 | x64          | ✅ Supported    | Latest LTS version |
| Windows  | 10                        | x64          | ✅ Supported    | Minimum Windows version |
| Windows  | 11                        | x64          | ✅ Supported    | Latest Windows version |
| macOS    | All versions              | x64/ARM64    | ❌ Not supported| No active support or testing |

### Platform-Specific Notes

#### Ubuntu/Linux
- Requires system packages: `python3-dev`, `build-essential` for Nuitka
- Qt platform plugin: Wayland or X11
- Tested on clean installations and Docker containers

#### Windows
- Visual C++ Build Tools recommended for Nuitka
- Windows Defender exclusions may be needed for compilation
- PowerShell execution policy may need adjustment

#### macOS
- Not officially supported
- Some utilities contain macOS-specific code for future compatibility
- Community contributions for macOS support are welcome

## Python Versions

### Version Support Status

| Python | Status         | Notes                                    |
|--------|----------------|------------------------------------------|
| 3.9    | ❌ Deprecated  | No longer supported as of v2.0           |
| 3.10   | ✅ Minimum     | Minimum supported version                |
| 3.11   | ✅ Recommended | Best performance and stability           |
| 3.12   | ✅ Stable      | Latest stable with full support          |
| 3.13   | 🧪 Experimental| Limited testing, may have issues         |

### Python Version Notes

- **3.10**: Baseline compatibility, all features work
- **3.11**: 10-25% performance improvement over 3.10
- **3.12**: Latest features, improved error messages
- **3.13**: Early support, use with caution in production

### Required Python Packages

Minimum versions are specified in `requirements.txt`:
- `PySide6 >= 6.8.0` (Python 3.13+)
- `PySide6 < 6.8` (Python < 3.13)
- `pytest >= 8.3.0` (Python 3.13+)
- `PyYAML >= 5.4.1, < 7.0.0`
- `psutil >= 5.9.0, < 6.0.0`

## Compilation Engines

### Engine Compatibility Matrix

| Engine      | Status | Ubuntu | Windows | Python 3.10+ | Notes |
|-------------|--------|--------|---------|--------------|-------|
| PyInstaller | ✅     | ✅     | ✅      | ✅           | Most widely used, good cross-platform support |
| Nuitka      | ✅     | ✅     | ✅      | ✅           | Best performance, requires C compiler |
| cx_Freeze   | ✅     | ✅     | ✅      | ✅           | Simple configuration, good for basic needs |

### Engine-Specific Requirements

#### PyInstaller
- No system dependencies
- Installed via pip in virtual environment
- Auto-detects hidden imports
- Version: Latest stable recommended

#### Nuitka
- **Ubuntu**: `gcc`, `g++`, `python3-dev`
- **Windows**: Visual Studio Build Tools or MinGW
- Longer compile time, better runtime performance
- Version: 1.8+ recommended

#### cx_Freeze
- **Ubuntu**: `python3-dev`
- **Windows**: No additional requirements
- Simple setup, good for straightforward projects
- Version: 6.15+ recommended

## UI Libraries and Frameworks

### Qt Bindings

| Binding  | Status          | Python 3.10+ | Notes                                    |
|----------|-----------------|--------------|------------------------------------------|
| PySide6  | ✅ Fully tested | ✅           | Official Qt binding, actively maintained |
| PyQt6    | ⚠️ Partial      | ✅           | Works but less tested                    |
| PyQt5    | ⚠️ Legacy       | ✅           | Limited support, not recommended         |

### UI Platform Support

| Platform | Status | Qt Backend | Notes |
|----------|--------|------------|-------|
| X11      | ✅     | xcb        | Default on most Linux systems |
| Wayland  | ✅     | wayland    | Modern Linux compositor |
| Windows  | ✅     | windows    | Native Windows backend |

## Development Tools

### Supported Development Environment

| Tool      | Minimum Version | Recommended | Purpose              |
|-----------|-----------------|-------------|----------------------|
| Git       | 2.25+           | Latest      | Version control      |
| pytest    | 8.0+            | 8.3+        | Testing framework    |
| black     | 23.0+           | Latest      | Code formatting      |
| ruff      | 0.1.0+          | Latest      | Linting              |
| mypy      | 1.0+            | Latest      | Type checking        |
| bandit    | 1.7+            | Latest      | Security scanning    |

### IDE Support

Tested and works well with:
- **VSCode**: Full support with Python extension
- **PyCharm**: Professional and Community editions
- **Vim/Neovim**: With LSP plugins
- **Sublime Text**: With Python packages

## Plugin System (BCASL)

### Plugin Compatibility

| Feature              | Status | Notes                                     |
|---------------------|--------|-------------------------------------------|
| Plugin loading      | ✅     | Dynamic loading from Plugins/ directory   |
| Sandboxed execution | ✅     | Isolated environments for security        |
| Dependency ordering | ✅     | Topological sort based on tags            |
| Parallel execution  | ✅     | Independent plugins run concurrently      |
| Plugin timeout      | ✅     | Configurable per-plugin timeout           |

### Built-in Plugins

| Plugin    | Status | Platform | Purpose                    |
|-----------|--------|----------|----------------------------|
| Cleaner   | ✅     | All      | Remove .pyc and cache dirs |
| More TBD  | 🚧     | All      | Additional plugins planned |

## Internationalization

### Language Support

| Language            | Code  | Status | Coverage |
|---------------------|-------|--------|----------|
| English             | en    | ✅     | 100%     |
| French              | fr    | ✅     | 100%     |
| German              | de    | ✅     | 90%      |
| Spanish             | es    | ✅     | 90%      |
| Portuguese (Brazil) | pt-BR | ✅     | 85%      |
| Russian             | ru    | ✅     | 85%      |
| Chinese (Simplified)| zh-CN | ✅     | 80%      |
| Japanese            | ja    | ✅     | 80%      |
| Korean              | ko    | ✅     | 75%      |

## Testing and CI/CD

### Test Coverage

| Component     | Coverage | Status |
|---------------|----------|--------|
| Core          | 85%      | ✅     |
| BCASL         | 82%      | ✅     |
| Plugins SDK   | 78%      | ✅     |
| Engine SDK    | 75%      | ⚠️     |

### CI/CD Platforms

| Platform       | Status | Usage                          |
|----------------|--------|--------------------------------|
| GitHub Actions | ✅     | Primary CI/CD for tests/builds |
| Local pytest   | ✅     | Development testing            |

## Known Limitations

### Current Limitations

1. **macOS Support**: Not officially supported, no active testing
2. **ARM Architecture**: Limited testing on ARM-based systems
3. **Python 3.13**: Experimental support, may have compatibility issues
4. **Legacy Python**: Python 3.9 and below not supported

### Planned Improvements

- Enhanced ARM64 support (Linux and potential macOS)
- Additional compilation engines (py2exe, py2app)
- More built-in BCASL plugins
- Improved internationalization coverage

## Version History

### Breaking Changes

- **v2.0**: Dropped Python 3.9 support, new BCASL plugin system
- **v2.0**: Minimum PySide6 version requirement updated

### Upgrade Guide

When upgrading from older versions:
1. Update Python to 3.10 or higher
2. Migrate legacy plugins to BCASL format
3. Update configuration files to new format
4. Review SUPPORTED_MATRIX.md for compatibility

## Support and Resources

### Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **Documentation**: [docs/](docs/) directory
- **Email**: ague.samuel27@gmail.com (security issues)

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code standards
- Testing requirements
- Pull request process

---

**Last Updated**: 2025-01-XX  
**Document Version**: 2.0  
**Project Version**: ARK++ v2.0
