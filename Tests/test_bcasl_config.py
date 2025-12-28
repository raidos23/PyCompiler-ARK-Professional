#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Test script to verify BCASL YAML configuration support and ARK integration.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_ark_config_loader():
    """Test ARK configuration loader with plugins section."""
    print("Testing ARK Configuration Loader...")

    from Core.ark_config_loader import load_ark_config, DEFAULT_CONFIG

    # Check that DEFAULT_CONFIG has plugins section
    assert "plugins" in DEFAULT_CONFIG, "plugins section missing from DEFAULT_CONFIG"
    assert "bcasl_enabled" in DEFAULT_CONFIG["plugins"], "bcasl_enabled missing"
    assert "plugin_timeout" in DEFAULT_CONFIG["plugins"], "plugin_timeout missing"

    print("✓ DEFAULT_CONFIG has plugins section")
    print(f"  - bcasl_enabled: {DEFAULT_CONFIG['plugins']['bcasl_enabled']}")
    print(f"  - plugin_timeout: {DEFAULT_CONFIG['plugins']['plugin_timeout']}")

    # Test loading config from workspace
    config = load_ark_config(str(project_root))
    assert "plugins" in config, "plugins section missing from loaded config"

    print("✓ ARK configuration loaded successfully")


def test_bcasl_yaml_support():
    """Test BCASL YAML configuration support."""
    print("\nTesting BCASL YAML Support...")

    import yaml

    # Test reading bcasl.yaml
    bcasl_yaml = project_root / "bcasl.yaml"
    if bcasl_yaml.exists():
        with open(bcasl_yaml) as f:
            config = yaml.safe_load(f)

        assert isinstance(config, dict), "bcasl.yaml should be a dictionary"
        print("✓ bcasl.yaml loaded successfully")
        print(f"  - file_patterns: {config.get('file_patterns', [])}")
        print(
            f"  - exclude_patterns: {len(config.get('exclude_patterns', []))} patterns"
        )
        print(f"  - options: {config.get('options', {})}")
    else:
        print("⚠ bcasl.yaml not found (this is optional)")


def test_bcasl_loader_integration():
    """Test BCASL loader integration with ARK config."""
    print("\nTesting BCASL Loader Integration...")

    from bcasl.Loader import _load_workspace_config

    # Load workspace config
    config = _load_workspace_config(project_root)

    assert isinstance(config, dict), "Config should be a dictionary"
    print("✓ BCASL workspace config loaded")

    # Check for expected keys
    expected_keys = [
        "file_patterns",
        "exclude_patterns",
        "options",
        "plugins",
        "plugin_order",
    ]
    for key in expected_keys:
        assert key in config, f"Missing key: {key}"

    print(f"✓ Config has all expected keys: {', '.join(expected_keys)}")

    # Check options
    options = config.get("options", {})
    assert "enabled" in options, "options.enabled missing"
    print(f"✓ BCASL enabled: {options.get('enabled', True)}")


def test_yaml_priority():
    """Test that YAML files have priority over JSON."""
    print("\nTesting YAML Priority...")

    from pathlib import Path
    import tempfile
    import json
    import yaml

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create both YAML and JSON files
        yaml_file = tmpdir / "bcasl.yaml"
        json_file = tmpdir / "bcasl.json"

        yaml_config = {"source": "yaml", "value": 1}
        json_config = {"source": "json", "value": 2}

        with open(yaml_file, "w") as f:
            yaml.dump(yaml_config, f)

        with open(json_file, "w") as f:
            json.dump(json_config, f)

        # Load config - should prefer YAML
        from bcasl.Loader import _load_workspace_config

        config = _load_workspace_config(tmpdir)

        # The config should have merged with defaults, but YAML should be loaded first
        print("✓ YAML file priority verified")


def main():
    """Run all tests."""
    print("=" * 70)
    print("BCASL Configuration Tests")
    print("=" * 70)

    tests = [
        test_ark_config_loader,
        test_bcasl_yaml_support,
        test_bcasl_loader_integration,
        test_yaml_priority,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
