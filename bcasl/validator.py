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
Plugin Compatibility Validator - Validates plugin compatibility with system components

This module provides utilities to validate plugin compatibility with:
- BCASL version
- Core version
- Plugins SDK version
- BcPluginContext version
- GeneralContext version
"""

from __future__ import annotations

from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class CompatibilityCheckResult:
    """Result of a plugin compatibility check."""

    plugin_id: str
    plugin_name: str
    is_compatible: bool
    missing_requirements: List[str]
    error_message: str = ""


def parse_version(version_string: str) -> Tuple[int, int, int]:
    """
    Parse a version string into (major, minor, patch).

    Supports formats:
    - "1.0.0" -> (1, 0, 0)
    - "1.0.0+" -> (1, 0, 0) [+ means "or higher"]
    - "1.0.0-beta" -> (1, 0, 0)
    - "1.0.0+build123" -> (1, 0, 0)
    """
    try:
        # Remove leading/trailing whitespace
        s = version_string.strip()

        # Handle "1.0.0+" format (+ at the end means "or higher")
        # We just strip it since our comparison logic already uses >= semantics
        if s.endswith("+"):
            s = s[:-1].strip()

        # Remove build metadata and pre-release identifiers
        s = s.split("+")[0].split("-")[0]

        # Parse major.minor.patch
        parts = s.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except Exception:
        return (0, 0, 0)


def check_plugin_compatibility(
    plugin,
    bcasl_version: str,
    core_version: str,
    plugins_sdk_version: str,
    bc_plugin_context_version: str,
    general_context_version: str,
) -> CompatibilityCheckResult:
    """
    Check if a plugin is compatible with the current system versions.

    Args:
        plugin: BcPluginBase instance
        bcasl_version: Current BCASL version
        core_version: Current Core version
        plugins_sdk_version: Current Plugins SDK version
        bc_plugin_context_version: Current BcPluginContext version
        general_context_version: Current GeneralContext version

    Returns:
        CompatibilityCheckResult with compatibility information
    """
    plugin_id = plugin.meta.id
    plugin_name = plugin.meta.name
    missing_requirements = []

    # Check BCASL compatibility
    if not plugin.is_compatible_with_bcasl(bcasl_version):
        missing_requirements.append(
            f"BCASL >= {plugin.meta.required_bcasl_version} (current: {bcasl_version})"
        )

    # Check Core compatibility
    if not plugin.is_compatible_with_core(core_version):
        missing_requirements.append(
            f"Core >= {plugin.meta.required_core_version} (current: {core_version})"
        )

    # Check Plugins SDK compatibility
    if not plugin.is_compatible_with_plugins_sdk(plugins_sdk_version):
        missing_requirements.append(
            f"Plugins SDK >= {plugin.meta.required_plugins_sdk_version} (current: {plugins_sdk_version})"
        )

    # Check BcPluginContext compatibility
    if not plugin.is_compatible_with_bc_plugin_context(bc_plugin_context_version):
        missing_requirements.append(
            f"BcPluginContext >= {plugin.meta.required_bc_plugin_context_version} (current: {bc_plugin_context_version})"
        )

    # Check GeneralContext compatibility
    if not plugin.is_compatible_with_general_context(general_context_version):
        missing_requirements.append(
            f"GeneralContext >= {plugin.meta.required_general_context_version} (current: {general_context_version})"
        )

    is_compatible = len(missing_requirements) == 0

    error_message = ""
    if not is_compatible:
        error_message = f"Plugin '{plugin_name}' ({plugin_id}) is incompatible. Missing: {', '.join(missing_requirements)}"

    return CompatibilityCheckResult(
        plugin_id=plugin_id,
        plugin_name=plugin_name,
        is_compatible=is_compatible,
        missing_requirements=missing_requirements,
        error_message=error_message,
    )


def validate_plugins_compatibility(
    plugins: List,
    bcasl_version: str,
    core_version: str,
    plugins_sdk_version: str,
    bc_plugin_context_version: str,
    general_context_version: str,
    strict_mode: bool = True,
) -> Tuple[List, List]:
    """
    Validate a list of plugins for compatibility.

    Args:
        plugins: List of BcPluginBase instances
        bcasl_version: Current BCASL version
        core_version: Current Core version
        plugins_sdk_version: Current Plugins SDK version
        bc_plugin_context_version: Current BcPluginContext version
        general_context_version: Current GeneralContext version
        strict_mode: If True, reject plugins without explicit version requirements

    Returns:
        Tuple of (compatible_plugins, incompatible_results)
    """
    compatible_plugins = []
    incompatible_results = []

    for plugin in plugins:
        try:
            # In strict mode, reject plugins that don't specify requirements
            if strict_mode:
                has_explicit_requirements = (
                    plugin.meta.required_bcasl_version != "1.0.0"
                    or plugin.meta.required_core_version != "1.0.0"
                    or plugin.meta.required_plugins_sdk_version != "1.0.0"
                    or plugin.meta.required_bc_plugin_context_version != "1.0.0"
                    or plugin.meta.required_general_context_version != "1.0.0"
                )

                if not has_explicit_requirements:
                    result = CompatibilityCheckResult(
                        plugin_id=plugin.meta.id,
                        plugin_name=plugin.meta.name,
                        is_compatible=False,
                        missing_requirements=[
                            "No explicit version requirements specified"
                        ],
                        error_message=f"Plugin '{plugin.meta.name}' ({plugin.meta.id}) does not specify version requirements. "
                        f"Please add required_*_version fields to PluginMeta.",
                    )
                    incompatible_results.append(result)
                    continue

            # Check compatibility
            result = check_plugin_compatibility(
                plugin,
                bcasl_version,
                core_version,
                plugins_sdk_version,
                bc_plugin_context_version,
                general_context_version,
            )

            if result.is_compatible:
                compatible_plugins.append(plugin)
            else:
                incompatible_results.append(result)

        except Exception as e:
            result = CompatibilityCheckResult(
                plugin_id=(
                    getattr(plugin, "meta", {}).id
                    if hasattr(plugin, "meta")
                    else "unknown"
                ),
                plugin_name=(
                    getattr(plugin, "meta", {}).name
                    if hasattr(plugin, "meta")
                    else "Unknown"
                ),
                is_compatible=False,
                missing_requirements=[],
                error_message=f"Error validating plugin: {str(e)}",
            )
            incompatible_results.append(result)

    return compatible_plugins, incompatible_results


def print_compatibility_report(
    compatible_plugins: List,
    incompatible_results: List,
) -> None:
    """Print a formatted compatibility report."""
    print("=" * 70)
    print("Plugin Compatibility Report")
    print("=" * 70)

    print(f"\n✓ Compatible: {len(compatible_plugins)}")
    for plugin in compatible_plugins:
        print(f"  - {plugin.meta.name} ({plugin.meta.id}) v{plugin.meta.version}")

    print(f"\n✗ Incompatible: {len(incompatible_results)}")
    for result in incompatible_results:
        print(f"  - {result.plugin_name} ({result.plugin_id})")
        if result.missing_requirements:
            for req in result.missing_requirements:
                print(f"    • {req}")
        if result.error_message:
            print(f"    Error: {result.error_message}")

    print("\n" + "=" * 70)


__all__ = [
    "CompatibilityCheckResult",
    "parse_version",
    "check_plugin_compatibility",
    "validate_plugins_compatibility",
    "print_compatibility_report",
]
