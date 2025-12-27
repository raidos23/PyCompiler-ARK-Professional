# Contributing to PyCompiler ARK++

Thank you for your interest in contributing to PyCompiler ARK++! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Plugin Development](#plugin-development)
- [Security](#security)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all. We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Trolling, insulting/derogatory comments, and personal or political attacks
- Public or private harassment
- Publishing others' private information without explicit permission
- Other conduct which could reasonably be considered inappropriate in a professional setting

## Getting Started

### Prerequisites

- Python 3.10 or higher (3.11 recommended)
- Git
- Virtual environment tool (venv, virtualenv, or conda)
- Basic knowledge of Python and Qt (for UI contributions)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/PyCompiler-ARK-Professional.git
   cd PyCompiler-ARK-Professional
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/raidos23/PyCompiler-ARK-Professional.git
   ```

## Development Setup

### 1. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 2. Install Dependencies

```bash
# Install runtime and development dependencies
pip install -r requirements.txt -c constraints.txt

# Install development tools
pip install black ruff mypy pytest pytest-cov pytest-qt bandit pre-commit
```

### 3. Setup Pre-commit Hooks

```bash
pre-commit install
```

This will automatically run code quality checks before each commit.

### 4. Verify Installation

```bash
# Run tests to verify setup
pytest Tests/

# Check code quality
ruff check .
black --check .
mypy Core/ bcasl/ Plugins_SDK/ engine_sdk/
```

## Development Workflow

### 1. Create a Feature Branch

Always create a new branch for your work:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only changes
- `refactor/` - Code refactoring
- `test/` - Adding or updating tests

### 2. Make Your Changes

- Write clean, readable code following our standards
- Add or update tests as needed
- Update documentation to reflect changes
- Commit often with clear, descriptive messages

### 3. Commit Guidelines

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Example:**
```
feat(bcasl): add timeout configuration for plugins

- Add plugin_timeout_s option to configuration
- Implement timeout enforcement in executor
- Add tests for timeout behavior

Closes #123
```

### 4. Keep Your Branch Updated

Regularly sync with upstream:

```bash
git fetch upstream
git rebase upstream/main
```

### 5. Push Your Changes

```bash
git push origin feature/your-feature-name
```

## Code Standards

### Python Style Guide

We follow PEP 8 with some modifications:

- **Line length**: 120 characters maximum
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Double quotes for strings, single quotes for dict keys
- **Imports**: Organized using `isort` (automatic with pre-commit)

### Code Quality Tools

All code must pass these checks:

```bash
# Linting with ruff
ruff check .

# Formatting with black
black .

# Type checking with mypy
mypy Core/ bcasl/ Plugins_SDK/ engine_sdk/

# Security scanning with bandit
bandit -r Core/ bcasl/ Plugins_SDK/
```

### Type Hints

- Required for all public APIs and functions
- Use `from __future__ import annotations` for forward references
- Example:
  ```python
  from __future__ import annotations
  
  def process_file(path: Path, options: dict[str, Any]) -> bool:
      """Process a file with given options."""
      pass
  ```

### Documentation Strings

All public modules, classes, and functions must have docstrings:

```python
def inject_header(file_path: Path, header: str) -> bool:
    """Inject license header into a Python file.
    
    Args:
        file_path: Path to the file to modify
        header: License header text to inject
        
    Returns:
        True if header was injected successfully, False otherwise
        
    Raises:
        FileNotFoundError: If file_path does not exist
        PermissionError: If file cannot be written
    """
    pass
```

### Error Handling

- Use specific exception types
- Provide meaningful error messages
- Log errors appropriately
- Clean up resources in `finally` blocks

```python
try:
    with open(file_path, 'r') as f:
        content = f.read()
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    raise
except Exception as e:
    logger.exception(f"Unexpected error processing {file_path}: {e}")
    raise
```

## Testing Guidelines

### Test Structure

```
Tests/
├── __init__.py
├── conftest.py              # Pytest configuration and fixtures
├── test_module_name.py      # Unit tests
└── workspace_support.py     # Test utilities
```

### Writing Tests

```python
import unittest
from pathlib import Path
from Core.ark_config_loader import load_ark_config

class TestArkConfigLoader(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path("test_workspace")
        self.test_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_load_config_returns_dict(self):
        """Test that load_ark_config returns a dictionary."""
        config = load_ark_config(str(self.test_dir))
        self.assertIsInstance(config, dict)
```

### Running Tests

```bash
# Run all tests
pytest Tests/

# Run with coverage
pytest --cov=Core --cov=bcasl --cov=Plugins_SDK Tests/

# Run specific test file
pytest Tests/test_ark_config_loader.py

# Run specific test
pytest Tests/test_ark_config_loader.py::TestArkConfigLoader::test_load_config

# Run with verbose output
pytest -v Tests/
```

### Test Coverage

- Minimum 80% coverage for new features
- 100% coverage for critical security code
- Generate coverage report:
  ```bash
  pytest --cov=Core --cov=bcasl --cov-report=html Tests/
  # Open htmlcov/index.html in browser
  ```

## Documentation

### Code Documentation

- **Docstrings**: Required for all public APIs
- **Comments**: Use for complex logic, not obvious code
- **Type hints**: Required for function signatures

### User Documentation

Located in `docs/` directory:

- **User guides**: Step-by-step instructions
- **API reference**: Detailed API documentation
- **Examples**: Code examples and tutorials

### Updating Documentation

When making changes:

1. Update relevant documentation files
2. Add examples if introducing new features
3. Update README.md if changing major features
4. Keep SUPPORTED_MATRIX.md current

## Pull Request Process

### Before Submitting

- [ ] All tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation is updated
- [ ] Commit messages are clear
- [ ] Branch is up to date with main

### Submitting a Pull Request

1. Push your branch to your fork
2. Go to the original repository
3. Click "New Pull Request"
4. Select your branch
5. Fill out the PR template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe tests performed

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Code follows style guide
- [ ] No breaking changes (or documented)
```

### PR Review Process

1. **Automated checks**: CI/CD runs tests and quality checks
2. **Code review**: Maintainers review your code
3. **Feedback**: Address any requested changes
4. **Approval**: Once approved, PR will be merged

### After Merge

1. Delete your feature branch
2. Pull latest main branch
3. Celebrate! 🎉

## Plugin Development

### BCASL Plugin Structure

```
Plugins/
└── YourPlugin/
    ├── __init__.py        # Plugin registration
    ├── plugin.py          # Main plugin logic
    ├── README.md          # Plugin documentation
    └── tests/             # Plugin tests
```

### Plugin Template

```python
# Plugins/YourPlugin/__init__.py
from bcasl import PluginMeta, BcPluginBase, PreCompileContext, register_plugin

class YourPlugin(BcPluginBase):
    """Your plugin description."""
    
    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            id="your-plugin",
            name="Your Plugin",
            version="1.0.0",
            description="What your plugin does",
            author="Your Name",
            tags=["validation", "preprocessing"]
        )
    
    def on_pre_compile(self, ctx: PreCompileContext) -> None:
        """Plugin logic executed before compilation."""
        self.log.info("Running Your Plugin")
        # Your code here

def bcasl_register(manager):
    """Register plugin with BCASL."""
    register_plugin(manager, YourPlugin)
```

### Plugin Guidelines

- Follow dependency graph for plugin ordering
- Use provided logging interfaces
- Handle errors gracefully
- Document configuration options
- Add comprehensive tests

See [docs/how_to_create_a_BC_plugin.md](docs/how_to_create_a_BC_plugin.md) for detailed guide.

## Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead:
1. Email: ague.samuel27@gmail.com
2. Include detailed description
3. Provide steps to reproduce
4. Suggest potential fixes if possible

### Security Best Practices

- Never commit secrets or credentials
- Sanitize user inputs
- Use secure file operations
- Follow principle of least privilege
- Keep dependencies updated

### Security Scanning

Run security checks:

```bash
# Scan with bandit
bandit -r Core/ bcasl/ Plugins_SDK/

# Check dependencies
pip-audit
safety check
```

## Questions or Need Help?

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and ideas
- **Email**: ague.samuel27@gmail.com

## License

By contributing to PyCompiler ARK++, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing to PyCompiler ARK++! Your efforts help make this project better for everyone.