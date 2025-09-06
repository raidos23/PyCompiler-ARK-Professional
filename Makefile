# PyCompiler ARK++ Professional Edition - Makefile
# Professional development workflow automation

.PHONY: help install install-dev clean lint format type-check test security audit sbom build run

# Default target
help:
	@echo "🚀 PyCompiler ARK++ Professional Edition - Development Commands"
	@echo ""
	@echo "Setup Commands:"
	@echo "  install      Install production dependencies"
	@echo "  install-dev  Install development dependencies"
	@echo "  clean        Clean build artifacts and cache"
	@echo ""
	@echo "Quality Commands:"
	@echo "  lint         Run linting with ruff"
	@echo "  format       Format code with black and ruff"
	@echo "  type-check   Run type checking with mypy"
	@echo "  test         Run tests with pytest"
	@echo "  quality      Run all quality checks"
	@echo ""
	@echo "Security Commands:"
	@echo "  security     Run security scanning"
	@echo "  audit        Audit dependencies for vulnerabilities"
	@echo "  sbom         Generate Software Bill of Materials"
	@echo ""
	@echo "Build Commands:"
	@echo "  build        Build distribution packages"
	@echo "  run          Run the application"
	@echo "  launch       Run with professional launcher"
	@echo ""
	@echo "Git Commands:"
	@echo "  pre-commit   Install and run pre-commit hooks"
	@echo "  hooks        Run pre-commit on all files"

# Setup commands
install:
	@echo "📦 Installing production dependencies..."
	pip install -r requirements.txt -c constraints.txt

install-dev:
	@echo "🛠️  Installing development dependencies..."
	pip install -r requirements.txt -c constraints.txt
	pip install black ruff mypy pytest pytest-cov bandit pip-audit safety cyclonedx-py pre-commit
	pre-commit install

clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .coverage htmlcov/
	rm -rf .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Quality commands
lint:
	@echo "🔍 Running linting..."
	ruff check .

format:
	@echo "✨ Formatting code..."
	black .
	ruff format .

type-check:
	@echo "🔍 Running type checking..."
	mypy utils API_SDK engine_sdk bcasl acasl

test:
	@echo "🧪 Running tests..."
	pytest tests/ -v --tb=short

test-cov:
	@echo "🧪 Running tests with coverage..."
	pytest tests/ -v --cov=utils --cov=API_SDK --cov=engine_sdk --cov=bcasl --cov=acasl --cov-report=html --cov-report=term-missing

quality: lint type-check test
	@echo "✅ All quality checks completed"

# Security commands
security:
	@echo "🔒 Running security scanning..."
	bandit -r utils API_SDK engine_sdk bcasl acasl

audit:
	@echo "🔍 Auditing dependencies..."
	pip-audit -r requirements.txt
	safety check -r requirements.txt

sbom:
	@echo "📋 Generating SBOM..."
	cyclonedx-py -r requirements.txt -o sbom.json
	@echo "SBOM generated: sbom.json"

security-full: security audit sbom
	@echo "🔒 Complete security audit completed"

# Build commands
build:
	@echo "🏗️  Building distribution packages..."
	python -m build --sdist --wheel

run:
	@echo "🚀 Running PyCompiler ARK++..."
	python main.py

launch:
	@echo "🚀 Launching with professional launcher..."
	python launch.py

# Git commands
pre-commit:
	@echo "🪝 Installing pre-commit hooks..."
	pre-commit install

hooks:
	@echo "🪝 Running pre-commit on all files..."
	pre-commit run --all-files

# Development workflow
dev-setup: install-dev pre-commit
	@echo "🛠️  Development environment setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  make quality    # Run all quality checks"
	@echo "  make security   # Run security scanning"
	@echo "  make run        # Start the application"

# CI simulation
ci: lint type-check test security audit
	@echo "🤖 CI pipeline simulation completed"

# Release preparation
release-check: clean quality security-full build
	@echo "🚀 Release readiness check completed"
	@echo "Artifacts ready in dist/"

# Quick development cycle
dev: format lint test
	@echo "🔄 Quick development cycle completed"

# Full validation
validate: clean install-dev quality security-full build
	@echo "✅ Full validation completed - ready for production"
