# BCASL Configuration Guide

## Overview

**Scope:** This guide is specifically for configuring **BC (Before Compilation) plugins** that use the BCASL system.

BCASL (Before-Compilation Actions System Loader) is fully integrated with the ARK global configuration system. This configuration system controls **BC plugins** - pre-compilation plugins that run before the build process starts.

The activation/deactivation of BCASL (and all BC plugins) is managed through the global `ARK_Main_Config.yml` file, while BCASL-specific settings are configured in a dedicated **YML file only** (YAML format).

**Note:** This configuration does **not** apply to compilation engines (PyInstaller, Nuitka, etc.). Engine configuration is managed separately in `ARK_Main_Config.yml`. See [ARK Configuration Guide](./ARK_Configuration.md) for engine configuration.

## Configuration Files

### 1. Global ARK Configuration (`ARK_Main_Config.yml`)

The global ARK configuration file now includes a `plugins` section that controls BCASL behavior:

```yaml
# PLUGINS CONFIGURATION
plugins:
  bcasl_enabled: true          # Enable/disable BCASL globally
  plugin_timeout: 0.0          # Plugin timeout in seconds (0 = unlimited)
```

**Parameters:**
- `bcasl_enabled` (boolean): Controls whether BCASL pre-compilation actions are executed
  - `true`: BCASL plugins will run before compilation
  - `false`: BCASL will be skipped entirely
- `plugin_timeout` (float): Maximum execution time for each plugin in seconds
  - `0.0` or negative: No timeout (unlimited execution)
  - Positive value: Timeout in seconds

### 2. BCASL-Specific Configuration (YML ONLY)

BCASL configuration uses **YML format only** (no JSON, no YAML). The loader checks for files in this order:

1. `bcasl.yml` (preferred)
2. `.bcasl.yml` (hidden file)

#### YML Configuration Example (`bcasl.yml`)

```yaml
# BCASL Configuration File
# This file defines BCASL-specific settings
# Format: YML only (no JSON, no YAML)

# File patterns for plugin processing
file_patterns:
  - "**/*.py"

exclude_patterns:
  - "**/__pycache__/**"
  - "**/*.pyc"
  - ".git/**"
  - "venv/**"
  - ".venv/**"

# BCASL options
options:
  enabled: true                    # Enable/disable BCASL (can be overridden by ARK config)
  plugin_timeout_s: 0.0            # Plugin timeout in seconds (0 = unlimited)
  sandbox: true                    # Run plugins in sandbox mode
  plugin_parallelism: 0            # 0 = sequential, >0 = parallel
  iter_files_cache: true           # Cache file iteration results

# Plugin-specific configuration
plugins:
  Cleaner:
    enabled: true
    priority: 0

# Plugin execution order
plugin_order:
  - Cleaner
```

## Configuration Priority

The configuration is resolved in the following order:

1. **BCASL-specific file** (bcasl.yml or .bcasl.yml)
   - Provides BCASL-specific settings
   - Defines plugin order and individual plugin settings
   - **Format: YML only**

2. **ARK Global Configuration** (ARK_Main_Config.yml)
   - Overrides BCASL enabled/disabled state
   - Sets plugin timeout
   - Provides file patterns and exclusion patterns
   - **Format: YML only**

3. **Default Configuration**
   - Used if no configuration files are found
   - BCASL is enabled by default
   - Default timeout is 0 (unlimited)

## Configuration Merging

When both BCASL and ARK configurations exist:

- **File patterns**: Merged from both sources
- **Exclusion patterns**: Combined (union of both sets)
- **BCASL enabled flag**: ARK configuration takes precedence
- **Plugin timeout**: ARK configuration takes precedence
- **Plugin order**: From BCASL configuration

## Example: Complete Setup

### Step 1: Create ARK_Main_Config.yml

```yaml
# ARK Main Configuration
plugins:
  bcasl_enabled: true
  plugin_timeout: 30.0  # 30 seconds timeout

exclusion_patterns:
  - "**/__pycache__/**"
  - "**/*.pyc"
  - ".git/**"
  - "venv/**"
  - ".venv/**"
  - "build/**"
  - "dist/**"

inclusion_patterns:
  - "**/*.py"
```

### Step 2: Create bcasl.yml

```yaml
file_patterns:
  - "**/*.py"

exclude_patterns:
  - "**/__pycache__/**"
  - "**/*.pyc"

options:
  enabled: true
  plugin_timeout_s: 0.0
  sandbox: true
  plugin_parallelism: 0
  iter_files_cache: true

plugins:
  Cleaner:
    enabled: true
    priority: 0

plugin_order:
  - Cleaner
```

## Disabling BCASL

To disable BCASL globally, set `bcasl_enabled: false` in `ARK_Main_Config.yml`:

```yaml
plugins:
  bcasl_enabled: false
```

When BCASL is disabled:
- No pre-compilation actions will be executed
- The compilation process will proceed directly to the compiler phase
- A message will be logged indicating BCASL was skipped

## Environment Variables

You can also control BCASL timeout via environment variable:

```bash
export PYCOMPILER_BCASL_PLUGIN_TIMEOUT=60
```

Priority for timeout resolution:
1. Environment variable `PYCOMPILER_BCASL_PLUGIN_TIMEOUT`
2. ARK configuration `plugins.plugin_timeout`
3. BCASL configuration `options.plugin_timeout_s`
4. Default: 0 (unlimited)

## UI Configuration

The BCASL Loader dialog allows you to:

1. **Enable/Disable BCASL**: Toggle the global BCASL switch
2. **Enable/Disable Individual Plugins**: Check/uncheck plugins
3. **Reorder Plugins**: Drag plugins up/down to change execution order
4. **Save Configuration**: Changes are saved to `bcasl.yml` (YML format only)

**Note**: The global enabled/disabled state is controlled by `ARK_Main_Config.yml`, but can be overridden in the UI by modifying `bcasl.yml`.

## File Format Requirements

### ✅ Supported Formats
- **YML files**: `bcasl.yml`, `.bcasl.yml`
- **ARK Config**: `ARK_Main_Config.yml`, `ARK_Main_Config.yaml`, `.ARK_Main_Config.yml`, `.ARK_Main_Config.yaml`

### ❌ NOT Supported
- JSON files (`.json`)
- YAML files (`.yaml`) for BCASL config
- Any other format

## Migration from Old Configuration

If you have an existing `bcasl.json` file:

1. **The JSON file will be ignored** - BCASL now uses YML format only
2. To migrate your configuration:
   - Convert your `bcasl.json` to `bcasl.yml` format
   - Use the BCASL Loader UI to reconfigure plugins
   - Save the new configuration (automatically saved as `bcasl.yml`)
3. To manage BCASL activation globally, add the `plugins` section to `ARK_Main_Config.yml`

## Troubleshooting

### BCASL is not running

1. Check if `bcasl_enabled: true` in `ARK_Main_Config.yml`
2. Verify the configuration file is in YML format (not JSON)
3. Check the application logs for error messages
4. Ensure plugins are properly installed in the `Plugins/` directory

### Configuration not being applied

1. Verify the configuration file is in the workspace root directory
2. Check file permissions (must be readable)
3. Ensure YML syntax is valid (proper indentation, no tabs)
4. Restart the application to reload configuration
5. Verify you're using `.yml` extension (not `.yaml` or `.json`)

### Plugins not executing in expected order

1. Check the `plugin_order` list in `bcasl.yml`
2. Verify plugin IDs match exactly (case-sensitive)
3. Use the BCASL Loader UI to reorder plugins visually
4. Check individual plugin `enabled` status

## See Also

- [How to Create a BCASL Plugin](./how_to_create_a_BC_plugin.md) - Complete BC plugin development guide
- [ARK Configuration Guide](./ARK_Configuration.md) - Global configuration system (includes engine configuration)
- [About SDKs](./About_Sdks.md) - Overview of Plugins_SDK (BC plugins) and Engine SDK
