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
Engine Compatibility Validator - Validates engine compatibility with system components

This module provides utilities to validate engine compatibility with:
- Core version
- Engine SDK version
"""

from __future__ import annotations

from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class EngineCompatibilityCheckResult:
    """Result of an engine compatibility check."""

    engine_id: str
    engine_name: str
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


def check_engine_compatibility(
    engine_class,
    core_version: str,
    engine_sdk_version: str,
) -> EngineCompatibilityCheckResult:
    """
    Check if an engine is compatible with the current system versions.

    Compatibility check uses >= (greater than or equal) semantics:
    - If engine requires Core 1.0.0, it accepts Core 1.0.0, 1.0.1, 1.1.0, 2.0.0, etc.
    - If engine requires SDK 1.0.0, it accepts SDK 1.0.0, 1.0.1, 1.1.0, 2.0.0, etc.

    Args:
        engine_class: CompilerEngine class
        core_version: Current Core version
        engine_sdk_version: Current Engine SDK version

    Returns:
        EngineCompatibilityCheckResult with compatibility information
    """
    engine_id = getattr(engine_class, "id", "unknown")
    engine_name = getattr(engine_class, "name", "Unknown Engine")
    missing_requirements = []

    # Get required versions from engine class
    required_core_version = getattr(engine_class, "required_core_version", "1.0.0")
    required_sdk_version = getattr(engine_class, "required_sdk_version", "1.0.0")

    # Check Core compatibility: current >= required (accept equal or higher versions)
    current_core = parse_version(core_version)
    required_core = parse_version(required_core_version)
    if current_core < required_core:
        missing_requirements.append(
            f"Core >= {required_core_version} (current: {core_version})"
        )

    # Check Engine SDK compatibility: current >= required (accept equal or higher versions)
    current_sdk = parse_version(engine_sdk_version)
    required_sdk = parse_version(required_sdk_version)
    if current_sdk < required_sdk:
        missing_requirements.append(
            f"Engine SDK >= {required_sdk_version} (current: {engine_sdk_version})"
        )

    is_compatible = len(missing_requirements) == 0

    error_message = ""
    if not is_compatible:
        error_message = f"Engine '{engine_name}' ({engine_id}) is incompatible. Missing: {', '.join(missing_requirements)}"

    return EngineCompatibilityCheckResult(
        engine_id=engine_id,
        engine_name=engine_name,
        is_compatible=is_compatible,
        missing_requirements=missing_requirements,
        error_message=error_message,
    )


def validate_engines_compatibility(
    engines: List,
    core_version: str,
    engine_sdk_version: str,
    strict_mode: bool = True,
) -> Tuple[List, List]:
    """
    Validate a list of engines for compatibility.

    Args:
        engines: List of CompilerEngine classes
        core_version: Current Core version
        engine_sdk_version: Current Engine SDK version
        strict_mode: If True, reject engines without explicit version requirements

    Returns:
        Tuple of (compatible_engines, incompatible_results)
    """
    compatible_engines = []
    incompatible_results = []

    for engine in engines:
        try:
            # In strict mode, reject engines that don't specify requirements
            if strict_mode:
                has_explicit_requirements = (
                    getattr(engine, "required_core_version", "1.0.0") != "1.0.0"
                    or getattr(engine, "required_sdk_version", "1.0.0") != "1.0.0"
                )

                if not has_explicit_requirements:
                    result = EngineCompatibilityCheckResult(
                        engine_id=getattr(engine, "id", "unknown"),
                        engine_name=getattr(engine, "name", "Unknown"),
                        is_compatible=False,
                        missing_requirements=[
                            "No explicit version requirements specified"
                        ],
                        error_message=f"Engine '{getattr(engine, 'name', 'Unknown')}' ({getattr(engine, 'id', 'unknown')}) does not specify version requirements. "
                        f"Please add required_core_version and required_sdk_version class attributes.",
                    )
                    incompatible_results.append(result)
                    continue

            # Check compatibility
            result = check_engine_compatibility(
                engine, core_version, engine_sdk_version
            )

            if result.is_compatible:
                compatible_engines.append(engine)
            else:
                incompatible_results.append(result)

        except Exception as e:
            result = EngineCompatibilityCheckResult(
                engine_id=getattr(engine, "id", "unknown"),
                engine_name=getattr(engine, "name", "Unknown"),
                is_compatible=False,
                missing_requirements=[],
                error_message=f"Error validating engine: {str(e)}",
            )
            incompatible_results.append(result)

    return compatible_engines, incompatible_results


def print_engine_compatibility_report(
    compatible_engines: List,
    incompatible_results: List,
) -> None:
    """Print a formatted engine compatibility report."""
    print("=" * 70)
    print("Engine Compatibility Report")
    print("=" * 70)

    print(f"\n✓ Compatible: {len(compatible_engines)}")
    for engine in compatible_engines:
        engine_name = getattr(engine, "name", "Unknown")
        engine_id = getattr(engine, "id", "unknown")
        print(f"  - {engine_name} ({engine_id})")

    print(f"\n✗ Incompatible: {len(incompatible_results)}")
    for result in incompatible_results:
        print(f"  - {result.engine_name} ({result.engine_id})")
        if result.missing_requirements:
            for req in result.missing_requirements:
                print(f"    • {req}")
        if result.error_message:
            print(f"    Error: {result.error_message}")

    print("\n" + "=" * 70)


__all__ = [
    "EngineCompatibilityCheckResult",
    "parse_version",
    "check_engine_compatibility",
    "validate_engines_compatibility",
    "print_engine_compatibility_report",
]
