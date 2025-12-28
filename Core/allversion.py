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
All Versions Module - Centralized version tracking for PyCompiler ARK++

This module provides utilities to capture and retrieve version information
for the core application and all SDKs/engines.
"""

from __future__ import annotations

from typing import Dict


class VersionInfo:
    """Container for version information of a component."""

    def __init__(self, name: str, version: str, component_type: str = "unknown"):
        """
        Initialize version information.

        Args:
            name: Component name
            version: Version string (e.g., "1.0.0")
            component_type: Type of component (core, sdk, engine, plugin)
        """
        self.name = name
        self.version = version
        self.component_type = component_type

    def __repr__(self) -> str:
        return f"VersionInfo(name={self.name!r}, version={self.version!r}, type={self.component_type!r})"

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "version": self.version,
            "type": self.component_type,
        }


def get_core_version() -> str:
    """Get the version of the PyCompiler ARK++ Core."""
    try:
        from . import __version__

        return __version__
    except (ImportError, AttributeError):
        return "unknown"


def get_engine_sdk_version() -> str:
    """Get the version of the Engine SDK."""
    try:
        import engine_sdk

        return engine_sdk.__version__
    except (ImportError, AttributeError):
        return "unknown"


def get_bcasl_version() -> str:
    """Get the version of the BCASL (Before-Compilation Actions System Loader)."""
    try:
        import bcasl

        return bcasl.__version__
    except (ImportError, AttributeError):
        return "unknown"


def get_plugins_sdk_version() -> str:
    """Get the version of the Plugins SDK."""
    try:
        from Plugins_SDK import __version__

        return __version__
    except (ImportError, AttributeError):
        return "unknown"


def get_bc_plugin_context_version() -> str:
    """Get the version of the BcPluginContext."""
    try:
        from Plugins_SDK.BcPluginContext import __version__

        return __version__
    except (ImportError, AttributeError):
        return "unknown"


def get_general_context_version() -> str:
    """Get the version of the GeneralContext."""
    try:
        from Plugins_SDK.GeneralContext import __version__

        return __version__
    except (ImportError, AttributeError):
        return "unknown"


def get_system_version() -> str:
    """Get the system information (Python version and platform)."""
    import sys
    import platform

    python_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    system_info = f"{platform.system()} {platform.release()}"
    return f"Python {python_version} on {system_info}"


def get_all_versions() -> Dict[str, VersionInfo]:
    """
    Get all version information for the application, SDKs and system.

    Returns:
        Dictionary mapping component names to VersionInfo objects
    """
    versions = {}

    # Core
    core_version = get_core_version()
    versions["core"] = VersionInfo("PyCompiler ARK++ Core", core_version, "core")

    # SDKs
    engine_sdk_version = get_engine_sdk_version()
    versions["engine_sdk"] = VersionInfo("Engine SDK", engine_sdk_version, "sdk")

    bcasl_version = get_bcasl_version()
    versions["bcasl"] = VersionInfo("BCASL", bcasl_version, "sdk")

    plugins_sdk_version = get_plugins_sdk_version()
    versions["plugins_sdk"] = VersionInfo("Plugins SDK", plugins_sdk_version, "sdk")

    bc_plugin_context_version = get_bc_plugin_context_version()
    versions["bc_plugin_context"] = VersionInfo(
        "BcPluginContext", bc_plugin_context_version, "sdk"
    )

    general_context_version = get_general_context_version()
    versions["general_context"] = VersionInfo(
        "GeneralContext", general_context_version, "sdk"
    )

    # System
    system_version = get_system_version()
    versions["system"] = VersionInfo("System", system_version, "system")

    return versions


def get_versions_dict() -> Dict[str, str]:
    """
    Get all versions as a simple dictionary mapping names to version strings.

    Returns:
        Dictionary mapping component names to version strings
    """
    versions = get_all_versions()
    return {name: info.version for name, info in versions.items()}


def print_all_versions() -> None:
    """Print all version information to stdout."""
    versions = get_all_versions()
    print("=" * 60)
    print("PyCompiler ARK++ - Version Information")
    print("=" * 60)

    # Group by type
    by_type = {}
    for name, info in versions.items():
        if info.component_type not in by_type:
            by_type[info.component_type] = []
        by_type[info.component_type].append((name, info))

    for component_type in ["core", "sdk", "system"]:
        if component_type in by_type:
            print(f"\n{component_type.upper()}:")
            for name, info in by_type[component_type]:
                print(f"  {info.name:.<40} {info.version}")

    print("\n" + "=" * 60)


def get_version_string() -> str:
    """
    Get a formatted version string for all components.

    Returns:
        Formatted string with all version information
    """
    versions = get_all_versions()
    lines = ["PyCompiler ARK++ Version Information:"]

    for name, info in versions.items():
        lines.append(f"  {info.name}: {info.version}")

    return "\n".join(lines)


__all__ = [
    "VersionInfo",
    "get_core_version",
    "get_engine_sdk_version",
    "get_bcasl_version",
    "get_plugins_sdk_version",
    "get_bc_plugin_context_version",
    "get_general_context_version",
    "get_system_version",
    "get_all_versions",
    "get_versions_dict",
    "print_all_versions",
    "get_version_string",
]
