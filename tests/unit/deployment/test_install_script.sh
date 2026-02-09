#!/bin/bash

# ===============================================
# Install Script Unit Tests
# ===============================================
#
# DESCRIPTION:
#   Unit tests for install-echomind-server.sh
#   Validates Docker version pinning logic
#
# USAGE:
#   bash tests/unit/deployment/test_install_script.sh
#
# REQUIREMENTS:
#   - bash 4.0+
#   - shellcheck (optional, for linting)
#
# AUTHOR: EchoMind Team
# VERSION: 1.0.0
# DATE: 2026-02-09
# ===============================================

set -e
set -u
set -o pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# ===============================================
# TEST FRAMEWORK
# ===============================================

log_test() {
    echo -e "${CYAN}TEST:${NC} $1"
}

log_pass() {
    echo -e "${GREEN}✓ PASS:${NC} $1"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}✗ FAIL:${NC} $1"
    ((TESTS_FAILED++))
}

assert_equals() {
    ((TESTS_RUN++))
    local expected=$1
    local actual=$2
    local message=$3

    if [ "$expected" = "$actual" ]; then
        log_pass "$message"
    else
        log_fail "$message (expected: '$expected', got: '$actual')"
    fi
}

assert_contains() {
    ((TESTS_RUN++))
    local haystack=$1
    local needle=$2
    local message=$3

    if echo "$haystack" | grep -q "$needle"; then
        log_pass "$message"
    else
        log_fail "$message (haystack does not contain: '$needle')"
    fi
}

assert_not_empty() {
    ((TESTS_RUN++))
    local value=$1
    local message=$2

    if [ -n "$value" ]; then
        log_pass "$message"
    else
        log_fail "$message (value is empty)"
    fi
}

print_summary() {
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "Test Results:"
    echo "  Total:  $TESTS_RUN"
    echo -e "  ${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "  ${RED}Failed: $TESTS_FAILED${NC}"
    echo "═══════════════════════════════════════════════════════"

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        exit 1
    fi
}

# ===============================================
# TEST SETUP
# ===============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
INSTALL_SCRIPT="$PROJECT_ROOT/deployment/install-echomind-server.sh"
CONFIG_TEMPLATE="$PROJECT_ROOT/deployment/echomind-install.conf.template"

echo "═══════════════════════════════════════════════════════"
echo "Install Script Unit Tests"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Project Root:    $PROJECT_ROOT"
echo "Install Script:  $INSTALL_SCRIPT"
echo "Config Template: $CONFIG_TEMPLATE"
echo ""

# ===============================================
# FILE EXISTENCE TESTS
# ===============================================

log_test "Install script exists"
if [ -f "$INSTALL_SCRIPT" ]; then
    ((TESTS_RUN++))
    log_pass "Install script found"
else
    ((TESTS_RUN++))
    log_fail "Install script not found at: $INSTALL_SCRIPT"
    exit 1
fi

log_test "Config template exists"
if [ -f "$CONFIG_TEMPLATE" ]; then
    ((TESTS_RUN++))
    log_pass "Config template found"
else
    ((TESTS_RUN++))
    log_fail "Config template not found at: $CONFIG_TEMPLATE"
    exit 1
fi

# ===============================================
# VERSION VARIABLE TESTS
# ===============================================

log_test "Install script has DOCKER_VERSION variable"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'DOCKER_VERSION="${DOCKER_VERSION:-' \
    "DOCKER_VERSION variable exists"

log_test "Install script has DOCKER_CE_ROOTLESS_VERSION variable"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'DOCKER_CE_ROOTLESS_VERSION="${DOCKER_CE_ROOTLESS_VERSION:-' \
    "DOCKER_CE_ROOTLESS_VERSION variable exists"

log_test "Install script has CONTAINERD_VERSION variable"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'CONTAINERD_VERSION="${CONTAINERD_VERSION:-' \
    "CONTAINERD_VERSION variable exists"

log_test "Install script has DOCKER_COMPOSE_PLUGIN_VERSION variable"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'DOCKER_COMPOSE_PLUGIN_VERSION="${DOCKER_COMPOSE_PLUGIN_VERSION:-' \
    "DOCKER_COMPOSE_PLUGIN_VERSION variable exists"

# ===============================================
# INSTALL COMMAND TESTS
# ===============================================

log_test "Install script pins docker-ce version"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'docker-ce="${DOCKER_VERSION}"' \
    "docker-ce is installed with pinned version"

log_test "Install script pins docker-ce-cli version"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'docker-ce-cli="${DOCKER_VERSION}"' \
    "docker-ce-cli is installed with pinned version"

log_test "Install script pins docker-ce-rootless-extras version"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'docker-ce-rootless-extras="${DOCKER_CE_ROOTLESS_VERSION}"' \
    "docker-ce-rootless-extras is installed with pinned version"

log_test "Install script pins containerd.io version"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'containerd.io="${CONTAINERD_VERSION}"' \
    "containerd.io is installed with pinned version"

log_test "Install script pins docker-compose-plugin version"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'docker-compose-plugin="${DOCKER_COMPOSE_PLUGIN_VERSION}"' \
    "docker-compose-plugin is installed with pinned version"

# ===============================================
# HOLD COMMAND TESTS
# ===============================================

log_test "Install script holds all Docker packages"
HOLD_LINE=$(grep "apt-mark hold" "$INSTALL_SCRIPT" | grep docker-ce | head -1)
assert_not_empty "$HOLD_LINE" "apt-mark hold command exists"

log_test "Install script holds docker-ce"
assert_contains "$HOLD_LINE" "docker-ce" "docker-ce is held"

log_test "Install script holds docker-ce-cli"
assert_contains "$HOLD_LINE" "docker-ce-cli" "docker-ce-cli is held"

log_test "Install script holds docker-ce-rootless-extras"
assert_contains "$HOLD_LINE" "docker-ce-rootless-extras" "docker-ce-rootless-extras is held"

log_test "Install script holds containerd.io"
assert_contains "$HOLD_LINE" "containerd.io" "containerd.io is held"

log_test "Install script holds docker-compose-plugin"
assert_contains "$HOLD_LINE" "docker-compose-plugin" "docker-compose-plugin is held"

# ===============================================
# VERIFICATION FUNCTION TESTS
# ===============================================

log_test "Install script has verify_docker_versions function"
assert_contains "$(cat "$INSTALL_SCRIPT")" "verify_docker_versions()" \
    "verify_docker_versions function exists"

log_test "verify_docker_versions checks docker-ce version"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'if \[ "$installed_docker_ce" != "$DOCKER_VERSION" \]' \
    "verify_docker_versions checks docker-ce version"

log_test "verify_docker_versions checks docker-ce-rootless-extras version"
assert_contains "$(cat "$INSTALL_SCRIPT")" 'if \[ "$installed_rootless" != "$DOCKER_CE_ROOTLESS_VERSION" \]' \
    "verify_docker_versions checks docker-ce-rootless-extras version"

log_test "verify_docker_versions checks package holds"
assert_contains "$(cat "$INSTALL_SCRIPT")" "apt-mark showhold" \
    "verify_docker_versions checks package holds"

log_test "verify_docker_versions is called in main()"
assert_contains "$(cat "$INSTALL_SCRIPT")" "verify_docker_versions" \
    "verify_docker_versions is called"

# ===============================================
# CONFIG TEMPLATE TESTS
# ===============================================

log_test "Config template has DOCKER_VERSION"
assert_contains "$(cat "$CONFIG_TEMPLATE")" 'DOCKER_VERSION=' \
    "Config template has DOCKER_VERSION"

log_test "Config template has DOCKER_CE_ROOTLESS_VERSION"
assert_contains "$(cat "$CONFIG_TEMPLATE")" 'DOCKER_CE_ROOTLESS_VERSION=' \
    "Config template has DOCKER_CE_ROOTLESS_VERSION"

log_test "Config template has CONTAINERD_VERSION"
assert_contains "$(cat "$CONFIG_TEMPLATE")" 'CONTAINERD_VERSION=' \
    "Config template has CONTAINERD_VERSION"

log_test "Config template has DOCKER_COMPOSE_PLUGIN_VERSION"
assert_contains "$(cat "$CONFIG_TEMPLATE")" 'DOCKER_COMPOSE_PLUGIN_VERSION=' \
    "Config template has DOCKER_COMPOSE_PLUGIN_VERSION"

# ===============================================
# VERSION CONSISTENCY TESTS
# ===============================================

log_test "All docker-ce* packages use same version in config template"
TEMPLATE_DOCKER_VERSION=$(grep "^DOCKER_VERSION=" "$CONFIG_TEMPLATE" | cut -d'"' -f2)
TEMPLATE_ROOTLESS_VERSION=$(grep "^DOCKER_CE_ROOTLESS_VERSION=" "$CONFIG_TEMPLATE" | cut -d'"' -f2)

assert_not_empty "$TEMPLATE_DOCKER_VERSION" "DOCKER_VERSION is set in template"
assert_not_empty "$TEMPLATE_ROOTLESS_VERSION" "DOCKER_CE_ROOTLESS_VERSION is set in template"

assert_equals "$TEMPLATE_DOCKER_VERSION" "$TEMPLATE_ROOTLESS_VERSION" \
    "docker-ce and docker-ce-rootless-extras versions match"

# ===============================================
# SHELLCHECK LINTING (Optional)
# ===============================================

if command -v shellcheck &> /dev/null; then
    log_test "Shellcheck linting on install script"
    if shellcheck -x "$INSTALL_SCRIPT" 2>/dev/null; then
        ((TESTS_RUN++))
        log_pass "Install script passes shellcheck"
    else
        ((TESTS_RUN++))
        log_fail "Install script has shellcheck warnings"
    fi

    log_test "Shellcheck linting on fix-docker-versions script"
    FIX_SCRIPT="$PROJECT_ROOT/deployment/fix-docker-versions.sh"
    if [ -f "$FIX_SCRIPT" ]; then
        if shellcheck -x "$FIX_SCRIPT" 2>/dev/null; then
            ((TESTS_RUN++))
            log_pass "fix-docker-versions.sh passes shellcheck"
        else
            ((TESTS_RUN++))
            log_fail "fix-docker-versions.sh has shellcheck warnings"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  shellcheck not installed, skipping linting tests${NC}"
fi

# ===============================================
# SUMMARY
# ===============================================

print_summary
