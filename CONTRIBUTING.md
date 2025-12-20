# Contributing Guide - PyCompiler ARK++

Thank you for your interest in contributing to PyCompiler ARK++! This guide explains how to contribute effectively to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Environment Setup](#environment-setup)
- [Development Process](#development-process)
- [Code Standards](#code-standards)
- [Tests](#tests)
- [Documentation](#documentation)
- [Review Process](#review-process)
- [Contribution Types](#contribution-types)
- [Resources](#resources)
- [Communication](#communication)
- [FAQ](#faq)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code. Please report unacceptable behavior to: ague.samuel27@gmail.com.

## How to Contribute

### Report Bugs

Before opening an issue:
- Check that the bug hasn’t already been reported in [Issues](https://github.com/raidos23/PyCompiler-ARK-Professional/issues)
- Ensure you’re using a supported version (see [SUPPORTED_MATRIX.md](SUPPORTED_MATRIX.md))

To report a bug:
1. Use the "Bug Report" issue template
2. Include detailed information about your environment
3. Provide clear reproduction steps
4. Attach logs or screenshots when relevant

### Propose Features

1. Check if it already exists in open issues or the roadmap
2. Create an issue using the "Feature Request" template
3. Clearly describe the problem to solve
4. Propose a solution or alternatives
5. Discuss with the community before starting implementation

### Contribute Code

1. Fork the repository
2. Clone your fork locally
3. Create a feature branch (`git checkout -b feature/my-feature`)
4. Commit your changes (`git commit -am 'feat: add my feature'`)
5. Push the branch (`git push origin feature/my-feature`)
6. Open a Pull Request

## Environment Setup

### Prerequisites

- Python 3.10+ (recommended: 3.11)
- Git
- A code editor (VS Code recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/raidos23/PyCompiler-ARK-Professional.git
cd PyCompiler-ARK-Professional

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt -c constraints.txt

# Install dev tools
pip install pre-commit black ruff mypy pytest

# Configure pre-commit
pre-commit install
```

### Verify Installation

```bash
# Quick checks
python main.py --version
python -m pytest tests/ -v
```

## Development Process

### Git Workflow

1. Main branches:
   - `main`: Stable, production-ready code
   - `develop`: Active development branch

2. Feature branches:
   - Format: `feature/short-description`
   - Based on `develop`
   - Merged via Pull Request

3. Fix branches:
   - Format: `fix/bug-description`
   - Based on `main` for critical hotfixes
   - Based on `develop` for regular fixes

4. Release branches:
   - Format: `release/x.y.z`
   - Created from `develop`
   - Merged into `main` and `develop`

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description

More detailed description if needed.

Fixes #123
```

Accepted types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting changes
- `refactor`: Refactoring with no functional change
- `test`: Add or modify tests
- `chore`: Maintenance, tooling, etc.

Examples:
```
feat(acasl): add Windows code signing support
fix(bcasl): fix plugin loading on macOS
docs(api): update API SDK documentation
```

## Code Standards

### Formatting

- Black: automatic Python code formatting
- Ruff: linting and style checks
- isort: import sorting (via Ruff)

```bash
# Format code
black .
ruff format .

# Check style
ruff check .
```

### Type Hints

- Use type hints for all public functions
- Validate types with `mypy`
- Prefer modern generic types (`list[str]` instead of `List[str]`)

```python
def process_files(files: list[str]) -> dict[str, bool]:
    """Process a list of files and return success flags."""
    return {file: True for file in files}
```

### Documentation

- Docstrings in Google/NumPy style
- Document parameters and return values
- Provide examples for complex functions

```python
def compile_project(source_path: str, output_path: str, options: dict[str, Any]) -> bool:
    """Compile a Python project.

    Args:
        source_path: Path to the source code
        output_path: Output directory for artifacts
        options: Compilation options

    Returns:
        True if the compilation succeeds, False otherwise

    Raises:
        CompilationError: If compilation fails

    Example:
        >>> compile_project("/src", "/dist", {"optimize": True})
        True
    """
```

### Code Structure

- Follow SOLID principles
- Prefer composition over inheritance
- Use descriptive names
- Keep functions short and focused
- Separate concerns

## Tests

### Types of Tests

1. Unit tests: isolated functions/classes
2. Integration tests: interactions between components
3. Functional tests: end-user flows

### Writing Tests

```python
import pytest
from unittest.mock import Mock, patch

def test_compile_project_success():
    """Compilation succeeds with valid parameters."""
    source_path = "/valid/source"
    output_path = "/valid/output"
    options = {"optimize": True}
    result = compile_project(source_path, output_path, options)
    assert result is True

def test_compile_project_invalid_source():
    """Compilation fails with invalid source path."""
    with pytest.raises(CompilationError):
        compile_project("/invalid/source", "/output", {})
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=utils --cov=API_SDK --cov=engine_sdk --cov=bcasl --cov=acasl

# Specific tests
pytest tests/test_bcasl.py::test_plugin_loading

# Verbose
pytest -v
```

### Coverage

- Target: ≥ 80%
- Focus on critical branches and error paths
- Exclude test and UI files from coverage

## Documentation

### Types

1. Code: docstrings and inline comments
2. API: public interfaces
3. Guides: tutorials and how-tos
4. Architecture: internal technical docs

### Updates

- Update docs with each API change
- Add examples for new features
- Verify links
- Test code snippets

## Review Process

### Before Submitting

- [ ] Tests pass locally
- [ ] Code formatted (black, ruff)
- [ ] Types validated (mypy)
- [ ] Documentation updated
- [ ] Commits follow conventions
- [ ] Branch is up to date with `develop`

### Review Criteria

Reviewers will check:
- Functionality: Does the code do what it should?
- Tests: Are there appropriate tests?
- Performance: Any performance concerns?
- Security: Any potential vulnerabilities?
- Maintainability: Is the code readable and maintainable?
- Compatibility: Any breaking changes?

### Process

1. Submission: open a PR with a clear description
2. CI/CD: wait for all checks to pass
3. Review: maintainers review the code
4. Feedback: address review comments
5. Approval: at least one maintainer approves
6. Merge: a maintainer merges the PR

## Contribution Types

### Code

- New features
- Bug fixes
- Performance improvements
- Refactoring

### Documentation

- User guides
- API docs
- Code examples
- Translations (for user-facing docs only, not code/commit messages)

### Tests

- Unit tests
- Integration tests
- Performance tests
- Security tests

### Plugins

- BCASL plugins
- ACASL plugins
- Compilation engines
- Core Exetensions
- UI themes

### Infrastructure

- Build scripts
- CI/CD configuration
- Developer tooling
- Automation

## Resources

### Documentation
- [About SDKs](docs/about_sdks.md) - Overview of available SDKs
- [Create a Building Engine](docs/how_to_create_a_building_engine.md) - Engine development guide
- [Create an ACASL Plugin](docs/how_to_create_an_acasl_plugin.md) - Post-compile plugin guide
- [Create a BCASL Plugin](docs/how_to_create_a_bcasl_plugin.md) - Pre-compile plugin guide


### Tools
- [GitHub Issues](https://github.com/raidos23/PyCompiler-ARK-Professional/issues)
- [Project Board](https://github.com/raidos23/PyCompiler-ARK-Professional/projects)
- [Discussions](https://github.com/raidos23/PyCompiler-ARK-Professional/discussions)

## Communication

- Email: ague.samuel27@gmail.com


## FAQ

### How do I get started?
Look for issues labeled "good first issue" or "help wanted".

### Can I contribute without coding?
Yes! Help with documentation, tests, translations (user docs), or bug reports.

### How long does PR review take?
Typically 2–5 business days, depending on complexity.

### How do I become a maintainer?
Contribute regularly and meaningfully, then contact the team.

---

Thank you for contributing to PyCompiler ARK++! Your help improves the tool for the entire community.

*Last updated: 06 September 2025*
