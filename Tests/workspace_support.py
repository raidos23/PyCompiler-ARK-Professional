from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = PROJECT_ROOT / "Tests"
BASE_WORKSPACE_DIR = TESTS_DIR / "test_workspace1"
ENV_VAR = "PYCOMPILER_TEST_WORKSPACE"


def ensure_base_workspace() -> Path:
    """Ensure a base test workspace exists under Tests/test_workspace1 with real content.

    Creates/overwrites essential files so they are non-empty and usable by tests:
      - main.py: simple entry point
      - requirements.txt: pinned local requirements for tests (can be empty logically)
      - ARK_Main_Config.yml: minimal but representative config with inclusion/exclusion and plugins
      - src/sample_pkg: small Python package to satisfy inclusion patterns
    """
    ws = BASE_WORKSPACE_DIR
    ws.mkdir(parents=True, exist_ok=True)

    # 1) main.py entry point
    (ws / "main.py").write_text(
        (
            """
#!/usr/bin/env python3
# Test workspace entry point

def run():
    return "main_ran"

if __name__ == "__main__":
    print(run())
"""
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    # 2) requirements.txt (avoid heavy deps; yaml provided by project deps)
    (ws / "requirements.txt").write_text(
        (
            """
# Minimal requirements for test workspace
# Intentionally light to avoid network installs during tests.
"""
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    # 3) Minimal ARK config with typical fields to support merges in tests
    (ws / "ARK_Main_Config.yml").write_text(
        (
            """
# Test ARK configuration
inclusion_patterns:
  - "**/*.py"
exclusion_patterns:
  - "**/__pycache__/**"
  - "**/*.pyc"
  - ".git/**"
  - "venv/**"
  - ".venv/**"
plugins:
  bcasl_enabled: true
  plugin_timeout: 0.0
output:
  directory: "dist"
  clean_before_build: false
"""
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    # 4) Small src package for inclusion matching
    pkg_dir = ws / "src" / "sample_pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("__all__ = ['module']\n", encoding="utf-8")
    (pkg_dir / "module.py").write_text(
        (
            """
"""Sample module for workspace tests."""

VALUE = 42

"""
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    # Export the workspace path for tests/tools
    os.environ[ENV_VAR] = str(ws)
    return ws


def get_shared_workspace() -> Path:
    """Return the shared base workspace path, creating it if necessary."""
    if not BASE_WORKSPACE_DIR.exists():
        return ensure_base_workspace()
    # Ensure env var is always set for consumers
    os.environ[ENV_VAR] = str(BASE_WORKSPACE_DIR)
    return BASE_WORKSPACE_DIR
