# PyCompiler ARK++ 3.2.3 - Supported Platform Matrix

## Officially Supported Platforms

This document outlines the officially supported and tested platforms for PyCompiler ARK++ 3.2.3.

### Operating Systems

| OS | Version | Architecture | Status | Notes |
|---|---|---|---|---|
| **Ubuntu** | 20.04 LTS | x64 | ✅ Supported | Primary development platform |
| **Ubuntu** | 22.04 LTS | x64 | ✅ Supported | Recommended for production |
| **Ubuntu** | 24.04 LTS | x64 | ✅ Supported | Latest LTS |
| **Windows** | 10 | x64 | ✅ Supported | Build 1909+ required |
| **Windows** | 11 | x64 | ✅ Supported | Recommended |
| **macOS** | 12 (Monterey) | x64, ARM64 | ✅ Supported | Intel and Apple Silicon |
| **macOS** | 13 (Ventura) | x64, ARM64 | ✅ Supported | Recommended |
| **macOS** | 14 (Sonoma) | x64, ARM64 | ✅ Supported | Latest |

### Python Versions

| Python Version | Status | Notes |
|---|---|---|
| **3.10** | ✅ Supported | Minimum required version |
| **3.11** | ✅ Supported | Recommended for performance |
| **3.12** | ✅ Supported | Latest stable |
| **3.13** | 🧪 Experimental | Beta support, not for production |

### Dependencies

#### Core Runtime Dependencies
- **PySide6**: 6.7.2+ (GUI framework)
- **psutil**: 5.9.0+ (System utilities)
- **PyYAML**: 6.0.0+ (Configuration)
- **jsonschema**: 4.18.0+ (Validation)
- **Pillow**: 9.0.0+ (Image processing)

#### Development Dependencies
- **pytest**: 7.4.0+ (Testing framework)
- **black**: 23.12.0+ (Code formatting)
- **ruff**: 0.1.9+ (Linting)
- **mypy**: 1.8.0+ (Type checking)

## Testing Matrix

Our CI/CD pipeline tests the following combinations:

### GitHub Actions Matrix
```yaml
os: [ubuntu-latest, macos-latest, windows-latest]
python-version: ['3.10', '3.11', '3.12']
```

### Manual Testing
- **Linux distributions**: Ubuntu, Debian, Fedora, CentOS/RHEL
- **Windows editions**: Home, Pro, Enterprise
- **macOS versions**: Intel and Apple Silicon variants

## Compatibility Notes

### Known Limitations
- **Windows 7/8/8.1**: Not supported (PySide6 requirement)
- **Python 3.9 and below**: Not supported
- **32-bit systems**: Not officially supported
- **ARM Linux**: Community support only

### Performance Recommendations
- **RAM**: Minimum 4GB, recommended 8GB+
- **Storage**: SSD recommended for better performance
- **CPU**: Multi-core recommended for parallel compilation

## Support Policy

### Long Term Support (LTS)
- **Current version**: 3.2.3 (supported until 2025-12-31)
- **Security updates**: Critical fixes for 18 months
- **Feature updates**: New features in minor releases

### End of Life Schedule
| Version | Release Date | End of Support |
|---|---|---|
| 3.2.x | 2024-01-01 | 2025-12-31 |
| 3.1.x | 2023-06-01 | 2024-12-31 |
| 3.0.x | 2023-01-01 | 2024-06-30 |

## Reporting Issues

If you encounter issues on a supported platform:
1. Check this matrix for compatibility
2. Verify your environment meets minimum requirements
3. Report issues via GitHub Issues with platform details
4. Include output of `python --version` and OS information

## Community Platforms

Platforms not listed above may work but are not officially tested. Community contributions for additional platform support are welcome.

---

*Last updated: 2024-01-15*
*Next review: 2024-04-15*