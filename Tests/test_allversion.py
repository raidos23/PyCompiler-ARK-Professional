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
Tests for Core.allversion module - Version tracking functionality
"""

import pytest
from Core.allversion import (
    VersionInfo,
    get_core_version,
    get_engine_sdk_version,
    get_bcasl_version,
    get_system_version,
    get_all_versions,
    get_versions_dict,
    get_version_string,
)


class TestVersionInfo:
    """Test VersionInfo class"""

    def test_version_info_creation(self):
        """Test creating a VersionInfo object"""
        info = VersionInfo("Test Component", "1.2.3", "sdk")
        assert info.name == "Test Component"
        assert info.version == "1.2.3"
        assert info.component_type == "sdk"

    def test_version_info_str(self):
        """Test string representation"""
        info = VersionInfo("Test", "1.0.0", "core")
        assert str(info) == "Test v1.0.0"

    def test_version_info_repr(self):
        """Test repr representation"""
        info = VersionInfo("Test", "1.0.0", "core")
        assert "VersionInfo" in repr(info)
        assert "1.0.0" in repr(info)

    def test_version_info_to_dict(self):
        """Test conversion to dictionary"""
        info = VersionInfo("Test", "1.0.0", "core")
        d = info.to_dict()
        assert d["name"] == "Test"
        assert d["version"] == "1.0.0"
        assert d["type"] == "core"

    def test_version_info_default_type(self):
        """Test default component type"""
        info = VersionInfo("Test", "1.0.0")
        assert info.component_type == "unknown"


class TestVersionGetters:
    """Test individual version getter functions"""

    def test_get_core_version(self):
        """Test getting core version"""
        version = get_core_version()
        assert isinstance(version, str)
        assert len(version) > 0
        assert version != "unknown"

    def test_get_engine_sdk_version(self):
        """Test getting engine SDK version"""
        version = get_engine_sdk_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_bcasl_version(self):
        """Test getting BCASL version"""
        version = get_bcasl_version()
        assert isinstance(version, str)
        assert len(version) > 0
        assert version == "2.0.0"

    def test_get_system_version(self):
        """Test getting system version"""
        version = get_system_version()
        assert isinstance(version, str)
        assert "Python" in version
        assert "on" in version


class TestVersionAggregation:
    """Test version aggregation functions"""

    def test_get_all_versions(self):
        """Test getting all versions"""
        versions = get_all_versions()
        assert isinstance(versions, dict)
        assert "core" in versions
        assert "engine_sdk" in versions
        assert "bcasl" in versions
        assert "system" in versions

    def test_get_all_versions_returns_version_info(self):
        """Test that get_all_versions returns VersionInfo objects"""
        versions = get_all_versions()
        for name, info in versions.items():
            assert isinstance(info, VersionInfo)
            assert hasattr(info, "name")
            assert hasattr(info, "version")
            assert hasattr(info, "component_type")

    def test_get_versions_dict(self):
        """Test getting versions as simple dictionary"""
        versions = get_versions_dict()
        assert isinstance(versions, dict)
        assert "core" in versions
        assert "engine_sdk" in versions
        assert "bcasl" in versions
        assert "system" in versions
        # Values should be strings
        for name, version in versions.items():
            assert isinstance(version, str)

    def test_get_version_string(self):
        """Test getting formatted version string"""
        version_str = get_version_string()
        assert isinstance(version_str, str)
        assert "PyCompiler ARK++" in version_str
        assert "Core" in version_str or "core" in version_str.lower()


class TestVersionFormatting:
    """Test version string formatting"""

    def test_version_string_contains_all_components(self):
        """Test that version string contains all components"""
        version_str = get_version_string()
        assert "Core" in version_str
        assert "SDK" in version_str or "engine_sdk" in version_str
        assert "BCASL" in version_str

    def test_version_string_multiline(self):
        """Test that version string is multiline"""
        version_str = get_version_string()
        lines = version_str.split("\n")
        assert len(lines) > 1


class TestVersionConsistency:
    """Test consistency of version information"""

    def test_all_versions_have_valid_format(self):
        """Test that all versions have valid format"""
        versions = get_all_versions()
        for name, info in versions.items():
            # Version should be non-empty
            assert len(info.version) > 0
            # Component type should be one of the expected types
            assert info.component_type in ["core", "sdk", "system", "unknown"]

    def test_versions_dict_matches_all_versions(self):
        """Test that versions_dict matches all_versions"""
        all_versions = get_all_versions()
        versions_dict = get_versions_dict()
        
        for name, info in all_versions.items():
            assert name in versions_dict
            assert versions_dict[name] == info.version

    def test_bcasl_version_is_2_0_0(self):
        """Test that BCASL version is 2.0.0"""
        bcasl_version = get_bcasl_version()
        assert bcasl_version == "2.0.0"
