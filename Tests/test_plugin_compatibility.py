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
Tests for plugin compatibility metadata - PluginMeta and BcPluginBase
"""

import pytest
from bcasl import BcPluginBase, PluginMeta


class TestPluginMetaCompatibility:
    """Test PluginMeta compatibility fields"""

    def test_plugin_meta_with_compatibility_info(self):
        """Test creating PluginMeta with compatibility information"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            description="A test plugin",
            required_bcasl_version="2.0.0",
            required_core_version="1.0.0",
        )
        assert meta.required_bcasl_version == "2.0.0"
        assert meta.required_core_version == "1.0.0"

    def test_plugin_meta_default_compatibility(self):
        """Test PluginMeta with default compatibility versions"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
        )
        assert meta.required_bcasl_version == "1.0.0"
        assert meta.required_core_version == "1.0.0"

    def test_plugin_meta_custom_versions(self):
        """Test PluginMeta with custom version requirements"""
        meta = PluginMeta(
            id="advanced_plugin",
            name="Advanced Plugin",
            version="2.1.0",
            required_bcasl_version="2.1.0",
            required_core_version="1.5.0",
        )
        assert meta.required_bcasl_version == "2.1.0"
        assert meta.required_core_version == "1.5.0"


class TestBcPluginBaseCompatibility:
    """Test BcPluginBase compatibility methods"""

    def test_get_compatibility_info(self):
        """Test getting plugin compatibility information"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_bcasl_version="2.0.0",
            required_core_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        info = plugin.get_compatibility_info()

        assert info["plugin_id"] == "test_plugin"
        assert info["plugin_name"] == "Test Plugin"
        assert info["plugin_version"] == "1.0.0"
        assert info["required_bcasl_version"] == "2.0.0"
        assert info["required_core_version"] == "1.0.0"

    def test_is_compatible_with_bcasl_compatible(self):
        """Test checking BCASL compatibility - compatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_bcasl_version="2.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_bcasl("2.0.0") is True
        assert plugin.is_compatible_with_bcasl("2.1.0") is True
        assert plugin.is_compatible_with_bcasl("3.0.0") is True

    def test_is_compatible_with_bcasl_incompatible(self):
        """Test checking BCASL compatibility - incompatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_bcasl_version="2.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_bcasl("1.9.9") is False
        assert plugin.is_compatible_with_bcasl("1.0.0") is False

    def test_is_compatible_with_core_compatible(self):
        """Test checking Core compatibility - compatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_core_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_core("1.0.0") is True
        assert plugin.is_compatible_with_core("1.1.0") is True
        assert plugin.is_compatible_with_core("2.0.0") is True

    def test_is_compatible_with_core_incompatible(self):
        """Test checking Core compatibility - incompatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_core_version="1.5.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_core("1.4.9") is False
        assert plugin.is_compatible_with_core("1.0.0") is False

    def test_plugin_compatibility_with_prerelease_versions(self):
        """Test plugin compatibility with prerelease versions"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_bcasl_version="2.0.0",
            required_core_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        # Prerelease versions should be parsed correctly
        assert plugin.is_compatible_with_bcasl("2.0.0-alpha") is True
        assert plugin.is_compatible_with_bcasl("2.0.0+build.1") is True

    def test_plugin_compatibility_with_invalid_versions(self):
        """Test plugin compatibility with invalid version strings"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_bcasl_version="2.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        # Invalid versions should be treated as 0.0.0
        assert plugin.is_compatible_with_bcasl("invalid") is False
        assert plugin.is_compatible_with_bcasl("") is False


class TestPluginCompatibilityScenarios:
    """Test realistic plugin compatibility scenarios"""

    def test_plugin_requires_bcasl_2_and_core_1(self):
        """Test plugin that requires BCASL 2.0.0 and Core 1.0.0"""
        meta = PluginMeta(
            id="formatter_plugin",
            name="Code Formatter",
            version="1.2.0",
            description="Formats code before compilation",
            required_bcasl_version="2.0.0",
            required_core_version="1.0.0",
        )

        class FormatterPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = FormatterPlugin(meta)

        # Should be compatible with BCASL 2.0.0 and Core 1.0.0
        assert plugin.is_compatible_with_bcasl("2.0.0") is True
        assert plugin.is_compatible_with_core("1.0.0") is True

        # Should not be compatible with older versions
        assert plugin.is_compatible_with_bcasl("1.9.9") is False
        assert plugin.is_compatible_with_core("0.9.9") is False

    def test_plugin_requires_latest_versions(self):
        """Test plugin that requires latest versions"""
        meta = PluginMeta(
            id="advanced_plugin",
            name="Advanced Features",
            version="2.0.0",
            description="Advanced compilation features",
            required_bcasl_version="2.1.0",
            required_core_version="1.5.0",
        )

        class AdvancedPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = AdvancedPlugin(meta)
        info = plugin.get_compatibility_info()

        assert info["required_bcasl_version"] == "2.1.0"
        assert info["required_core_version"] == "1.5.0"

    def test_multiple_plugins_different_requirements(self):
        """Test multiple plugins with different compatibility requirements"""
        meta1 = PluginMeta(
            id="plugin1",
            name="Plugin 1",
            version="1.0.0",
            required_bcasl_version="1.0.0",
            required_core_version="1.0.0",
        )

        meta2 = PluginMeta(
            id="plugin2",
            name="Plugin 2",
            version="2.0.0",
            required_bcasl_version="2.0.0",
            required_core_version="1.5.0",
        )

        class Plugin1(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        class Plugin2(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin1 = Plugin1(meta1)
        plugin2 = Plugin2(meta2)

        # Plugin1 should be compatible with older versions
        assert plugin1.is_compatible_with_bcasl("1.0.0") is True
        assert plugin1.is_compatible_with_core("1.0.0") is True

        # Plugin2 requires newer versions
        assert plugin2.is_compatible_with_bcasl("2.0.0") is True
        assert plugin2.is_compatible_with_core("1.5.0") is True
        assert plugin2.is_compatible_with_bcasl("1.9.9") is False
        assert plugin2.is_compatible_with_core("1.4.9") is False
