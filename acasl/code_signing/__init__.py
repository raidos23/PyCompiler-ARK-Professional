"""
ACASL Plugin: Code Signing
Provides cross-platform code signing capabilities for compiled artifacts.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ACASL Plugin Metadata
ACASL_PLUGIN = True
ACASL_ID = "code_signing"
ACASL_DESCRIPTION = "Cross-platform code signing for compiled artifacts"
ACASL_VERSION = "1.0.0"
ACASL_AUTHOR = "PyCompiler ARK++ Team"
ACASL_PRIORITY = 70  # After compilation, before packaging


def acasl_main(sctx: Any) -> bool:
    """
    Main ACASL entry point for code signing.
    
    Args:
        sctx: ACASL context object containing workspace and configuration
        
    Returns:
        bool: True if signing successful, False otherwise
    """
    try:
        print(f"[{ACASL_ID}] Starting code signing process...")
        
        # Get configuration
        config = getattr(sctx, 'config', {})
        signing_config = config.get('code_signing', {})
        
        if not signing_config.get('enabled', False):
            print(f"[{ACASL_ID}] Code signing disabled in configuration")
            return True
            
        # Find artifacts to sign
        artifacts = _find_artifacts(sctx)
        if not artifacts:
            print(f"[{ACASL_ID}] No artifacts found to sign")
            return True
            
        # Determine platform and sign accordingly
        platform = sys.platform.lower()
        
        if platform.startswith('win'):
            return _sign_windows(artifacts, signing_config)
        elif platform.startswith('darwin'):
            return _sign_macos(artifacts, signing_config)
        elif platform.startswith('linux'):
            return _sign_linux(artifacts, signing_config)
        else:
            print(f"[{ACASL_ID}] Unsupported platform for code signing: {platform}")
            return True  # Don't fail on unsupported platforms
            
    except Exception as e:
        print(f"[{ACASL_ID}] Error during code signing: {e}")
        return False


def _find_artifacts(sctx: Any) -> List[Path]:
    """Find compiled artifacts that need signing."""
    artifacts = []
    workspace = Path(sctx.workspace_root)
    dist_dir = workspace / "dist"
    
    if not dist_dir.exists():
        return artifacts
        
    # Common executable extensions by platform
    extensions = {
        'win32': ['.exe', '.dll', '.msi'],
        'darwin': ['.app', '.dmg', '.pkg'],
        'linux': ['']  # No extension for Linux executables
    }
    
    platform = sys.platform.lower()
    if platform.startswith('win'):
        exts = extensions['win32']
    elif platform.startswith('darwin'):
        exts = extensions['darwin']
    else:
        exts = extensions['linux']
    
    for ext in exts:
        if ext:
            artifacts.extend(dist_dir.glob(f"*{ext}"))
        else:
            # For Linux, find executable files
            for file in dist_dir.iterdir():
                if file.is_file() and os.access(file, os.X_OK):
                    artifacts.append(file)
                    
    return artifacts


def _sign_windows(artifacts: List[Path], config: Dict[str, Any]) -> bool:
    """Sign Windows executables using signtool."""
    cert_path = config.get('windows', {}).get('certificate_path')
    cert_password = config.get('windows', {}).get('certificate_password')
    timestamp_url = config.get('windows', {}).get('timestamp_url', 'http://timestamp.digicert.com')
    
    if not cert_path:
        print(f"[{ACASL_ID}] Windows certificate path not configured")
        return False
        
    if not Path(cert_path).exists():
        print(f"[{ACASL_ID}] Certificate file not found: {cert_path}")
        return False
    
    success = True
    for artifact in artifacts:
        if artifact.suffix.lower() in ['.exe', '.dll', '.msi']:
            cmd = [
                'signtool', 'sign',
                '/f', cert_path,
                '/t', timestamp_url,
                '/v'  # Verbose output
            ]
            
            if cert_password:
                cmd.extend(['/p', cert_password])
                
            cmd.append(str(artifact))
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    print(f"[{ACASL_ID}] Successfully signed: {artifact.name}")
                else:
                    print(f"[{ACASL_ID}] Failed to sign {artifact.name}: {result.stderr}")
                    success = False
            except subprocess.TimeoutExpired:
                print(f"[{ACASL_ID}] Timeout signing {artifact.name}")
                success = False
            except FileNotFoundError:
                print(f"[{ACASL_ID}] signtool not found. Install Windows SDK.")
                return False
                
    return success


def _sign_macos(artifacts: List[Path], config: Dict[str, Any]) -> bool:
    """Sign macOS applications using codesign."""
    identity = config.get('macos', {}).get('signing_identity')
    keychain = config.get('macos', {}).get('keychain_path')
    notarize = config.get('macos', {}).get('notarize', False)
    
    if not identity:
        print(f"[{ACASL_ID}] macOS signing identity not configured")
        return False
    
    success = True
    for artifact in artifacts:
        if artifact.suffix.lower() in ['.app', '.dmg', '.pkg']:
            cmd = ['codesign', '--sign', identity, '--verbose']
            
            if keychain:
                cmd.extend(['--keychain', keychain])
                
            cmd.append(str(artifact))
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    print(f"[{ACASL_ID}] Successfully signed: {artifact.name}")
                    
                    # Verify signature
                    verify_cmd = ['codesign', '--verify', '--verbose', str(artifact)]
                    verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
                    if verify_result.returncode != 0:
                        print(f"[{ACASL_ID}] Signature verification failed for {artifact.name}")
                        success = False
                        
                    # Notarize if requested
                    if notarize and artifact.suffix.lower() in ['.dmg', '.pkg']:
                        if not _notarize_macos(artifact, config):
                            success = False
                            
                else:
                    print(f"[{ACASL_ID}] Failed to sign {artifact.name}: {result.stderr}")
                    success = False
            except subprocess.TimeoutExpired:
                print(f"[{ACASL_ID}] Timeout signing {artifact.name}")
                success = False
            except FileNotFoundError:
                print(f"[{ACASL_ID}] codesign not found. Install Xcode Command Line Tools.")
                return False
                
    return success


def _notarize_macos(artifact: Path, config: Dict[str, Any]) -> bool:
    """Notarize macOS application with Apple."""
    profile = config.get('macos', {}).get('notarytool_profile')
    
    if not profile:
        print(f"[{ACASL_ID}] Notarytool profile not configured")
        return False
    
    try:
        # Submit for notarization
        cmd = [
            'xcrun', 'notarytool', 'submit',
            str(artifact),
            '--keychain-profile', profile,
            '--wait'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        if result.returncode == 0:
            print(f"[{ACASL_ID}] Successfully notarized: {artifact.name}")
            
            # Staple the notarization
            staple_cmd = ['xcrun', 'stapler', 'staple', str(artifact)]
            staple_result = subprocess.run(staple_cmd, capture_output=True, text=True)
            if staple_result.returncode == 0:
                print(f"[{ACASL_ID}] Successfully stapled: {artifact.name}")
                return True
            else:
                print(f"[{ACASL_ID}] Failed to staple {artifact.name}: {staple_result.stderr}")
                return False
        else:
            print(f"[{ACASL_ID}] Failed to notarize {artifact.name}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[{ACASL_ID}] Timeout during notarization of {artifact.name}")
        return False
    except FileNotFoundError:
        print(f"[{ACASL_ID}] notarytool not found. Install Xcode Command Line Tools.")
        return False


def _sign_linux(artifacts: List[Path], config: Dict[str, Any]) -> bool:
    """Sign Linux executables using GPG."""
    gpg_key = config.get('linux', {}).get('gpg_key_id')
    
    if not gpg_key:
        print(f"[{ACASL_ID}] GPG key ID not configured for Linux signing")
        return False
    
    success = True
    for artifact in artifacts:
        # Create detached signature
        sig_file = artifact.with_suffix(artifact.suffix + '.sig')
        
        cmd = [
            'gpg', '--detach-sign', '--armor',
            '--local-user', gpg_key,
            '--output', str(sig_file),
            str(artifact)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print(f"[{ACASL_ID}] Successfully signed: {artifact.name}")
                
                # Verify signature
                verify_cmd = ['gpg', '--verify', str(sig_file), str(artifact)]
                verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
                if verify_result.returncode != 0:
                    print(f"[{ACASL_ID}] Signature verification failed for {artifact.name}")
                    success = False
            else:
                print(f"[{ACASL_ID}] Failed to sign {artifact.name}: {result.stderr}")
                success = False
        except subprocess.TimeoutExpired:
            print(f"[{ACASL_ID}] Timeout signing {artifact.name}")
            success = False
        except FileNotFoundError:
            print(f"[{ACASL_ID}] gpg not found. Install GnuPG.")
            return False
            
    return success


# Configuration example for reference
EXAMPLE_CONFIG = {
    "code_signing": {
        "enabled": True,
        "windows": {
            "certificate_path": "path/to/certificate.p12",
            "certificate_password": "cert_password",
            "timestamp_url": "http://timestamp.digicert.com"
        },
        "macos": {
            "signing_identity": "Developer ID Application: Your Name",
            "keychain_path": "/path/to/keychain",
            "notarize": True,
            "notarytool_profile": "notarytool-profile"
        },
        "linux": {
            "gpg_key_id": "your-gpg-key-id"
        }
    }
}