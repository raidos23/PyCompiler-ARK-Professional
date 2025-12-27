# BCASL Configuration Guide

## Overview

BCASL (Before-Compilation Actions System Loader) is now fully integrated with the ARK global configuration system. The activation/deactivation of BCASL is managed through the global `ARK_Main_Config.yml` file, while BCASL-specific settings can be configured in a dedicated YAML or JSON file.

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

### 2. BCASL-Specific Configuration

BCASL can be configured using either YAML or JSON format. The loader checks for files in this order:

1. `bcasl.yaml` (preferred)
2. `bcasl.yml`
3. `bcasl.json`
4. `.bcasl.json`

#### YAML Configuration Example (`bcasl.yaml`)

```yaml
# BCASL Configuration File
# This file defines BCASL-specific settings

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

#### JSON Configuration Example (`bcasl.json`)

```json
{
  "file_patterns": ["**/*.py"],
  "exclude_patterns": [
    "**/__pycache__/**",
    "**/*.pyc",
    ".git/**",
    "venv/**",
    ".venv/**"
  ],
  "options": {
    "sandbox": true,
    "plugin_parallelism": 0,
    "iter_files_cache": true
  },
  "plugins": {
    "Cleaner": {
      "enabled": true,
      "priority": 0
    }
  },
  "plugin_order": ["Cleaner"]
}
```

## Configuration Priority

The configuration is resolved in the following order:

1. **BCASL-specific file** (bcasl.yaml/yml or bcasl.json)
   - Provides BCASL-specific settings
   - Defines plugin order and individual plugin settings

2. **ARK Global Configuration** (ARK_Main_Config.yml)
   - Overrides BCASL enabled/disabled state
   - Sets plugin timeout
   - Provides file patterns and exclusion patterns

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

### Step 2: Create bcasl.yaml

```yaml
file_patterns:
  - "**/*.py"

exclude_patterns:
  - "**/__pycache__/**"
  - "**/*.pyc"

options:
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
4. **Save Configuration**: Changes are saved to `bcasl.json`

**Note**: The global enabled/disabled state is controlled by `ARK_Main_Config.yml`, but can be overridden in the UI by modifying `bcasl.json`.

## Migration from Old Configuration

If you have an existing `bcasl.json` file:

1. The file will continue to work as before
2. To use YAML format, create a `bcasl.yaml` file (it will take precedence)
3. To manage BCASL activation globally, add the `plugins` section to `ARK_Main_Config.yml`

## Troubleshooting

### BCASL is not running

1. Check if `bcasl_enabled: true` in `ARK_Main_Config.yml`
2. Verify the configuration file syntax (YAML/JSON)
3. Check the application logs for error messages
4. Ensure plugins are properly installed in the `Plugins/` directory

### Configuration not being applied

1. Verify the configuration file is in the workspace root directory
2. Check file permissions (must be readable)
3. Ensure YAML/JSON syntax is valid
4. Restart the application to reload configuration

### Plugins not executing in expected order

1. Check the `plugin_order` list in `bcasl.yaml`
2. Verify plugin IDs match exactly (case-sensitive)
3. Use the BCASL Loader UI to reorder plugins visually
4. Check individual plugin `enabled` status

## See Also

- [ARK Configuration Guide](./ARK_Configuration.md)
- [How to Create a BCASL Plugin](./how_to_create_a_BC_plugin.md)
