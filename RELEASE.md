# Distribution Process - PyCompiler ARK++ 3.2.3

## Overview

This document describes how to build, sign, verify, and distribute artifacts for PyCompiler ARK++ 3.2.3.
There are no formal GitHub Releases or public tags; artifacts are produced and shared via internal channels.

## Versioning

- Canonical version: **3.2.3**
- Semantic Versioning is followed conceptually (MAJOR.MINOR.PATCH), but public release channels are not used.

## Pre-Distribution Checklist

### Code Quality
- [ ] All CI checks pass (lint, format, types, tests)
- [ ] Code coverage ≥ 80%
- [ ] Security audit clean (bandit, pip-audit, safety)
- [ ] SBOM generated and reviewed (optional)
- [ ] Documentation updated (README, CHANGELOG, docs/)

### Testing
- [ ] Unit tests pass on supported platforms
- [ ] Integration/smoke tests succeed
- [ ] Manual verification on primary platforms (Ubuntu, Windows, macOS)
- [ ] Backward compatibility validated where applicable

### Dependencies
- [ ] Dependencies pinned via `constraints.txt`
- [ ] No known vulnerabilities for production dependencies
- [ ] License compatibility reviewed

## Build Process

### Environment Setup
```bash
export TZ=UTC
export LANG=C.UTF-8
export PYTHONHASHSEED=0
export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)
```

### Clean Build
```bash
rm -rf dist/ build/ *.egg-info/
python -m build --clean --sdist --wheel
```

### Verify Build
```bash
python -m pip install dist/*.whl
python -c "import main; print('Build verification successful')"
```

## Code Signing (Optional)

### Windows (AuthentiCode)
```bash
signtool sign /f certificate.p12 /p password /t http://timestamp.digicert.com dist/*.exe
signtool verify /pa dist/*.exe
```

### macOS (codesign + notarization)
```bash
codesign --sign "Developer ID Application: Your Name" dist/*.app
codesign --verify --verbose dist/*.app

xcrun notarytool submit dist/*.dmg --keychain-profile "notarytool-profile" --wait
xcrun stapler staple dist/*.dmg
```

### Linux (GPG)
```bash
gpg --detach-sign --armor dist/*.tar.gz
gpg --verify dist/*.tar.gz.asc dist/*.tar.gz
```

## Checksums

Generate and verify checksums for distribution:
```bash
cd dist
sha256sum * > SHA256SUMS.txt
sha256sum -c SHA256SUMS.txt
```

## Distribution (No GitHub Releases)

- Artifacts are shared via internal channels (e.g., secure storage, internal package registry, or direct delivery).
- Include the following in the delivery bundle:
  - Built artifacts from `dist/`
  - `SHA256SUMS.txt` and (if applicable) signature files (`.asc`)
  - Minimal README with installation/usage notes if needed

Example packaging:
```bash
# Create a distributable archive
cd dist
zip -r ../pycompiler-arkpp-3.2.3-artifacts.zip .
```

## Post-Distribution

### Verification
- [ ] Consumer verifies checksums and signatures
- [ ] Installation tests on clean environments
- [ ] Smoke tests across target OSes

### Communication
- [ ] Update internal documentation/portals
- [ ] Notify stakeholders of availability and changes

## Automation

### CI (optional but recommended)
- Build and test on tag or main branch updates
- Multi-platform artifact jobs (Ubuntu, Windows, macOS)
- Security scanning integrated in pipeline

### ACASL Integration
- Packaging, signing, or SBOM generation can be automated with ACASL plugins:
  - `code_sign_windows` – Windows Authenticode signing
  - `code_sign_macos` – macOS codesign and notarization
  - `generate_sbom` – Software Bill of Materials
  - `package_installer` – Create platform installers

## Troubleshooting

### Common Issues
- Build failures: verify environment variables, toolchain, and pinned deps
- Signing failures: check certificate validity, access rights, and timestamps
- Verification failures: re-generate checksums and ensure no file corruption

### Recovery
- Keep previous artifacts for rollback
- Document remediation steps
- Maintain emergency contacts

---

*This document reflects a distribution workflow without public releases. Update as internal processes evolve.*
