#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════════
# PyCompiler ARK - Test Launcher Script
# ═══════════════════════════════════════════════════════════════════════════════
# This script runs all tests for the PyCompiler ARK project

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# ══════════════════════════════════════════════════════════════════════���════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_test() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

print_skip() {
    echo -e "${YELLOW}⊘ $1${NC}"
    ((TESTS_SKIPPED++))
}

# ════════════════════════════════════════════════════���══════════════════════════
# Test Functions
# ═══════════════════════════════════════════════════════════════════════════════

# Disabled: Only pytest tests are run now
# test_python_syntax() {
#     print_header "Python Syntax Validation"
#     
#     local python_files=(
#         "Core/ark_config_loader.py"
#         "bcasl/Loader.py"
#         "bcasl/Base.py"
#         "bcasl/executor.py"
#         "bcasl/tagging.py"
#     )
#     
#     for file in "${python_files[@]}"; do
#         if [ -f "$file" ]; then
#             print_test "Checking $file"
#             if python3 -m py_compile "$file" 2>/dev/null; then
#                 print_success "$file syntax is valid"
#             else
#                 print_error "$file has syntax errors"
#             fi
#         else
#             print_skip "$file not found"
#         fi
#     done
# }

# test_yaml_files() {
#     print_header "YAML Configuration Files"
#     
#     local yaml_files=(
#         "bcasl.yaml"
#         "ARK_Main_Config.yml.example"
#     )
#     
#     for file in "${yaml_files[@]}"; do
#         if [ -f "$file" ]; then
#             print_test "Validating $file"
#             if python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
#                 print_success "$file is valid YAML"
#             else
#                 print_error "$file has YAML syntax errors"
#             fi
#         else
#             print_skip "$file not found"
#         fi
#     done
# }

# test_imports() {
#     print_header "Module Imports"
#     
#     print_test "Testing Core.ark_config_loader import"
#     if python3 -c "from Core.ark_config_loader import load_ark_config, DEFAULT_CONFIG" 2>/dev/null; then
#         print_success "Core.ark_config_loader imports successfully"
#     else
#         print_error "Core.ark_config_loader import failed"
#     fi
#     
#     print_test "Testing bcasl.Loader import"
#     if python3 -c "from bcasl.Loader import _load_workspace_config" 2>/dev/null; then
#         print_success "bcasl.Loader imports successfully"
#     else
#         print_error "bcasl.Loader import failed"
#     fi
# }

# test_ark_config() {
#     print_header "ARK Configuration Loader"
#     
#     print_test "Checking DEFAULT_CONFIG has plugins section"
#     if python3 << 'PYTHON_TEST' 2>/dev/null
# from Core.ark_config_loader import DEFAULT_CONFIG
# assert "plugins" in DEFAULT_CONFIG, "plugins section missing"
# assert "bcasl_enabled" in DEFAULT_CONFIG["plugins"], "bcasl_enabled missing"
# assert "plugin_timeout" in DEFAULT_CONFIG["plugins"], "plugin_timeout missing"
# print("OK")
# PYTHON_TEST
#     then
#         print_success "DEFAULT_CONFIG has plugins section"
#     else
#         print_error "DEFAULT_CONFIG plugins section validation failed"
#     fi
#     
#     print_test "Testing load_ark_config function"
#     if python3 << 'PYTHON_TEST' 2>/dev/null
# from Core.ark_config_loader import load_ark_config
# from pathlib import Path
# config = load_ark_config(str(Path.cwd()))
# assert isinstance(config, dict), "Config should be a dictionary"
# assert "plugins" in config, "plugins section missing from loaded config"
# print("OK")
# PYTHON_TEST
#     then
#         print_success "load_ark_config works correctly"
#     else
#         print_error "load_ark_config test failed"
#     fi
# }

# test_bcasl_yaml_support() {
#     print_header "BCASL YAML Support"
#     
#     print_test "Testing YAML file reading"
#     if python3 << 'PYTHON_TEST' 2>/dev/null
# import yaml
# from pathlib import Path
# yaml_file = Path("bcasl.yaml")
# if yaml_file.exists():
#     with open(yaml_file) as f:
#         config = yaml.safe_load(f)
#     assert isinstance(config, dict), "bcasl.yaml should be a dictionary"
#     print("OK")
# else:
#     print("SKIP")
# PYTHON_TEST
#     then
#         print_success "YAML file reading works"
#     else
#         print_error "YAML file reading failed"
#     fi
# }

# test_bcasl_loader() {
#     print_header "BCASL Loader Integration"
#     
#     print_test "Testing _load_workspace_config function"
#     if python3 << 'PYTHON_TEST' 2>/dev/null
# from bcasl.Loader import _load_workspace_config
# from pathlib import Path
# config = _load_workspace_config(Path.cwd())
# assert isinstance(config, dict), "Config should be a dictionary"
# expected_keys = ["file_patterns", "exclude_patterns", "options", "plugins", "plugin_order"]
# for key in expected_keys:
#     assert key in config, f"Missing key: {key}"
# print("OK")
# PYTHON_TEST
#     then
#         print_success "_load_workspace_config works correctly"
#     else
#         print_error "_load_workspace_config test failed"
#     fi
#     
#     print_test "Testing BCASL enabled flag"
#     if python3 << 'PYTHON_TEST' 2>/dev/null
# from bcasl.Loader import _load_workspace_config
# from pathlib import Path
# config = _load_workspace_config(Path.cwd())
# options = config.get("options", {})
# assert "enabled" in options, "options.enabled missing"
# print("OK")
# PYTHON_TEST
#     then
#         print_success "BCASL enabled flag is present"
#     else
#         print_error "BCASL enabled flag test failed"
#     fi
# }

# test_configuration_files() {
#     print_header "Configuration Files Existence"
#     
#     local files=(
#         "docs/BCASL_Configuration.md"
#         "bcasl.yaml"
#         "ARK_Main_Config.yml.example"
#         "BCASL_UPDATE.md"
#         "IMPLEMENTATION_SUMMARY.md"
#     )
#     
#     for file in "${files[@]}"; do
#         print_test "Checking $file"
#         if [ -f "$file" ]; then
#             print_success "$file exists"
#         else
#             print_error "$file not found"
#         fi
#     done
# }

# test_bcasl_config_script() {
#     print_header "BCASL Configuration Test Script"
#     
#     if [ -f "test_bcasl_config.py" ]; then
#         print_test "Running test_bcasl_config.py"
#         if python3 test_bcasl_config.py 2>&1 | grep -q "Results: .* passed"; then
#             print_success "test_bcasl_config.py passed"
#         else
#             print_error "test_bcasl_config.py failed"
#         fi
#     else
#         print_skip "test_bcasl_config.py not found"
#     fi
# }

# test_gitignore() {
#     print_header "Git Configuration"
#     
#     print_test "Checking .gitignore for bcasl.json"
#     if grep -q "bcasl.json" .gitignore; then
#         print_success "bcasl.json is in .gitignore"
#     else
#         print_error "bcasl.json not found in .gitignore"
#     fi
# }

# ═══════════════════════════════════════════════════════��═══════════════════════
# Main Test Execution
# ═══════════════════════════════════════════════════════════════════════════════

# Run tests located in the Tests directory using pytest (if available) or unittest
# Updates global counters TESTS_PASSED/FAILED/SKIPPED based on parsed results
# and prints a concise outcome for the suite.
test_python_tests_dir() {
    print_header "Python Tests in Tests/"
    
    if [ -d "Tests" ]; then
        if command -v pytest >/dev/null 2>&1; then
            print_test "Running pytest in Tests/"
            local output
            output=$(pytest -q Tests 2>&1)
            local exit_code=$?
            echo "$output"
            # Attempt to parse summary like: "3 passed, 1 failed, 2 skipped in ..."
            local summary
            summary=$(echo "$output" | grep -E "^[0-9].*(passed|failed|skipped|xpassed|xfailed)")
            if [ -n "$summary" ]; then
                local p f s
                p=$(echo "$summary" | grep -oE '([0-9]+) passed' | grep -oE '[0-9]+' | tail -n1)
                f=$(echo "$summary" | grep -oE '([0-9]+) failed' | grep -oE '[0-9]+' | tail -n1)
                s=$(echo "$summary" | grep -oE '([0-9]+) skipped' | grep -oE '[0-9]+' | tail -n1)
                [ -z "$p" ] && p=0
                [ -z "$f" ] && f=0
                [ -z "$s" ] && s=0
                TESTS_PASSED=$((TESTS_PASSED + p))
                TESTS_FAILED=$((TESTS_FAILED + f))
                TESTS_SKIPPED=$((TESTS_SKIPPED + s))
            fi
            if [ $exit_code -eq 0 ]; then
                print_success "pytest in Tests passed"
            else
                print_error "pytest in Tests failed"
            fi
        else
            print_test "pytest not found, using unittest discovery"
            local uout
            uout=$(python3 - <<'PY'
import unittest, sys
suite = unittest.defaultTestLoader.discover('Tests')
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
skipped = len(getattr(result, 'skipped', []))
print(f"SUMMARY: {result.testsRun} run, {len(result.failures)+len(result.errors)} failed, {skipped} skipped")
sys.exit(0 if result.wasSuccessful() else 1)
PY
)
            local exit_code=$?
            echo "$uout"
            # Parse: SUMMARY: N run, X failed, Y skipped
            local run failed skipped
            run=$(echo "$uout" | grep -oE 'SUMMARY: ([0-9]+) run' | grep -oE '[0-9]+' | tail -n1)
            failed=$(echo "$uout" | grep -oE ', ([0-9]+) failed' | grep -oE '[0-9]+' | tail -n1)
            skipped=$(echo "$uout" | grep -oE ', ([0-9]+) skipped' | grep -oE '[0-9]+' | tail -n1)
            [ -z "$run" ] && run=0
            [ -z "$failed" ] && failed=0
            [ -z "$skipped" ] && skipped=0
            # passed = run - failed - skipped
            local passed=$((run - failed - skipped))
            if [ $passed -lt 0 ]; then passed=0; fi
            TESTS_PASSED=$((TESTS_PASSED + passed))
            TESTS_FAILED=$((TESTS_FAILED + failed))
            TESTS_SKIPPED=$((TESTS_SKIPPED + skipped))
            if [ $exit_code -eq 0 ]; then
                print_success "unittest discovery passed"
            else
                print_error "unittest discovery failed"
            fi
        fi
    else
        print_skip "Tests directory not found"
    fi
}

main() {
    print_header "PyCompiler ARK - Test Suite"
    
    echo "Starting pytest execution..."
    echo ""
    
    # Run only pytest tests
    test_python_tests_dir
    
    # Print summary
    print_header "Test Summary"
    
    echo -e "${GREEN}Passed:  $TESTS_PASSED${NC}"
    echo -e "${RED}Failed:  $TESTS_FAILED${NC}"
    echo -e "${YELLOW}Skipped: $TESTS_SKIPPED${NC}"
    echo ""
    
    local total=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))
    echo "Total tests: $total"
    echo ""
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}✗ Some tests failed!${NC}"
        return 1
    fi
}

# Run main function
main
exit $?
