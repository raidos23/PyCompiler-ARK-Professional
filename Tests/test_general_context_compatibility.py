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
Tests for GeneralContext compatibility - Plugin SDK version requirements
"""

import pytest
from bcasl import BcPluginBase, PluginMeta


class TestGeneralContextVersion:
    """Test GeneralContext version"""

    def test_general_context_version_accessible(self):
        """Test that GeneralContext version is accessible"""
        from Plugins_SDK.GeneralContext import __version__

        assert isinstance(__version__, str)
        assert __version__ == "1.0.0"

    def test_general_context_in_exports(self):
        """Test that __version__ is in GeneralContext exports"""
        from Plugins_SDK.GeneralContext import __all__

        assert "__version__" in __all__


class TestPluginGeneralContextCompatibility:
    """Test plugin compatibility with GeneralContext"""

    def test_plugin_meta_with_general_context_version(self):
        """Test creating PluginMeta with GeneralContext version requirement"""
        meta = PluginMeta(
            id="dialog_plugin",
            name="Dialog Plugin",
            version="1.0.0",
            required_general_context_version="1.0.0",
        )
        assert meta.required_general_context_version == "1.0.0"

    def test_plugin_meta_default_general_context_version(self):
        """Test PluginMeta with default GeneralContext version"""
        meta = PluginMeta(
            id="simple_plugin",
            name="Simple Plugin",
            version="1.0.0",
        )
        assert meta.required_general_context_version == "1.0.0"

    def test_is_compatible_with_general_context_compatible(self):
        """Test checking GeneralContext compatibility - compatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_general_context_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_general_context("1.0.0") is True
        assert plugin.is_compatible_with_general_context("1.1.0") is True
        assert plugin.is_compatible_with_general_context("2.0.0") is True

    def test_is_compatible_with_general_context_incompatible(self):
        """Test checking GeneralContext compatibility - incompatible case"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_general_context_version="1.5.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_general_context("1.4.9") is False
        assert plugin.is_compatible_with_general_context("1.0.0") is False

    def test_plugin_compatibility_with_current_general_context(self):
        """Test plugin compatibility with current GeneralContext version"""
        from Plugins_SDK.GeneralContext import __version__ as gc_version

        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_general_context_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)
        assert plugin.is_compatible_with_general_context(gc_version) is True


class TestPluginAllContextsCompatibility:
    """Test plugin compatibility with all contexts"""

    def test_plugin_with_all_contexts(self):
        """Test plugin that uses all contexts"""
        meta = PluginMeta(
            id="full_featured_plugin",
            name="Full Featured Plugin",
            version="2.0.0",
            description="Uses all available contexts",
            required_bcasl_version="2.0.0",
            required_core_version="1.0.0",
            required_plugins_sdk_version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
            required_general_context_version="1.0.0",
        )

        class FullFeaturedPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = FullFeaturedPlugin(meta)

        # Check all contexts
        assert plugin.is_compatible_with_bcasl("2.0.0") is True
        assert plugin.is_compatible_with_core("1.0.0") is True
        assert plugin.is_compatible_with_plugins_sdk("1.0.0") is True
        assert plugin.is_compatible_with_bc_plugin_context("1.0.0") is True
        assert plugin.is_compatible_with_general_context("1.0.0") is True

    def test_plugin_with_different_context_versions(self):
        """Test plugin with different version requirements for each context"""
        meta = PluginMeta(
            id="advanced_plugin",
            name="Advanced Plugin",
            version="2.5.0",
            required_bcasl_version="2.1.0",
            required_core_version="1.2.0",
            required_plugins_sdk_version="1.1.0",
            required_bc_plugin_context_version="1.0.5",
            required_general_context_version="1.0.3",
        )

        class AdvancedPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = AdvancedPlugin(meta)
        info = plugin.get_full_compatibility_info()

        assert info["required_bcasl_version"] == "2.1.0"
        assert info["required_core_version"] == "1.2.0"
        assert info["required_plugins_sdk_version"] == "1.1.0"
        assert info["required_bc_plugin_context_version"] == "1.0.5"
        assert info["required_general_context_version"] == "1.0.3"

    def test_plugin_with_prerelease_general_context_version(self):
        """Test plugin compatibility with prerelease GeneralContext versions"""
        meta = PluginMeta(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            required_general_context_version="1.0.0",
        )

        class TestPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = TestPlugin(meta)

        # Prerelease versions should be parsed correctly
        assert plugin.is_compatible_with_general_context("1.0.0-alpha") is True
        assert plugin.is_compatible_with_general_context("1.0.0+build.1") is True
        assert plugin.is_compatible_with_general_context("1.0.0-rc.1") is True


class TestPluginContextsScenarios:
    """Test realistic plugin context compatibility scenarios"""

    def test_plugin_using_dialogs(self):
        """Test plugin that uses GeneralContext for dialogs"""
        meta = PluginMeta(
            id="ui_plugin",
            name="UI Plugin",
            version="1.5.0",
            description="Plugin with UI dialogs",
            required_general_context_version="1.0.0",
        )

        class UIPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = UIPlugin(meta)
        assert plugin.is_compatible_with_general_context("1.0.0") is True

    def test_plugin_using_bc_context_only(self):
        """Test plugin that only uses BcPluginContext"""
        meta = PluginMeta(
            id="bc_only_plugin",
            name="BC Only Plugin",
            version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
        )

        class BCOnlyPlugin(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin = BCOnlyPlugin(meta)
        assert plugin.is_compatible_with_bc_plugin_context("1.0.0") is True
        # Should still have default requirement for GeneralContext
        assert plugin.is_compatible_with_general_context("1.0.0") is True

    def test_multiple_plugins_different_context_requirements(self):
        """Test multiple plugins with different context requirements"""
        meta1 = PluginMeta(
            id="plugin1",
            name="Plugin 1",
            version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
        )

        meta2 = PluginMeta(
            id="plugin2",
            name="Plugin 2",
            version="1.0.0",
            required_general_context_version="1.0.0",
        )

        meta3 = PluginMeta(
            id="plugin3",
            name="Plugin 3",
            version="1.0.0",
            required_bc_plugin_context_version="1.0.0",
            required_general_context_version="1.0.0",
        )

        class Plugin1(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        class Plugin2(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        class Plugin3(BcPluginBase):
            def on_pre_compile(self, ctx):
                pass

        plugin1 = Plugin1(meta1)
        plugin2 = Plugin2(meta2)
        plugin3 = Plugin3(meta3)

        # Plugin1 uses BC context
        assert plugin1.is_compatible_with_bc_plugin_context("1.0.0") is True

        # Plugin2 uses General context
        assert plugin2.is_compatible_with_general_context("1.0.0") is True

        # Plugin3 uses both
        assert plugin3.is_compatible_with_bc_plugin_context("1.0.0") is True
        assert plugin3.is_compatible_with_general_context("1.0.0") is True
