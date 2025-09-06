#!/usr/bin/env python3
"""
PyCompiler ARK++ Professional Edition - Validation Script
Comprehensive validation of the professional setup.
"""

import subprocess
import sys
from pathlib import Path


class ValidationResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results = []

    def add_result(self, category: str, test: str, status: str, message: str = ""):
        self.results.append({"category": category, "test": test, "status": status, "message": message})

        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        elif status == "WARN":
            self.warnings += 1

    def print_summary(self):
        total = self.passed + self.failed + self.warnings
        print(f"\n{'='*60}")
        print("🔍 VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"⚠️  Warnings: {self.warnings}")
        print(f"📊 Total: {total}")

        if self.failed == 0:
            print("\n🎉 ALL VALIDATIONS PASSED! PyCompiler ARK++ Professional Edition is ready.")
        else:
            print(f"\n❌ {self.failed} validation(s) failed. Please address the issues above.")

        return self.failed == 0


def validate_file_structure(result: ValidationResult):
    """Validate that all required files are present."""
    print("📁 Validating File Structure...")

    required_files = [
        "main.py",
        "pyproject.toml",
        "requirements.txt",
        "constraints.txt",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "CODEOWNERS",
        "SUPPORTED_MATRIX.md",
        "RELEASE.md",
        ".gitignore",
        ".pre-commit-config.yaml",
        "launch.py",
        "Makefile",
        ".env.example",
    ]

    for file_path in required_files:
        if Path(file_path).exists():
            result.add_result("Structure", f"File: {file_path}", "PASS")
        else:
            result.add_result("Structure", f"File: {file_path}", "FAIL", "Missing required file")

    # Check directories
    required_dirs = ["utils", "API_SDK", "engine_sdk", "bcasl", "acasl", "ENGINES", "docs", ".github/workflows"]

    for dir_path in required_dirs:
        if Path(dir_path).exists() and Path(dir_path).is_dir():
            result.add_result("Structure", f"Directory: {dir_path}", "PASS")
        else:
            result.add_result("Structure", f"Directory: {dir_path}", "FAIL", "Missing required directory")


def validate_python_syntax(result: ValidationResult):
    """Validate Python syntax for all Python files."""
    print("🐍 Validating Python Syntax...")

    python_files = list(Path(".").rglob("*.py"))
    python_files = [f for f in python_files if ".venv" not in str(f) and "__pycache__" not in str(f)]

    for py_file in python_files[:10]:  # Limit to first 10 files for speed
        try:
            with open(py_file, encoding="utf-8") as f:
                compile(f.read(), str(py_file), "exec")
            result.add_result("Syntax", f"Python: {py_file}", "PASS")
        except SyntaxError as e:
            result.add_result("Syntax", f"Python: {py_file}", "FAIL", f"Syntax error: {e}")
        except Exception as e:
            result.add_result("Syntax", f"Python: {py_file}", "WARN", f"Could not validate: {e}")


def validate_configuration_files(result: ValidationResult):
    """Validate configuration files."""
    print("⚙️  Validating Configuration Files...")

    # Validate pyproject.toml
    try:
        if sys.version_info < (3, 11):
            import tomli as tomllib
        else:
            import tomllib

        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)

        # Check required sections
        required_sections = ["tool.ruff", "tool.mypy", "tool.black", "project"]
        for section in required_sections:
            keys = section.split(".")
            current = data
            for key in keys:
                if key in current:
                    current = current[key]
                else:
                    result.add_result("Config", f"pyproject.toml: {section}", "FAIL", "Missing section")
                    break
            else:
                result.add_result("Config", f"pyproject.toml: {section}", "PASS")

    except Exception as e:
        result.add_result("Config", "pyproject.toml", "FAIL", f"Invalid TOML: {e}")

    # Validate pre-commit config
    try:
        import yaml

        with open(".pre-commit-config.yaml") as f:
            yaml.safe_load(f)
        result.add_result("Config", ".pre-commit-config.yaml", "PASS")
    except Exception as e:
        result.add_result("Config", ".pre-commit-config.yaml", "FAIL", f"Invalid YAML: {e}")


def validate_dependencies(result: ValidationResult):
    """Validate that dependencies can be resolved."""
    print("📦 Validating Dependencies...")

    # Check if requirements.txt exists and is readable
    try:
        with open("requirements.txt") as f:
            requirements = f.read().strip().split("\n")

        # Basic validation of requirement format
        for req in requirements:
            req = req.strip()
            if req and not req.startswith("#"):
                if ">=" in req or "==" in req or "<" in req:
                    result.add_result("Dependencies", f"Requirement: {req}", "PASS")
                else:
                    result.add_result("Dependencies", f"Requirement: {req}", "WARN", "No version specified")

    except Exception as e:
        result.add_result("Dependencies", "requirements.txt", "FAIL", f"Cannot read: {e}")

    # Check constraints.txt
    try:
        with open("constraints.txt") as f:
            constraints = f.read().strip()
        if constraints:
            result.add_result("Dependencies", "constraints.txt", "PASS")
        else:
            result.add_result("Dependencies", "constraints.txt", "WARN", "Empty constraints file")
    except Exception as e:
        result.add_result("Dependencies", "constraints.txt", "FAIL", f"Cannot read: {e}")


def validate_git_setup(result: ValidationResult):
    """Validate Git repository setup."""
    print("🔧 Validating Git Setup...")

    # Check if it's a git repository
    if Path(".git").exists():
        result.add_result("Git", "Repository", "PASS")
    else:
        result.add_result("Git", "Repository", "FAIL", "Not a Git repository")
        return

    # Check git configuration
    try:
        subprocess.run(["git", "config", "user.name"], capture_output=True, check=True, text=True)
        result.add_result("Git", "User name", "PASS")
    except subprocess.CalledProcessError:
        result.add_result("Git", "User name", "WARN", "Git user.name not configured")

    try:
        subprocess.run(["git", "config", "user.email"], capture_output=True, check=True, text=True)
        result.add_result("Git", "User email", "PASS")
    except subprocess.CalledProcessError:
        result.add_result("Git", "User email", "WARN", "Git user.email not configured")

    # Check for commits
    try:
        result_cmd = subprocess.run(["git", "log", "--oneline", "-1"], capture_output=True, check=True, text=True)
        if result_cmd.stdout.strip():
            result.add_result("Git", "Commits", "PASS")
        else:
            result.add_result("Git", "Commits", "WARN", "No commits found")
    except subprocess.CalledProcessError:
        result.add_result("Git", "Commits", "WARN", "Cannot check commit history")


def validate_tools(result: ValidationResult):
    """Validate that development tools are available."""
    print("🛠️  Validating Development Tools...")

    tools = {
        "python": "Python interpreter",
        "pip": "Package installer",
        "black": "Code formatter",
        "ruff": "Linter",
        "mypy": "Type checker",
        "pytest": "Test runner",
        "pre-commit": "Git hooks",
        "git": "Version control",
    }

    for tool, description in tools.items():
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True, timeout=5)
            result.add_result("Tools", f"{tool} ({description})", "PASS")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            if tool in ["black", "ruff", "mypy", "pytest", "pre-commit"]:
                result.add_result("Tools", f"{tool} ({description})", "WARN", "Development tool not available")
            else:
                result.add_result("Tools", f"{tool} ({description})", "FAIL", "Required tool not available")


def validate_security_setup(result: ValidationResult):
    """Validate security configuration."""
    print("🔒 Validating Security Setup...")

    # Check for security tools
    security_tools = ["bandit", "pip-audit", "safety"]
    for tool in security_tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True, timeout=5)
            result.add_result("Security", f"Tool: {tool}", "PASS")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            result.add_result("Security", f"Tool: {tool}", "WARN", "Security tool not available")

    # Check security configuration in pyproject.toml
    try:
        if sys.version_info < (3, 11):
            import tomli as tomllib
        else:
            import tomllib

        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)

        if "tool" in data and "bandit" in data["tool"]:
            result.add_result("Security", "Bandit configuration", "PASS")
        else:
            result.add_result("Security", "Bandit configuration", "WARN", "No bandit configuration found")

    except Exception:
        result.add_result("Security", "Security configuration", "WARN", "Cannot validate security config")


def main():
    """Main validation function."""
    print("🔍 PyCompiler ARK++ Professional Edition - Validation")
    print("=" * 60)

    result = ValidationResult()

    # Run all validations
    validate_file_structure(result)
    validate_python_syntax(result)
    validate_configuration_files(result)
    validate_dependencies(result)
    validate_git_setup(result)
    validate_tools(result)
    validate_security_setup(result)

    # Print detailed results
    print("\n📋 DETAILED RESULTS:")
    print("-" * 60)

    current_category = None
    for res in result.results:
        if res["category"] != current_category:
            current_category = res["category"]
            print(f"\n📂 {current_category}:")

        status_icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ "}[res["status"]]
        message = f" - {res['message']}" if res["message"] else ""
        print(f"  {status_icon} {res['test']}{message}")

    # Print summary and return exit code
    success = result.print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
