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
Compatibility Module - Version compatibility checking for engines and plugins

This module provides utilities to verify if engines and plugins are compatible
with the current version of PyCompiler ARK++.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CompatibilityResult:
    """Result of a compatibility check."""

    is_compatible: bool
    component_name: str
    component_version: str
    required_version: str
    message: str


def parse_version(version_string: str) -> Tuple[int, int, int]:
    """
    Parse a version string into a tuple of (major, minor, patch).

    Args:
        version_string: Version string (e.g., "1.0.0", "2.1.3")

    Returns:
        Tuple of (major, minor, patch) as integers
    """
    try:
        parts = version_string.strip().split("+")[0].split("-")[0].split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError, AttributeError):
        return (0, 0, 0)


def compare_versions(
    current: str, required: str, mode: str = "gte"
) -> bool:
    """
    Compare two version strings.

    Args:
        current: Current version string
        required: Required version string
        mode: Comparison mode ("gte" = >=, "gt" = >, "eq" = ==, "lte" = <=, "lt" = <)

    Returns:
        True if the comparison is satisfied, False otherwise
    """
    curr_tuple = parse_version(current)
    req_tuple = parse_version(required)

    if mode == "gte":
        return curr_tuple >= req_tuple
    elif mode == "gt":
        return curr_tuple > req_tuple
    elif mode == "eq":
        return curr_tuple == req_tuple
    elif mode == "lte":
        return curr_tuple <= req_tuple
    elif mode == "lt":
        return curr_tuple < req_tuple
    else:
        return False


def check_engine_compatibility(
    engine_class, current_core_version: str
) -> CompatibilityResult:
    """
    Check if an engine is compatible with the current core version.

    Args:
        engine_class: The engine class to check
        current_core_version: Current version of PyCompiler ARK++ Core

    Returns:
        CompatibilityResult with compatibility information
    """
    engine_name = getattr(engine_class, "name", "Unknown Engine")
    engine_id = getattr(engine_class, "id", "unknown")

    # Check if engine has version metadata
    engine_version = getattr(engine_class, "version", "1.0.0")
    required_core_version = getattr(engine_class, "required_core_version", "1.0.0")

    is_compatible = compare_versions(current_core_version, required_core_version, "gte")

    message = (
        f"Engine '{engine_name}' (v{engine_version}) is compatible with Core v{current_core_version}"
        if is_compatible
        else f"Engine '{engine_name}' (v{engine_version}) requires Core v{required_core_version} or higher (current: v{current_core_version})"
    )

    return CompatibilityResult(
        is_compatible=is_compatible,
        component_name=engine_name,
        component_version=engine_version,
        required_version=required_core_version,
        message=message,
    )


def check_plugin_compatibility(
    plugin_class, current_core_version: str
) -> CompatibilityResult:
    """
    Check if a plugin is compatible with the current core version.

    Args:
        plugin_class: The plugin class to check
        current_core_version: Current version of PyCompiler ARK++ Core

    Returns:
        CompatibilityResult with compatibility information
    """
    # Try to get plugin metadata
    try:
        meta = getattr(plugin_class, "meta", None)
        if meta:
            plugin_name = getattr(meta, "name", "Unknown Plugin")
            plugin_version = getattr(meta, "version", "1.0.0")
        else:
            plugin_name = getattr(plugin_class, "name", "Unknown Plugin")
            plugin_version = getattr(plugin_class, "version", "1.0.0")
    except Exception:
        plugin_name = "Unknown Plugin"
        plugin_version = "1.0.0"

    required_core_version = getattr(plugin_class, "required_core_version", "1.0.0")

    is_compatible = compare_versions(current_core_version, required_core_version, "gte")

    message = (
        f"Plugin '{plugin_name}' (v{plugin_version}) is compatible with Core v{current_core_version}"
        if is_compatible
        else f"Plugin '{plugin_name}' (v{plugin_version}) requires Core v{required_core_version} or higher (current: v{current_core_version})"
    )

    return CompatibilityResult(
        is_compatible=is_compatible,
        component_name=plugin_name,
        component_version=plugin_version,
        required_version=required_core_version,
        message=message,
    )


def check_sdk_compatibility(
    sdk_version: str, required_version: str, sdk_name: str = "SDK"
) -> CompatibilityResult:
    """
    Check if an SDK version is compatible with a required version.

    Args:
        sdk_version: Current SDK version
        required_version: Required SDK version
        sdk_name: Name of the SDK

    Returns:
        CompatibilityResult with compatibility information
    """
    is_compatible = compare_versions(sdk_version, required_version, "gte")

    message = (
        f"{sdk_name} v{sdk_version} is compatible with required version v{required_version}"
        if is_compatible
        else f"{sdk_name} v{sdk_version} does not meet minimum requirement v{required_version}"
    )

    return CompatibilityResult(
        is_compatible=is_compatible,
        component_name=sdk_name,
        component_version=sdk_version,
        required_version=required_version,
        message=message,
    )


def validate_engines(
    engines: List, current_core_version: str
) -> Dict[str, CompatibilityResult]:
    """
    Validate a list of engines for compatibility.

    Args:
        engines: List of engine classes
        current_core_version: Current version of PyCompiler ARK++ Core

    Returns:
        Dictionary mapping engine names to CompatibilityResult
    """
    results = {}
    for engine in engines:
        try:
            result = check_engine_compatibility(engine, current_core_version)
            engine_name = getattr(engine, "name", "Unknown")
            results[engine_name] = result
        except Exception as e:
            engine_name = getattr(engine, "name", "Unknown")
            results[engine_name] = CompatibilityResult(
                is_compatible=False,
                component_name=engine_name,
                component_version="unknown",
                required_version="unknown",
                message=f"Error checking compatibility: {str(e)}",
            )
    return results


def validate_plugins(
    plugins: List, current_core_version: str
) -> Dict[str, CompatibilityResult]:
    """
    Validate a list of plugins for compatibility.

    Args:
        plugins: List of plugin classes
        current_core_version: Current version of PyCompiler ARK++ Core

    Returns:
        Dictionary mapping plugin names to CompatibilityResult
    """
    results = {}
    for plugin in plugins:
        try:
            result = check_plugin_compatibility(plugin, current_core_version)
            plugin_name = result.component_name
            results[plugin_name] = result
        except Exception as e:
            plugin_name = getattr(plugin, "name", "Unknown")
            results[plugin_name] = CompatibilityResult(
                is_compatible=False,
                component_name=plugin_name,
                component_version="unknown",
                required_version="unknown",
                message=f"Error checking compatibility: {str(e)}",
            )
    return results


def get_incompatible_components(
    results: Dict[str, CompatibilityResult],
) -> List[CompatibilityResult]:
    """
    Filter and return only incompatible components from validation results.

    Args:
        results: Dictionary of CompatibilityResult objects

    Returns:
        List of incompatible CompatibilityResult objects
    """
    return [result for result in results.values() if not result.is_compatible]


def print_compatibility_report(
    results: Dict[str, CompatibilityResult], title: str = "Compatibility Report"
) -> None:
    """
    Print a formatted compatibility report.

    Args:
        results: Dictionary of CompatibilityResult objects
        title: Title for the report
    """
    print("=" * 70)
    print(f"{title}")
    print("=" * 70)

    compatible_count = sum(1 for r in results.values() if r.is_compatible)
    incompatible_count = len(results) - compatible_count

    print(f"\nSummary: {compatible_count} compatible, {incompatible_count} incompatible\n")

    for name, result in results.items():
        status = "✓ COMPATIBLE" if result.is_compatible else "✗ INCOMPATIBLE"
        print(f"{status}: {result.message}")

    print("\n" + "=" * 70)


__all__ = [
    "CompatibilityResult",
    "parse_version",
    "compare_versions",
    "check_engine_compatibility",
    "check_plugin_compatibility",
    "check_sdk_compatibility",
    "validate_engines",
    "validate_plugins",
    "get_incompatible_components",
    "print_compatibility_report",
]
