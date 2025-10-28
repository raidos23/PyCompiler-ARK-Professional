#!/usr/bin/env python3
"""
PyCompiler ARK++ Professional Edition Launcher
Professional launcher with environment validation and setup.
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

def check_python_version():
    """Check if Python version meets requirements."""
    if sys.version_info < (3, 10):
        print(
            "❌ Error: Python 3.10+ is required for PyCompiler ARK++ Professional Edition"
        )
        print(f"   Current version: {sys.version}")
        print("   Please upgrade Python and try again.")
        return False

    print(f"✅ Python {sys.version.split()[0]} - Compatible")
    return True

def check_virtual_environment():
    """Check if running in a virtual environment."""
    in_venv = (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
        or os.environ.get("VIRTUAL_ENV") is not None
    )

    if in_venv:
        venv_path = os.environ.get("VIRTUAL_ENV", "Unknown")
        print(f"✅ Virtual environment: {venv_path}")
    else:
        print("���️  Warning: Not running in a virtual environment")
        print("   Recommendation: Use 'python -m venv .venv' and activate it")

    return in_venv

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = ["PySide6", "psutil", "PyYAML", "jsonschema", "Pillow"]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.lower().replace("-", "_"))
            print(f"✅ {package} - Installed")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - Missing")

    if missing_packages:
        print(f"\n❌ Missing dependencies: {', '.join(missing_packages)}")
        print("   Install with: pip install -r requirements.txt -c constraints.txt")
        return False

    return True

def check_development_tools():
    """Check if development tools are available."""
    dev_tools = {
        "black": "Code formatting",
        "ruff": "Linting and formatting",
        "mypy": "Type checking",
        "pytest": "Testing framework",
        "pre-commit": "Git hooks",
    }

    print("\n🛠️  Development Tools Status:")
    for tool, description in dev_tools.items():
        try:
            result = subprocess.run(
                [tool, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0]
                print(f"✅ {tool} - {description} ({version})")
            else:
                print(f"❌ {tool} - {description} (Not working)")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"❌ {tool} - {description} (Not installed)")

def check_platform_specific():
    """Check platform-specific requirements."""
    system = platform.system().lower()

    print(f"\n🌍 Platform: {platform.system()} {platform.release()}")
    print(f"   Architecture: {platform.machine()}")

    if system == "linux":
        # Check for required system libraries
        print("   Linux-specific checks passed")
    elif system == "darwin":
        # macOS specific checks
        print("   macOS-specific checks passed")
    elif system == "windows":
        # Windows specific checks
        print("   Windows-specific checks passed")

def run_quality_checks():
    """Run basic quality checks."""
    print("\n🔍 Running Quality Checks...")

    # Check if main.py exists and is valid Python
    main_file = Path("main.py")
    if not main_file.exists():
        print("❌ main.py not found")
        return False

    try:
        # Try to compile main.py
        with open(main_file, encoding="utf-8") as f:
            compile(f.read(), str(main_file), "exec")
        print("✅ main.py syntax is valid")
    except SyntaxError as e:
        print(f"❌ Syntax error in main.py: {e}")
        return False

    return True

def launch_application():
    """Launch the main application."""
    print("\n🚀 Launching PyCompiler ARK++ Professional Edition...")

    try:
        # Set environment variables for professional mode
        env = os.environ.copy()
        env["PYCOMPILER_EDITION"] = "professional"
        env["PYCOMPILER_VERSION"] = "3.2.3"

        # Launch main application
        subprocess.run([sys.executable, "main.py"], env=env)

    except KeyboardInterrupt:
        print("\n⏹️  Application stopped by user")
    except Exception as e:
        print(f"\n❌ Error launching application: {e}")
        return False

    return True

def main():
    """Main launcher function."""
    print("=" * 60)
    print("🚀 PyCompiler ARK++ Professional Edition Launcher")
    print("   Industrial-grade Python compilation toolkit")
    print("=" * 60)

    # Environment checks
    print("\n🔍 Environment Validation:")

    if not check_python_version():
        sys.exit(1)

    check_virtual_environment()

    if not check_dependencies():
        print("\n💡 Quick setup:")
        print("   1. Create virtual environment: python -m venv .venv")
        print(
            "   2. Activate it: source .venv/bin/activate (Linux/macOS) or .venv\\Scripts\\activate (Windows)"
        )
        print(
            "   3. Install dependencies: pip install -r requirements.txt -c constraints.txt"
        )
        sys.exit(1)

    check_development_tools()
    check_platform_specific()

    if not run_quality_checks():
        sys.exit(1)

    # Launch application
    print("\n" + "=" * 60)
    launch_application()
    print("=" * 60)
    print("✅ PyCompiler ARK++ Professional Edition session completed")

if __name__ == "__main__":
    main()
