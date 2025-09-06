"""
ACASL Plugin: SBOM Generator
Generates Software Bill of Materials (SBOM) for compiled artifacts.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ACASL Plugin Metadata
ACASL_PLUGIN = True
ACASL_ID = "sbom_generator"
ACASL_DESCRIPTION = "Generate Software Bill of Materials (SBOM) for compiled artifacts"
ACASL_VERSION = "1.0.0"
ACASL_AUTHOR = "PyCompiler ARK++ Team"
ACASL_PRIORITY = 75  # After compilation and signing, before final packaging


def acasl_main(sctx: Any) -> bool:
    """
    Main ACASL entry point for SBOM generation.

    Args:
        sctx: ACASL context object containing workspace and configuration

    Returns:
        bool: True if SBOM generation successful, False otherwise
    """
    try:
        print(f"[{ACASL_ID}] Starting SBOM generation...")

        # Get configuration
        config = getattr(sctx, 'config', {})
        sbom_config = config.get('sbom', {})

        if not sbom_config.get('enabled', True):  # Enabled by default
            print(f"[{ACASL_ID}] SBOM generation disabled in configuration")
            return True

        workspace = Path(sctx.workspace_root)

        # Generate SBOM using multiple methods
        success = True

        # Method 1: CycloneDX for Python dependencies
        if sbom_config.get('cyclonedx', True):
            success &= _generate_cyclonedx_sbom(workspace, sbom_config)

        # Method 2: Custom SBOM with project metadata
        if sbom_config.get('custom', True):
            success &= _generate_custom_sbom(workspace, sctx, sbom_config)

        # Method 3: SPDX format (if requested)
        if sbom_config.get('spdx', False):
            success &= _generate_spdx_sbom(workspace, sctx, sbom_config)

        if success:
            print(f"[{ACASL_ID}] SBOM generation completed successfully")
        else:
            print(f"[{ACASL_ID}] SBOM generation completed with errors")

        return success

    except Exception as e:
        print(f"[{ACASL_ID}] Error during SBOM generation: {e}")
        return False


def _generate_cyclonedx_sbom(workspace: Path, config: Dict[str, Any]) -> bool:
    """Generate SBOM using CycloneDX for Python dependencies."""
    try:
        requirements_file = workspace / "requirements.txt"
        if not requirements_file.exists():
            print(f"[{ACASL_ID}] No requirements.txt found, skipping CycloneDX SBOM")
            return True

        output_dir = workspace / "dist"
        output_dir.mkdir(exist_ok=True)

        # Generate CycloneDX SBOM
        output_file = output_dir / "sbom-cyclonedx.json"

        cmd = [
            sys.executable, "-m", "cyclonedx_py",
            "-r", str(requirements_file),
            "-o", str(output_file),
            "--format", "json"
        ]

        # Add additional options if configured
        if config.get('include_dev_dependencies', False):
            cmd.append("--include-dev")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print(f"[{ACASL_ID}] CycloneDX SBOM generated: {output_file}")

            # Also generate XML format if requested
            if config.get('xml_format', False):
                xml_file = output_dir / "sbom-cyclonedx.xml"
                xml_cmd = cmd[:-2] + ["-o", str(xml_file), "--format", "xml"]
                xml_result = subprocess.run(xml_cmd, capture_output=True, text=True, timeout=300)
                if xml_result.returncode == 0:
                    print(f"[{ACASL_ID}] CycloneDX SBOM XML generated: {xml_file}")

            return True
        else:
            print(f"[{ACASL_ID}] Failed to generate CycloneDX SBOM: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[{ACASL_ID}] Timeout generating CycloneDX SBOM")
        return False
    except FileNotFoundError:
        print(f"[{ACASL_ID}] cyclonedx-py not found. Install with: pip install cyclonedx-py")
        return False
    except Exception as e:
        print(f"[{ACASL_ID}] Error generating CycloneDX SBOM: {e}")
        return False


def _generate_custom_sbom(workspace: Path, sctx: Any, config: Dict[str, Any]) -> bool:
    """Generate custom SBOM with project-specific information."""
    try:
        output_dir = workspace / "dist"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "sbom-custom.json"

        # Collect project information
        project_info = _collect_project_info(workspace, sctx)

        # Collect dependency information
        dependencies = _collect_dependencies(workspace)

        # Collect artifact information
        artifacts = _collect_artifacts(output_dir)

        # Build SBOM structure
        sbom = {
            "bomFormat": "PyCompiler-ARK-SBOM",
            "specVersion": "1.0",
            "serialNumber": f"urn:uuid:{_generate_uuid()}",
            "version": 1,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "tools": [
                    {
                        "vendor": "PyCompiler ARK++",
                        "name": "SBOM Generator",
                        "version": "3.2.3"
                    }
                ],
                "component": project_info
            },
            "components": dependencies,
            "artifacts": artifacts,
            "buildInfo": _collect_build_info(sctx),
            "vulnerabilities": []  # Placeholder for future vulnerability scanning
        }

        # Write SBOM to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(sbom, f, indent=2, ensure_ascii=False)

        print(f"[{ACASL_ID}] Custom SBOM generated: {output_file}")
        return True

    except Exception as e:
        print(f"[{ACASL_ID}] Error generating custom SBOM: {e}")
        return False


def _generate_spdx_sbom(workspace: Path, sctx: Any, config: Dict[str, Any]) -> bool:
    """Generate SPDX format SBOM."""
    try:
        output_dir = workspace / "dist"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "sbom-spdx.json"

        # Basic SPDX structure
        spdx_doc = {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": f"PyCompiler ARK++ Project SBOM",
            "documentNamespace": f"https://pycompiler-ark.org/spdx/{_generate_uuid()}",
            "creationInfo": {
                "created": datetime.utcnow().isoformat() + "Z",
                "creators": ["Tool: PyCompiler ARK++ SBOM Generator"],
                "licenseListVersion": "3.21"
            },
            "packages": [],
            "relationships": []
        }

        # Add project as main package
        project_info = _collect_project_info(workspace, sctx)
        main_package = {
            "SPDXID": "SPDXRef-Package-Main",
            "name": project_info.get("name", "Unknown"),
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "versionInfo": project_info.get("version", "Unknown")
        }
        spdx_doc["packages"].append(main_package)

        # Add dependencies
        dependencies = _collect_dependencies(workspace)
        for i, dep in enumerate(dependencies):
            pkg_id = f"SPDXRef-Package-{i+1}"
            package = {
                "SPDXID": pkg_id,
                "name": dep.get("name", "Unknown"),
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "versionInfo": dep.get("version", "Unknown")
            }
            spdx_doc["packages"].append(package)

            # Add relationship
            relationship = {
                "spdxElementId": "SPDXRef-Package-Main",
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": pkg_id
            }
            spdx_doc["relationships"].append(relationship)

        # Write SPDX document
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(spdx_doc, f, indent=2, ensure_ascii=False)

        print(f"[{ACASL_ID}] SPDX SBOM generated: {output_file}")
        return True

    except Exception as e:
        print(f"[{ACASL_ID}] Error generating SPDX SBOM: {e}")
        return False


def _collect_project_info(workspace: Path, sctx: Any) -> Dict[str, Any]:
    """Collect project information from various sources."""
    info = {
        "type": "application",
        "name": "PyCompiler ARK++ Project",
        "version": "unknown",
        "description": "",
        "licenses": [],
        "supplier": "",
        "author": ""
    }

    # Try to get info from pyproject.toml
    pyproject_file = workspace / "pyproject.toml"
    if pyproject_file.exists():
        try:
            import tomli if sys.version_info < (3, 11) else tomllib

            with open(pyproject_file, 'rb') as f:
                if sys.version_info >= (3, 11):
                    import tomllib
                    data = tomllib.load(f)
                else:
                    import tomli
                    data = tomli.load(f)

            project = data.get("project", {})
            info.update({
                "name": project.get("name", info["name"]),
                "version": project.get("version", info["version"]),
                "description": project.get("description", info["description"]),
                "author": ", ".join([author.get("name", "") for author in project.get("authors", [])]),
            })

            # Extract license info
            license_info = project.get("license", {})
            if isinstance(license_info, dict) and "file" in license_info:
                license_file = workspace / license_info["file"]
                if license_file.exists():
                    info["licenses"].append({
                        "license": {"name": "See LICENSE file"},
                        "expression": "See LICENSE file"
                    })

        except Exception as e:
            print(f"[{ACASL_ID}] Warning: Could not parse pyproject.toml: {e}")

    return info


def _collect_dependencies(workspace: Path) -> List[Dict[str, Any]]:
    """Collect dependency information from requirements files."""
    dependencies = []

    # Parse requirements.txt
    req_file = workspace / "requirements.txt"
    if req_file.exists():
        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Simple parsing - could be enhanced
                        if '>=' in line:
                            name, version = line.split('>=', 1)
                            version = version.split(',')[0].split(';')[0].strip()
                        elif '==' in line:
                            name, version = line.split('==', 1)
                            version = version.split(';')[0].strip()
                        else:
                            name = line.split(';')[0].strip()
                            version = "unknown"

                        dependencies.append({
                            "type": "library",
                            "name": name.strip(),
                            "version": version,
                            "scope": "required",
                            "licenses": []
                        })
        except Exception as e:
            print(f"[{ACASL_ID}] Warning: Could not parse requirements.txt: {e}")

    return dependencies


def _collect_artifacts(output_dir: Path) -> List[Dict[str, Any]]:
    """Collect information about generated artifacts."""
    artifacts = []

    if not output_dir.exists():
        return artifacts

    for file_path in output_dir.iterdir():
        if file_path.is_file() and not file_path.name.startswith('sbom-'):
            try:
                stat = file_path.stat()
                artifacts.append({
                    "name": file_path.name,
                    "path": str(file_path.relative_to(output_dir.parent)),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "checksum": _calculate_checksum(file_path),
                    "type": _determine_file_type(file_path)
                })
            except Exception as e:
                print(f"[{ACASL_ID}] Warning: Could not process artifact {file_path}: {e}")

    return artifacts


def _collect_build_info(sctx: Any) -> Dict[str, Any]:
    """Collect build environment information."""
    import platform

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor()
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler()
        },
        "environment": {
            "user": getattr(sctx, 'build_user', 'unknown'),
            "workspace": str(getattr(sctx, 'workspace_root', 'unknown'))
        }
    }


def _calculate_checksum(file_path: Path) -> Dict[str, str]:
    """Calculate file checksums."""
    import hashlib

    checksums = {}

    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            checksums['sha256'] = hashlib.sha256(content).hexdigest()
            checksums['md5'] = hashlib.md5(content).hexdigest()
    except Exception as e:
        print(f"[{ACASL_ID}] Warning: Could not calculate checksum for {file_path}: {e}")

    return checksums


def _determine_file_type(file_path: Path) -> str:
    """Determine file type based on extension and content."""
    suffix = file_path.suffix.lower()

    type_map = {
        '.exe': 'executable',
        '.dll': 'library',
        '.so': 'library',
        '.dylib': 'library',
        '.app': 'application',
        '.dmg': 'installer',
        '.msi': 'installer',
        '.pkg': 'installer',
        '.deb': 'installer',
        '.rpm': 'installer',
        '.tar.gz': 'archive',
        '.zip': 'archive',
        '.whl': 'package',
        '.egg': 'package'
    }

    return type_map.get(suffix, 'file')


def _generate_uuid() -> str:
    """Generate a UUID for SBOM identification."""
    import uuid
    return str(uuid.uuid4())


# Configuration example for reference
EXAMPLE_CONFIG = {
    "sbom": {
        "enabled": True,
        "cyclonedx": True,
        "custom": True,
        "spdx": False,
        "xml_format": False,
        "include_dev_dependencies": False
    }
}
