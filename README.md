# 🚀 PyCompiler ARK++

> **Comprehensive Python compilation toolkit** with modular architecture, security features, and extensible plugin system.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/raidos23?label=Sponsor&logo=github)](https://github.com/sponsors/raidos23)

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
- **Location**: `Plugins/BCASL/`

#### 🔧 **ACASL (After Compilation Advanced System Loader)**
- **Post-compilation automation** for packaging, signing, and deployment
- **Location**: `Plugins/ACASL/`

#### 🏭 **Compilation Engines**
- Modular engine system with SDK for custom engines
- **Location**: `Core/Engines/`

## 🚀 Quick Start

```bash
git clone https://github.com/raidos23/PyCompiler-ARK-Professional.git
cd PyCompiler-ARK-Professional
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate sur Windows
pip install -r requirements.txt -c constraints.txt
python main.py