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
Tests for Core.compatibility module - Version compatibility checking
"""

import pytest
from io import StringIO
import sys

from Core.compatibility import (
    CompatibilityResult,
    parse_version,
    compare_versions,
    check_engine_compatibility,
    check_plugin_compatibility,
    check_sdk_compatibility,
    validate_engines,
    validate_plugins,
    get_incompatible_components,
    print_compatibility_report,
)


class TestVersionParsing:
    """Test version parsing functionality"""

    def test_parse_version_standard(self):
        """Test parsing standard version strings"""
        assert parse_version("1.0.0") == (1, 0, 0)
        assert parse_version("2.3.4") == (2, 3, 4)
        assert parse_version("0.0.1") == (0, 0, 1)

    def test_parse_version_with_prerelease(self):
        """Test parsing versions with prerelease tags"""
        assert parse_version("1.0.0-alpha") == (1, 0, 0)
        assert parse_version("2.1.0-beta.1") == (2, 1, 0)

    def test_parse_version_with_build_metadata(self):
        """Test parsing versions with build metadata"""
        assert parse_version("1.0.0+build.1") == (1, 0, 0)
        assert parse_version("2.1.0+20130313144700") == (2, 1, 0)

    def test_parse_version_incomplete(self):
        """Test parsing incomplete version strings"""
        assert parse_version("1") == (1, 0, 0)
        assert parse_version("1.2") == (1, 2, 0)

    def test_parse_version_invalid(self):
        """Test parsing invalid version strings"""
        assert parse_version("invalid") == (0, 0, 0)
        assert parse_version("") == (0, 0, 0)
        assert parse_version("abc.def.ghi") == (0, 0, 0)

    def test_parse_version_with_whitespace(self):
        """Test parsing versions with whitespace"""
        assert parse_version("  1.0.0  ") == (1, 0, 0)
        assert parse_version("\t2.1.0\n") == (2, 1, 0)


class TestVersionComparison:
    """Test version comparison functionality"""

    def test_compare_versions_gte(self):
        """Test greater than or equal comparison"""
        assert compare_versions("2.0.0", "1.0.0", "gte") is True
        assert compare_versions("1.0.0", "1.0.0", "gte") is True
        assert compare_versions("1.0.0", "2.0.0", "gte") is False

    def test_compare_versions_gt(self):
        """Test greater than comparison"""
        assert compare_versions("2.0.0", "1.0.0", "gt") is True
        assert compare_versions("1.0.0", "1.0.0", "gt") is False
        assert compare_versions("1.0.0", "2.0.0", "gt") is False

    def test_compare_versions_eq(self):
        """Test equality comparison"""
        assert compare_versions("1.0.0", "1.0.0", "eq") is True
        assert compare_versions("1.0.0", "1.0.1", "eq") is False
        assert compare_versions("2.0.0", "1.0.0", "eq") is False

    def test_compare_versions_lte(self):
        """Test less than or equal comparison"""
        assert compare_versions("1.0.0", "2.0.0", "lte") is True
        assert compare_versions("1.0.0", "1.0.0", "lte") is True
        assert compare_versions("2.0.0", "1.0.0", "lte") is False

    def test_compare_versions_lt(self):
        """Test less than comparison"""
        assert compare_versions("1.0.0", "2.0.0", "lt") is True
        assert compare_versions("1.0.0", "1.0.0", "lt") is False
        assert compare_versions("2.0.0", "1.0.0", "lt") is False

    def test_compare_versions_invalid_mode(self):
        """Test invalid comparison mode"""
        assert compare_versions("1.0.0", "1.0.0", "invalid") is False


class TestCompatibilityResult:
    """Test CompatibilityResult dataclass"""

    def test_compatibility_result_creation(self):
        """Test creating a CompatibilityResult"""
        result = CompatibilityResult(
            is_compatible=True,
            component_name="Test Engine",
            component_version="1.0.0",
            required_version="1.0.0",
            message="Compatible",
        )
        assert result.is_compatible is True
        assert result.component_name == "Test Engine"
        assert result.component_version == "1.0.0"
        assert result.required_version == "1.0.0"
        assert result.message == "Compatible"

    def test_compatibility_result_incompatible(self):
        """Test incompatible result"""
        result = CompatibilityResult(
            is_compatible=False,
            component_name="Test Engine",
            component_version="1.0.0",
            required_version="2.0.0",
            message="Incompatible",
        )
        assert result.is_compatible is False


class TestEngineCompatibility:
    """Test engine compatibility checking"""

    def test_check_engine_compatibility_compatible(self):
        """Test checking compatible engine"""

        class MockEngine:
            name = "Test Engine"
            id = "test_engine"
            version = "1.0.0"
            required_core_version = "1.0.0"

        result = check_engine_compatibility(MockEngine, "1.0.0")
        assert result.is_compatible is True
        assert "compatible" in result.message.lower()

    def test_check_engine_compatibility_incompatible(self):
        """Test checking incompatible engine"""

        class MockEngine:
            name = "Test Engine"
            id = "test_engine"
            version = "1.0.0"
            required_core_version = "2.0.0"

        result = check_engine_compatibility(MockEngine, "1.0.0")
        assert result.is_compatible is False
        assert "require" in result.message.lower()

    def test_check_engine_compatibility_missing_attributes(self):
        """Test checking engine with missing attributes"""

        class MockEngine:
            pass

        result = check_engine_compatibility(MockEngine, "1.0.0")
        assert isinstance(result, CompatibilityResult)


class TestPluginCompatibility:
    """Test plugin compatibility checking"""

    def test_check_plugin_compatibility_compatible(self):
        """Test checking compatible plugin"""

        class MockPlugin:
            name = "Test Plugin"
            version = "1.0.0"
            required_core_version = "1.0.0"

        result = check_plugin_compatibility(MockPlugin, "1.0.0")
        assert result.is_compatible is True

    def test_check_plugin_compatibility_incompatible(self):
        """Test checking incompatible plugin"""

        class MockPlugin:
            name = "Test Plugin"
            version = "1.0.0"
            required_core_version = "2.0.0"

        result = check_plugin_compatibility(MockPlugin, "1.0.0")
        assert result.is_compatible is False

    def test_check_plugin_compatibility_with_meta(self):
        """Test checking plugin with meta attribute"""

        class MockMeta:
            name = "Test Plugin"
            version = "1.0.0"

        class MockPlugin:
            meta = MockMeta()
            required_core_version = "1.0.0"

        result = check_plugin_compatibility(MockPlugin, "1.0.0")
        assert result.is_compatible is True


class TestSDKCompatibility:
    """Test SDK compatibility checking"""

    def test_check_sdk_compatibility_compatible(self):
        """Test checking compatible SDK"""
        result = check_sdk_compatibility("3.2.3", "3.2.0", "Engine SDK")
        assert result.is_compatible is True

    def test_check_sdk_compatibility_incompatible(self):
        """Test checking incompatible SDK"""
        result = check_sdk_compatibility("3.1.0", "3.2.0", "Engine SDK")
        assert result.is_compatible is False

    def test_check_sdk_compatibility_exact_match(self):
        """Test checking SDK with exact version match"""
        result = check_sdk_compatibility("3.2.0", "3.2.0", "Engine SDK")
        assert result.is_compatible is True


class TestValidation:
    """Test validation functions"""

    def test_validate_engines_empty_list(self):
        """Test validating empty engine list"""
        results = validate_engines([], "1.0.0")
        assert isinstance(results, dict)
        assert len(results) == 0

    def test_validate_engines_single(self):
        """Test validating single engine"""

        class MockEngine:
            name = "Test Engine"
            version = "1.0.0"
            required_core_version = "1.0.0"

        results = validate_engines([MockEngine], "1.0.0")
        assert len(results) == 1
        assert "Test Engine" in results

    def test_validate_engines_multiple(self):
        """Test validating multiple engines"""

        class Engine1:
            name = "Engine 1"
            version = "1.0.0"
            required_core_version = "1.0.0"

        class Engine2:
            name = "Engine 2"
            version = "1.0.0"
            required_core_version = "1.0.0"

        results = validate_engines([Engine1, Engine2], "1.0.0")
        assert len(results) == 2

    def test_validate_plugins_empty_list(self):
        """Test validating empty plugin list"""
        results = validate_plugins([], "1.0.0")
        assert isinstance(results, dict)
        assert len(results) == 0

    def test_validate_plugins_single(self):
        """Test validating single plugin"""

        class MockPlugin:
            name = "Test Plugin"
            version = "1.0.0"
            required_core_version = "1.0.0"

        results = validate_plugins([MockPlugin], "1.0.0")
        assert len(results) == 1


class TestIncompatibleComponents:
    """Test filtering incompatible components"""

    def test_get_incompatible_components_all_compatible(self):
        """Test filtering when all components are compatible"""
        results = {
            "engine1": CompatibilityResult(
                is_compatible=True,
                component_name="Engine 1",
                component_version="1.0.0",
                required_version="1.0.0",
                message="Compatible",
            ),
            "engine2": CompatibilityResult(
                is_compatible=True,
                component_name="Engine 2",
                component_version="1.0.0",
                required_version="1.0.0",
                message="Compatible",
            ),
        }
        incompatible = get_incompatible_components(results)
        assert len(incompatible) == 0

    def test_get_incompatible_components_mixed(self):
        """Test filtering with mixed compatibility"""
        results = {
            "engine1": CompatibilityResult(
                is_compatible=True,
                component_name="Engine 1",
                component_version="1.0.0",
                required_version="1.0.0",
                message="Compatible",
            ),
            "engine2": CompatibilityResult(
                is_compatible=False,
                component_name="Engine 2",
                component_version="1.0.0",
                required_version="2.0.0",
                message="Incompatible",
            ),
        }
        incompatible = get_incompatible_components(results)
        assert len(incompatible) == 1
        assert incompatible[0].component_name == "Engine 2"

    def test_get_incompatible_components_all_incompatible(self):
        """Test filtering when all components are incompatible"""
        results = {
            "engine1": CompatibilityResult(
                is_compatible=False,
                component_name="Engine 1",
                component_version="1.0.0",
                required_version="2.0.0",
                message="Incompatible",
            ),
            "engine2": CompatibilityResult(
                is_compatible=False,
                component_name="Engine 2",
                component_version="1.0.0",
                required_version="2.0.0",
                message="Incompatible",
            ),
        }
        incompatible = get_incompatible_components(results)
        assert len(incompatible) == 2


class TestReporting:
    """Test reporting functionality"""

    def test_print_compatibility_report(self, capsys):
        """Test printing compatibility report"""
        results = {
            "engine1": CompatibilityResult(
                is_compatible=True,
                component_name="Engine 1",
                component_version="1.0.0",
                required_version="1.0.0",
                message="Engine 1 is compatible",
            ),
            "engine2": CompatibilityResult(
                is_compatible=False,
                component_name="Engine 2",
                component_version="1.0.0",
                required_version="2.0.0",
                message="Engine 2 is incompatible",
            ),
        }
        print_compatibility_report(results, "Test Report")
        captured = capsys.readouterr()
        assert "Test Report" in captured.out
        assert "compatible" in captured.out.lower()
        assert "incompatible" in captured.out.lower()

    def test_print_compatibility_report_summary(self, capsys):
        """Test that report includes summary"""
        results = {
            "engine1": CompatibilityResult(
                is_compatible=True,
                component_name="Engine 1",
                component_version="1.0.0",
                required_version="1.0.0",
                message="Compatible",
            ),
            "engine2": CompatibilityResult(
                is_compatible=False,
                component_name="Engine 2",
                component_version="1.0.0",
                required_version="2.0.0",
                message="Incompatible",
            ),
        }
        print_compatibility_report(results)
        captured = capsys.readouterr()
        assert "1 compatible" in captured.out
        assert "1 incompatible" in captured.out
