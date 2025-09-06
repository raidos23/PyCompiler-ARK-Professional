# Release Process - PyCompiler ARK++ 3.2.3

## Overview

This document outlines the complete release process for PyCompiler ARK++, including versioning, testing, building, signing, and distribution procedures.

## Release Types

### Version Numbering
We follow [Semantic Versioning](https://semver.org/) (SemVer):
- **MAJOR.MINOR.PATCH** (e.g., 3.2.3)
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Release Channels
- **Stable**: Production-ready releases (e.g., 3.2.3)
- **Release Candidate**: Pre-release testing (e.g., 3.2.3-rc1)
- **Beta**: Feature-complete testing (e.g., 3.2.3-beta1)
- **Alpha**: Early development (e.g., 3.2.3-alpha1)

## Pre-Release Checklist

### Code Quality
- [ ] All CI checks pass (lint, format, types, tests)
- [ ] Code coverage ≥ 80%
- [ ] Security audit clean (bandit, pip-audit, safety)
- [ ] SBOM generated and reviewed
- [ ] Documentation updated

### Testing
- [ ] Unit tests pass on all supported platforms
- [ ] Integration tests complete
- [ ] Manual testing on primary platforms
- [ ] Performance regression tests
- [ ] Backward compatibility verified

### Dependencies
- [ ] All dependencies pinned in constraints.txt
- [ ] Security vulnerabilities addressed
- [ ] License compatibility verified
- [ ] Third-party notices updated

## Release Process

### 1. Preparation Phase

#### Update Version
```bash
# Update version in relevant files
# - pyproject.toml
# - main.py
# - docs/conf.py (if applicable)
```

#### Update Documentation
- [ ] Update CHANGELOG.md with new features, fixes, breaking changes
- [ ] Update README.md if needed
- [ ] Review and update API documentation
- [ ] Update SUPPORTED_MATRIX.md if platform support changed

#### Create Release Branch
```bash
git checkout -b release/3.2.3
git push origin release/3.2.3
```

### 2. Build Phase

#### Environment Setup
```bash
# Set reproducible build environment
export TZ=UTC
export LANG=C.UTF-8
export PYTHONHASHSEED=0
export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)
```

#### Clean Build
```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info/
python -m build --clean --sdist --wheel
```

#### Verify Build
```bash
# Test installation from built packages
python -m pip install dist/*.whl
python -c "import main; print('Build verification successful')"
```

### 3. Code Signing

#### Windows Code Signing
```bash
# Using signtool (requires certificate)
signtool sign /f certificate.p12 /p password /t http://timestamp.digicert.com dist/*.exe
signtool verify /pa dist/*.exe
```

#### macOS Code Signing
```bash
# Using codesign (requires Apple Developer certificate)
codesign --sign "Developer ID Application: Your Name" dist/*.app
codesign --verify --verbose dist/*.app

# Notarization (requires Apple Developer account)
xcrun notarytool submit dist/*.dmg --keychain-profile "notarytool-profile" --wait
xcrun stapler staple dist/*.dmg
```

#### Linux Code Signing (GPG)
```bash
# Sign with GPG
gpg --detach-sign --armor dist/*.tar.gz
gpg --verify dist/*.tar.gz.asc dist/*.tar.gz
```

### 4. Testing Phase

#### Smoke Tests
```bash
# Test on clean environments
docker run --rm -v $(pwd):/app python:3.11-slim bash -c "cd /app && pip install dist/*.whl && python -c 'import main'"
```

#### Platform Testing
- [ ] Test on Ubuntu 22.04 LTS
- [ ] Test on Windows 11
- [ ] Test on macOS 13+ (Intel and Apple Silicon)

### 5. Release Phase

#### Create Git Tag
```bash
git tag -a v3.2.3 -m "Release version 3.2.3"
git push origin v3.2.3
```

#### GitHub Release
The release workflow will automatically:
1. Build artifacts for all platforms
2. Generate checksums (SHA256SUMS.txt)
3. Create GitHub release with artifacts
4. Upload signed binaries

#### Manual Release Steps
If manual release is needed:
```bash
# Create release notes
gh release create v3.2.3 \
  --title "PyCompiler ARK++ v3.2.3" \
  --notes-file CHANGELOG.md \
  --draft

# Upload artifacts
gh release upload v3.2.3 dist/*
gh release upload v3.2.3 SHA256SUMS.txt
```

## Post-Release

### Verification
- [ ] Download and verify release artifacts
- [ ] Test installation from GitHub releases
- [ ] Verify checksums match
- [ ] Test on fresh systems

### Communication
- [ ] Update project website/documentation
- [ ] Announce on relevant channels
- [ ] Update package managers (if applicable)
- [ ] Close milestone in project management

### Cleanup
```bash
# Merge release branch back to main
git checkout main
git merge release/3.2.3
git branch -d release/3.2.3
git push origin --delete release/3.2.3
```

## Hotfix Process

For critical security or bug fixes:

1. Create hotfix branch from latest release tag
2. Apply minimal fix
3. Follow abbreviated release process
4. Increment PATCH version
5. Release immediately after testing

## Rollback Procedure

If a release needs to be rolled back:

1. Mark GitHub release as pre-release
2. Create hotfix with revert
3. Release new patch version
4. Communicate rollback to users

## Security Considerations

### Code Signing Certificates
- Store certificates securely (Azure Key Vault, AWS KMS)
- Use time-stamping for long-term validity
- Rotate certificates before expiration

### Release Artifacts
- Generate and verify checksums
- Sign all release artifacts
- Use HTTPS for all downloads
- Maintain audit trail

## Automation

### GitHub Actions
- Automated builds on tag push
- Multi-platform artifact generation
- Automatic checksum generation
- Security scanning integration

### ACASL Integration
Code signing and packaging can be automated using ACASL plugins:
- `code_sign_windows` - Windows Authenticode signing
- `code_sign_macos` - macOS codesign and notarization
- `generate_sbom` - Software Bill of Materials
- `package_installer` - Create platform installers

## Troubleshooting

### Common Issues
- **Build failures**: Check environment variables and dependencies
- **Signing failures**: Verify certificate validity and permissions
- **Upload failures**: Check network connectivity and authentication

### Recovery Procedures
- Keep previous release artifacts as backup
- Document rollback procedures
- Maintain emergency contact list

---

*This document should be reviewed and updated with each major release.*