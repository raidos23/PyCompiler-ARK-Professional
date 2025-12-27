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
Tests for plugin SDK compatibility - PluginMeta with SDK version requirements
"""

import pytest
from bcasl import BcPluginBase, PluginMeta


class TestPluginMetaSdkVersions:
    """Test PluginMeta SDK version fields"""

    def test_plugin_meta_with_all_sdk_versions(self):
        """Test creating PluginMeta with all SDK version requirements"""
        meta = PluginMeta(
            id="advanced_plugin",
            name="Advanced Plugin",
            version="2.0.0",
            description="A plugin with full SDK requirements",
            required_bcasl_version="2.0.0",
            required_core_version="1.0.0",
            required_plugins_sdk_version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
        )
        assert meta.required_bcasl_version == "2.0.0"
        assert meta.required_core_version == "1.0.0"
        assert meta.required_plugins_sdk_version == "1.0.0"
        assert meta.required_bc_plugin_context_version == "1.0.0"

    def test_plugin_meta_default_sdk_versions(self):
        """Test PluginMeta with default SDK versions"""
        meta = PluginMeta(
            id="simple_plugin",
            name="Simple Plugin",
            version="1.0.0",
        )
        assert meta.required_plugins_sdk_version == "1.0.0"
        assert meta.required_bc_plugin_context_version == "1.0.0"

    def test_plugin_meta_custom_sdk_versions(self):
        """Test PluginMeta with custom SDK version requirements"""
        meta = PluginMeta(
            id="custom_plugin",
            name="Custom Plugin",
            version="1.5.0",
            required_plugins_sdk_version="1.2.0",
            required_bc_plugin_context_version="1.1.0",
        )
        assert meta.required_plugins_sdk_version == "1.2.0"
        assert meta.required_bc_plugin_context_version == "1.1.0"


class TestBcPluginBaseSdkCompatibility:
    """Test BcPluginBase SDK compatibility methods"""

    def test_is_compatible_with_plugins_sdk_compatible(self):
        """Test checking Plugins SDK compatibility - compatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_plugins_sdk_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_plugins_sdk("1.0.0") is True
        assert plugin.is_compatible_with_plugins_sdk("1.1.0") is True
        assert plugin.is_compatible_with_plugins_sdk("2.0.0") is True

    def test_is_compatible_with_plugins_sdk_incompatible(self):
        """Test checking Plugins SDK compatibility - incompatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_plugins_sdk_version="1.5.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_plugins_sdk("1.4.9") is False
        assert plugin.is_compatible_with_plugins_sdk("1.0.0") is False

    def test_is_compatible_with_bc_plugin_context_compatible(self):
        """Test checking BcPluginContext compatibility - compatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_bc_plugin_context("1.0.0") is True
        assert plugin.is_compatible_with_bc_plugin_context("1.1.0") is True
        assert plugin.is_compatible_with_bc_plugin_context("2.0.0") is True

    def test_is_compatible_with_bc_plugin_context_incompatible(self):
        """Test checking BcPluginContext compatibility - incompatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_bc_plugin_context_version="1.2.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_bc_plugin_context("1.1.9") is False
        assert plugin.is_compatible_with_bc_plugin_context("1.0.0") is False

    def test_get_full_compatibility_info(self):
        """Test getting full compatibility information including SDKs"""
        meta = PluginMeta(
            id="full_plugin",
            name="Full Plugin",
            version="2.0.0",
            required_bcasl_version="2.0.0",
            required_core_version="1.5.0",
            required_plugins_sdk_version="1.1.0",
            required_bc_plugin_context_version="1.0.5",
        )

        class FullPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = FullPlugin(meta)
        info = plugin.get_full_compatibility_info()

        assert info["plugin_id"] == "full_plugin"
        assert info["plugin_name"] == "Full Plugin"
        assert info["plugin_version"] == "2.0.0"
        assert info["required_bcasl_version"] == "2.0.0"
        assert info["required_core_version"] == "1.5.0"
        assert info["required_plugins_sdk_version"] == "1.1.0"
        assert info["required_bc_plugin_context_version"] == "1.0.5"


class TestPluginSdkCompatibilityScenarios:
    """Test realistic plugin SDK compatibility scenarios"""

    def test_plugin_requires_latest_sdks(self):
        """Test plugin that requires latest SDK versions"""
        meta = PluginMeta(
            id="modern_plugin",
            name="Modern Plugin",
            version="3.0.0",
            description="Uses latest SDK features",
            required_bcasl_version="2.1.0",
            required_core_version="1.5.0",
            required_plugins_sdk_version="1.2.0",
            required_bc_plugin_context_version="1.1.0",
        )

        class ModernPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = ModernPlugin(meta)

        # Should be compatible with newer versions
        assert plugin.is_compatible_with_plugins_sdk("1.2.0") is True
        assert plugin.is_compatible_with_bc_plugin_context("1.1.0") is True

        # Should not be compatible with older versions
        assert plugin.is_compatible_with_plugins_sdk("1.1.9") is False
        assert plugin.is_compatible_with_bc_plugin_context("1.0.9") is False

    def test_plugin_compatible_with_old_sdks(self):
        """Test plugin compatible with older SDK versions"""
        meta = PluginMeta(
            id="legacy_plugin",
            name="Legacy Plugin",
            version="1.0.0",
            required_plugins_sdk_version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
        )

        class LegacyPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = LegacyPlugin(meta)

        # Should be compatible with any newer version
        assert plugin.is_compatible_with_plugins_sdk("1.0.0") is True
        assert plugin.is_compatible_with_plugins_sdk("1.5.0") is True
        assert plugin.is_compatible_with_bc_plugin_context("1.0.0") is True
        assert plugin.is_compatible_with_bc_plugin_context("2.0.0") is True

    def test_multiple_plugins_different_sdk_requirements(self):
        """Test multiple plugins with different SDK requirements"""
        meta1 = PluginMeta(
            id="plugin1",
            name="Plugin 1",
            version="1.0.0",
            required_plugins_sdk_version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
        )

        meta2 = PluginMeta(
            id="plugin2",
            name="Plugin 2",
            version="2.0.0",
            required_plugins_sdk_version="1.1.0",
            required_bc_plugin_context_version="1.0.5",
        )

        class Plugin1(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        class Plugin2(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin1 = Plugin1(meta1)
        plugin2 = Plugin2(meta2)

        # Plugin1 should be compatible with base versions
        assert plugin1.is_compatible_with_plugins_sdk("1.0.0") is True
        assert plugin1.is_compatible_with_bc_plugin_context("1.0.0") is True

        # Plugin2 requires newer versions
        assert plugin2.is_compatible_with_plugins_sdk("1.1.0") is True
        assert plugin2.is_compatible_with_bc_plugin_context("1.0.5") is True
        assert plugin2.is_compatible_with_plugins_sdk("1.0.9") is False
        assert plugin2.is_compatible_with_bc_plugin_context("1.0.4") is False

    def test_plugin_with_prerelease_sdk_versions(self):
        """Test plugin compatibility with prerelease SDK versions"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_plugins_sdk_version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)

        # Prerelease versions should be parsed correctly
        assert plugin.is_compatible_with_plugins_sdk("1.0.0-alpha") is True
        assert plugin.is_compatible_with_plugins_sdk("1.0.0+build.1") is True
        assert plugin.is_compatible_with_bc_plugin_context("1.0.0-beta") is True


class TestPluginSdkVersionsIntegration:
    """Integration tests for plugin SDK version requirements"""

    def test_plugins_sdk_version_accessible(self):
        """Test that Plugins SDK version is accessible"""
        from Plugins_SDK.BcPluginContext import __version__

        assert isinstance(__version__, str)
        assert __version__ == "1.0.0"

    def test_plugin_compatibility_with_current_plugins_sdk(self):
        """Test plugin compatibility with current Plugins SDK version"""
        from Plugins_SDK.BcPluginContext import __version__ as sdk_version

        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_plugins_sdk_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_plugins_sdk(sdk_version) is True

    def test_full_compatibility_check_all_components(self):
        """Test full compatibility check across all components"""
        meta = PluginMeta(
            id="comprehensive_plugin",
            name="Comprehensive Plugin",
            version="1.0.0",
            required_bcasl_version="2.0.0",
            required_core_version="1.0.0",
            required_plugins_sdk_version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
            required_general_context_version="1.0.0",
        )

        class ComprehensivePlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = ComprehensivePlugin(meta)

        # Check all compatibility methods work
        assert plugin.is_compatible_with_bcasl("2.0.0") is True
        assert plugin.is_compatible_with_core("1.0.0") is True
        assert plugin.is_compatible_with_plugins_sdk("1.0.0") is True
        assert plugin.is_compatible_with_bc_plugin_context("1.0.0") is True
        assert plugin.is_compatible_with_general_context("1.0.0") is True

        # Get full info
        info = plugin.get_full_compatibility_info()
        assert len(info) == 9  # 9 fields in full compatibility info
