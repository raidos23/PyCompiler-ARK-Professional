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
Tests for SDK compatibility checking - engine_sdk and bcasl
"""

import pytest


class TestEngineSdkCompatibility:
    """Test engine_sdk compatibility checking"""

    def test_engine_sdk_has_check_compatibility(self):
        """Test that engine_sdk has check_engine_compatibility function"""
        import engine_sdk

        assert hasattr(engine_sdk, "check_engine_compatibility")
        assert callable(engine_sdk.check_engine_compatibility)

    def test_engine_sdk_version_exists(self):
        """Test that engine_sdk has version"""
        import engine_sdk

        assert hasattr(engine_sdk, "__version__")
        assert isinstance(engine_sdk.__version__, str)
        assert len(engine_sdk.__version__) > 0

    def test_engine_sdk_ensure_min_sdk(self):
        """Test engine_sdk ensure_min_sdk function"""
        import engine_sdk

        # Current version should satisfy itself
        assert engine_sdk.ensure_min_sdk(engine_sdk.__version__) is True
        # Should not satisfy a higher version
        assert engine_sdk.ensure_min_sdk("999.0.0") is False

    def test_check_engine_compatibility_with_mock_engine(self):
        """Test checking engine compatibility"""
        import engine_sdk

        class MockEngine:
            required_sdk_version = "3.0.0"

        # Should be compatible if current SDK >= 3.0.0
        result = engine_sdk.check_engine_compatibility(MockEngine)
        assert isinstance(result, bool)

    def test_check_engine_compatibility_with_explicit_version(self):
        """Test checking engine compatibility with explicit version"""
        import engine_sdk

        class MockEngine:
            pass

        # Should be compatible with default version
        result = engine_sdk.check_engine_compatibility(MockEngine, "1.0.0")
        assert isinstance(result, bool)
        assert result is True


class TestBcaslCompatibility:
    """Test bcasl compatibility checking"""

    def test_bcasl_has_check_compatibility(self):
        """Test that bcasl has check_plugin_compatibility function"""
        import bcasl

        assert hasattr(bcasl, "check_plugin_compatibility")
        assert callable(bcasl.check_plugin_compatibility)

    def test_bcasl_version_exists(self):
        """Test that bcasl has version"""
        import bcasl

        assert hasattr(bcasl, "__version__")
        assert isinstance(bcasl.__version__, str)
        assert bcasl.__version__ == "2.0.0"

    def test_check_plugin_compatibility_with_mock_plugin(self):
        """Test checking plugin compatibility"""
        import bcasl

        class MockPlugin:
            required_bcasl_version = "2.0.0"

        result = bcasl.check_plugin_compatibility(MockPlugin)
        assert isinstance(result, bool)
        assert result is True

    def test_check_plugin_compatibility_with_explicit_version(self):
        """Test checking plugin compatibility with explicit version"""
        import bcasl

        class MockPlugin:
            pass

        result = bcasl.check_plugin_compatibility(MockPlugin, "1.0.0")
        assert isinstance(result, bool)

    def test_check_plugin_compatibility_incompatible(self):
        """Test checking incompatible plugin"""
        import bcasl

        class MockPlugin:
            required_bcasl_version = "3.0.0"

        result = bcasl.check_plugin_compatibility(MockPlugin)
        assert isinstance(result, bool)
        assert result is False

    def test_bcasl_version_in_exports(self):
        """Test that __version__ is in bcasl exports"""
        import bcasl

        assert "__version__" in bcasl.__all__
        assert "check_plugin_compatibility" in bcasl.__all__


class TestVersionConsistency:
    """Test version consistency across modules"""

    def test_core_version_accessible(self):
        """Test that core version is accessible"""
        from Core.allversion import get_core_version

        version = get_core_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_engine_sdk_version_accessible(self):
        """Test that engine_sdk version is accessible"""
        from Core.allversion import get_engine_sdk_version

        version = get_engine_sdk_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_bcasl_version_accessible(self):
        """Test that bcasl version is accessible"""
        from Core.allversion import get_bcasl_version

        version = get_bcasl_version()
        assert isinstance(version, str)
        assert version == "2.0.0"

    def test_all_versions_accessible(self):
        """Test that all versions are accessible"""
        from Core.allversion import get_all_versions

        versions = get_all_versions()
        assert "core" in versions
        assert "engine_sdk" in versions
        assert "bcasl" in versions
        assert "system" in versions


class TestCompatibilityIntegration:
    """Integration tests for compatibility checking"""

    def test_engine_compatibility_with_current_sdk(self):
        """Test engine compatibility with current SDK version"""
        import engine_sdk

        class TestEngine:
            required_sdk_version = "1.0.0"

        # Should be compatible with current SDK
        result = engine_sdk.check_engine_compatibility(TestEngine)
        assert result is True

    def test_plugin_compatibility_with_current_bcasl(self):
        """Test plugin compatibility with current BCASL version"""
        import bcasl

        class TestPlugin:
            required_bcasl_version = "1.0.0"

        # Should be compatible with current BCASL
        result = bcasl.check_plugin_compatibility(TestPlugin)
        assert result is True

    def test_multiple_engines_compatibility(self):
        """Test compatibility checking for multiple engines"""
        import engine_sdk

        class Engine1:
            required_sdk_version = "1.0.0"

        class Engine2:
            required_sdk_version = "2.0.0"

        result1 = engine_sdk.check_engine_compatibility(Engine1)
        result2 = engine_sdk.check_engine_compatibility(Engine2)

        assert isinstance(result1, bool)
        assert isinstance(result2, bool)

    def test_multiple_plugins_compatibility(self):
        """Test compatibility checking for multiple plugins"""
        import bcasl

        class Plugin1:
            required_bcasl_version = "1.0.0"

        class Plugin2:
            required_bcasl_version = "2.0.0"

        result1 = bcasl.check_plugin_compatibility(Plugin1)
        result2 = bcasl.check_plugin_compatibility(Plugin2)

        assert isinstance(result1, bool)
        assert isinstance(result2, bool)
        assert result1 is True
        assert result2 is True
