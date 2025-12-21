# 🚀 PyCompiler ARK++

> **Comprehensive Python compilation toolkit** with modular architecture, security features, and extensible plugin system.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 🎯 Key Features

### 🔧 **Modular Plugin System**
- **BCASL**: Pre-compilation plugins for validation, preparation, and code transformation
- **ACASL**: Post-compilation automation (packaging, signing, publishing)
- **Sandboxed execution** with isolated environments
- **Dependency management** with topological sorting
- **Parallel execution** for independent plugins

### 🏭 **Multi-Engine Compilation**
- **PyInstaller**: Standard Python compilation with advanced options
- **Nuitka**: High-performance compilation with optimization flags
- **cx_Freeze**: Cross-platform support with minimal configuration
- **Extensible architecture**: Add custom compilation engines

### 🛠️ **Developer-Friendly SDKs**
- **Plugins_SDK**: Complete plugin development framework
- **Progress tracking**: Non-blocking UI updates with detailed metrics
- **Context management**: Secure workspace and resource handling
- **Internationalization**: Async i18n with plugin overlay support

## 🏗️ **Architecture Overview**

PyCompiler ARK++ provides a modular, extensible platform for Python compilation with comprehensive tooling and security features.

### **Core Components**

#### 🔧 **BCASL (Before Compilation Advanced System Loader)**
- **Pre-compilation plugins** for validation, preparation, and code transformation
- **Location**: `Plugins/<plugin_id>/` with `__init__.py`
- **Sandboxed execution** with resource limits and timeouts
- **Type-checked interfaces** with comprehensive error handling
- **Dependency resolution** with topological sorting
- **Parallel execution** for independent plugins

#### 🏭 **Multi-Engine Compilation**
- **PyInstaller**: Industry-standard with advanced options and auto-plugin detection
- **Nuitka**: High-performance compilation with optimization flags
- **cx_Freeze**: Cross-platform support with minimal configuration
- **Extensible**: Plugin architecture for additional compilation engines

#### 📦 **ACASL (After Compilation Advanced System Loader)**
- **Post-compilation automation** (packaging, signing, publishing)
- **Built-in plugins**: Code signing, SBOM generation, integrity checking
- **Isolated execution** environment with audit logging
- **CI/CD integration** and automated workflows

### **SDKs & Utilities**

#### 🛠️ **Plugins_SDK**
- **Progress tracking**: Non-blocking UI updates with detailed metrics
- **Context management**: Secure workspace and resource handling
- **Internationalization**: Async i18n with plugin overlay support
- **Dialog helpers**: User interaction utilities

#### 🔌 **Engine_SDK**
- **Base classes**: Standardized `CompilerEngine` interface
- **Auto-plugin detection**: Intelligent dependency analysis
- **Cross-platform utilities**: Path handling, subprocess management
- **Error handling**: Comprehensive logging and recovery mechanisms

## 🚀 **Quick Start**

### **Prerequisites**
- Python 3.10+ (3.11 recommended for performance)
- Git for version control
- Platform-specific tools for code signing (optional)

### **Installation**

```bash
# Clone the repository
git clone https://github.com/raidos23/pycompiler-ark-professional.git
cd pycompiler-ark-professional

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install with reproducible dependencies
pip install -r requirements.txt -c constraints.txt

# Install development tools (optional)
pip install -e ".[dev]"

# Setup pre-commit hooks (recommended)
pre-commit install
```

### **Basic Usage**

```bash
# Run the GUI application
python main.py

# Or use the command-line interface
python -m pycompiler_ark --help
```

### **Development Setup**

```bash
# Install all development dependencies
pip install -e ".[dev,security,docs]"

# Run quality checks
ruff check .                    # Linting
black --check .                 # Formatting
mypy .                         # Type checking
bandit -r .                    # Security scanning

# Run tests with coverage
pytest --cov=Core --cov=Plugins_SDK --cov=engine_sdk --cov=bcasl --cov=acasl --cov=cesl
```

## 🌍 **Platform Support**

### **Officially Supported Platforms**
| Platform | Versions | Architecture | Status |
|----------|----------|--------------|--------|
| **Ubuntu** | 20.04, 22.04, 24.04 LTS | x64 | ✅ Fully Supported |
| **Windows** | 10, 11 | x64 | ✅ Fully Supported |

### **Not Supported**
- **macOS**: Not officially supported (code contains macOS-specific utilities for future compatibility, but no active support)

### **Python Versions**
- **3.10**: ✅ Minimum supported version
- **3.11**: ✅ Recommended (performance optimizations)
- **3.12**: ✅ Latest stable support
- **3.13**: 🧪 Experimental support

See [SUPPORTED_MATRIX.md](SUPPORTED_MATRIX.md) for detailed compatibility information.

## 📚 **Documentation**

### **User Guides**
- [About SDKs](docs/about_sdks.md) - Overview of available SDKs
- [Create a Building Engine](docs/how_to_create_an_engine.md) - Engine development guide
- [Create an AC Plugin](docs/how_to_create_an_AC_plugin.md) - Post-compile plugin guide
- [Create a BC Plugin](docs/how_to_create_a_BC_plugin.md) - Pre-compile plugin guide


### **Developer Documentation**
- [Contributing](CONTRIBUTING.md) - How to contribute to the project

### **Operations**
- [Support Matrix](SUPPORTED_MATRIX.md) - Platform and version support

## 🤝 **Contributing**

We welcome contributions from the community! PyCompiler ARK++ follows structured development practices.

### **Development Process**
1. **Fork** the repository and create a feature branch
2. **Develop** with pre-commit hooks ensuring quality
3. **Test** across supported platforms and Python versions
4. **Document** changes and update relevant guides
5. **Submit** a pull request with comprehensive description

### **Quality Standards**
- **Code Coverage**: Minimum 80% for new features
- **Type Hints**: Required for all public APIs
- **Security Review**: Automated and manual security checks
- **Documentation**: User and developer documentation updates
- **Testing**: Unit, integration, and security tests

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📄 **License**

This project is licensed under the **GNU General Public License v3.0 only (GPL-3.0-only)**.

## 🆘 **Support**

### **Community Support**
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Community questions and ideas
- **Documentation**: Comprehensive guides and references

### **Security Issues**
For security vulnerabilities, please follow our [Security Policy](SECURITY.md):
- **Email**: ague.samuel27@gmail.com

## 🎉 **What's New**

PyCompiler ARK++ represents a comprehensive upgrade with:

### **Key Improvements**
- **Modular architecture**: Extensible plugin system with BCASL, ACASL and CESL
- **Enhanced security**: Comprehensive scanning and code signing
- **Complete documentation**: Guides for all major features
- **Modern tooling**: Latest Python practices and tools
- **Multi-platform support**: Ubuntu, Windows

### **Breaking Changes**
- **Python 3.10+**: Dropped support for Python 3.9 and below
- **New plugin system**: BCASL/ACASL/CESL replaces legacy plugin architecture
- **Enhanced APIs**: Backward compatibility with deprecation warnings

---

**PyCompiler ARK++** - *Comprehensive Python compilation toolkit with modular architecture and security features.*

Copyright (C) 2025 Samuel Amen Ague. Licensed under GPL-3.0-only.
