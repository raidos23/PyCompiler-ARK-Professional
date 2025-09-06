# Upgrade Guide - PyCompiler ARK++ 3.2.3

This guide helps you upgrade your development environment and projects to benefit from the new quality and security features.

## Summary of Improvements

### 🔧 CI/CD and Quality
- Restructured CI/CD pipeline with separate jobs (lint, format, types, tests)
- Pre-commit hooks with black, ruff, mypy, bandit
- Improved coverage reporting (e.g., Codecov)
- Automated security scanning

### 🔒 Security and Dependencies
- Dependency management with constraints.txt
- SBOM (Software Bill of Materials) generation
- Security auditing with pip-audit, safety, bandit
- ACASL plugins for code signing

### 📋 Governance
- Security policy (SECURITY.md)
- Code of Conduct (CODE_OF_CONDUCT.md)
- Contribution guide (CONTRIBUTING.md)
- Official support matrix

## Step-by-Step Migration

### 1. Update Your Development Environment

#### Install New Tools
```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install new quality tools
pip install black ruff mypy bandit pip-audit safety cyclonedx-py pre-commit

# Configure pre-commit
pre-commit install
```

#### Update Dependencies
```bash
# Install with new constraints
pip install -r requirements.txt -c constraints.txt

# Check vulnerabilities
pip-audit -r requirements.txt
safety check -r requirements.txt
```

### 2. Configure Quality Tools

#### Pre-commit Hooks
Pre-commit hooks are now configured automatically. To run them manually:
```bash
# Run all hooks
pre-commit run --all-files

# Run specific hooks
pre-commit run black --all-files
pre-commit run ruff --all-files
```

#### Code Formatting
```bash
# Format all code
black .
ruff format .

# Style checks
ruff check .
mypy utils API_SDK engine_sdk bcasl acasl
```

### 3. Update Existing Projects

#### pyproject.toml Configuration
If you have an existing project, add these sections to your `pyproject.toml`:

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

#### GitHub Actions Workflows
If you use GitHub Actions, update your workflows to the new structure:

```yaml
# Quality job example
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

### 4. Security and Compliance

#### Security Audit
Run these commands regularly:
```bash
# Dependency audit
pip-audit -r requirements.txt

# Source code security checks
bandit -r utils API_SDK engine_sdk bcasl acasl

# Vulnerability check
safety check -r requirements.txt
```

#### SBOM Generation
To generate an SBOM for your project:
```bash
# CycloneDX SBOM
cyclonedx-py -r requirements.txt -o sbom.json

# Or use the ACASL plugin
# Configure the sbom_generator plugin in your workspace configuration
```

### 5. Plugin Development

#### New ACASL Plugins
Two new plugins are available:

1. **Code Signing** (`API/code_signing`)
   - Cross-platform signing (Windows, macOS, Linux)
   - Supports Authenticode, codesign, GPG

2. **SBOM Generator** (`API/sbom_generator`)
   - Automatic SBOM generation
   - CycloneDX, SPDX, and custom formats

#### Plugin Configuration
Add to your configuration:
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

### 6. Tests and Validation

#### New Security Tests
Add security tests to your suite:
```python
# tests/test_security.py
def test_no_hardcoded_secrets():
    """Ensure there are no hardcoded secrets."""
    # Use bandit or custom regex checks
    pass

def test_input_validation():
    """Validate input sanitization."""
    pass
```

#### Compliance Tests
```bash
# Run all tests with coverage
pytest --cov=utils --cov=API_SDK --cov=engine_sdk --cov=bcasl --cov=acasl

# Security-specific tests
pytest tests/security/
```

## Troubleshooting

### Formatting Errors
```bash
# If black or ruff fail
black --diff .    # Preview changes
ruff check --fix .  # Autofix
```

### MyPy Type Errors
```bash
# Temporarily ignore specific errors
# type: ignore

# Or configure in pyproject.toml
[tool.mypy]
ignore_missing_imports = true
```

### Pre-commit Issues
```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install

# Update hooks
pre-commit autoupdate
```

### Bandit Security Errors
```bash
# See details
bandit -r . -f json

# Ignore specific rules
# nosec B101
```

## Best Practices

### Daily Development
1. Before each commit: pre-commit hooks run automatically
2. Run tests regularly: `pytest` before pushing
3. Weekly security audit with `pip-audit` and `safety`
4. Monthly dependency updates with security checks

### Dependency Management
1. Use constraints.txt for reproducible builds
2. Audit new dependencies regularly
3. Document changes in CHANGELOG.md
4. Test on all supported platforms

### Security
1. Never commit secrets (use .gitignore)
2. Sign production code
3. Generate SBOMs for traceability
4. Monitor GitHub security alerts

## Additional Resources

### Documentation
- [SECURITY.md](../SECURITY.md) - Security Policy
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution Guide
- [SUPPORTED_MATRIX.md](../SUPPORTED_MATRIX.md) - Supported Platforms

### Tools
- [Black](https://black.readthedocs.io/) - Code formatter
- [Ruff](https://docs.astral.sh/ruff/) - Fast linter
- [MyPy](https://mypy.readthedocs.io/) - Type checker
- [Bandit](https://bandit.readthedocs.io/) - Python security
- [Pre-commit](https://pre-commit.com/) - Git hooks

### Support
- GitHub Issues: for bugs and feature requests
- Discussions: for general questions
- Security: ague.samuel27@gmail.com for vulnerabilities

## Migration Checklist

- [ ] Development environment updated
- [ ] Pre-commit hooks installed and configured
- [ ] Code formatted with black and ruff
- [ ] Types validated with mypy
- [ ] Security tests added
- [ ] SBOM generated and reviewed
- [ ] Documentation updated
- [ ] CI/CD updated with new jobs
- [ ] Training completed on new tools
- [ ] Release process updated

---

This guide will be updated with each major release. For specific questions, see the documentation or open an issue.