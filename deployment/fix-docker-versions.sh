#!/bin/bash

# ===============================================
# Docker Version Alignment Script
# ===============================================
#
# DESCRIPTION:
#   Aligns all Docker packages to pinned versions on existing servers.
#   Fixes version drift (e.g., docker-ce-rootless-extras auto-upgraded).
#
# USAGE:
#   bash fix-docker-versions.sh
#
# WHAT IT DOES:
#   1. Checks current Docker package versions
#   2. Downgrades/upgrades packages to match pinned versions
#   3. Holds all Docker packages to prevent future auto-upgrades
#   4. Verifies installation
#
# REQUIREMENTS:
#   - Root access
#   - Active internet connection
#   - Docker containers will be restarted
#
# AUTHOR: EchoMind Team
# VERSION: 1.0.0
# DATE: 2026-02-09
# ===============================================

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# ===============================================
# CONFIGURATION
# ===============================================

# Target versions (must match install-echomind-server.sh)
TARGET_DOCKER_CE="5:28.5.2-1~ubuntu.24.04~noble"
TARGET_DOCKER_CE_CLI="5:28.5.2-1~ubuntu.24.04~noble"
TARGET_DOCKER_CE_ROOTLESS="5:28.5.2-1~ubuntu.24.04~noble"
TARGET_CONTAINERD="2.2.1-1~ubuntu.24.04~noble"
TARGET_COMPOSE_PLUGIN="5.0.2-1~ubuntu.24.04~noble"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ===============================================
# LOGGING FUNCTIONS
# ===============================================

log_info() {
    echo -e "${BLUE}ℹ️  ${NC}$1"
}

log_success() {
    echo -e "${GREEN}✅ ${NC}$1"
}

log_warning() {
    echo -e "${YELLOW}⚠️  ${NC}$1"
}

log_error() {
    echo -e "${RED}❌ ${NC}$1"
}

log_step() {
    echo -e "${CYAN}🚀 ${NC}$1"
}

print_banner() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║     Docker Version Alignment Script                ║"
    echo "║     Version 1.0.0                                  ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ===============================================
# VALIDATION FUNCTIONS
# ===============================================

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log_error "This script must be run as root"
        log_info "Run with: sudo bash $0"
        exit 1
    fi
}

check_docker_installed() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
}

# ===============================================
# VERSION CHECK FUNCTIONS
# ===============================================

get_installed_version() {
    local package=$1
    dpkg -l | grep "^ii.*${package} " | awk '{print $3}' || echo "not-installed"
}

check_versions() {
    log_step "Checking current Docker package versions..."
    echo ""

    local needs_fix=0

    # Check each package
    CURRENT_DOCKER_CE=$(get_installed_version "docker-ce ")
    CURRENT_DOCKER_CE_CLI=$(get_installed_version "docker-ce-cli ")
    CURRENT_DOCKER_CE_ROOTLESS=$(get_installed_version "docker-ce-rootless-extras ")
    CURRENT_CONTAINERD=$(get_installed_version "containerd.io ")
    CURRENT_COMPOSE_PLUGIN=$(get_installed_version "docker-compose-plugin ")

    # Compare versions
    echo "Package                       Current                              Target"
    echo "─────────────────────────────────────────────────────────────────────────────────────"

    compare_version "docker-ce" "$CURRENT_DOCKER_CE" "$TARGET_DOCKER_CE"
    compare_version "docker-ce-cli" "$CURRENT_DOCKER_CE_CLI" "$TARGET_DOCKER_CE_CLI"
    compare_version "docker-ce-rootless-extras" "$CURRENT_DOCKER_CE_ROOTLESS" "$TARGET_DOCKER_CE_ROOTLESS"
    compare_version "containerd.io" "$CURRENT_CONTAINERD" "$TARGET_CONTAINERD"
    compare_version "docker-compose-plugin" "$CURRENT_COMPOSE_PLUGIN" "$TARGET_COMPOSE_PLUGIN"

    echo ""

    if [ $needs_fix -eq 0 ]; then
        log_success "All Docker packages are at correct versions"
        return 0
    else
        log_warning "$needs_fix package(s) need version alignment"
        return 1
    fi
}

compare_version() {
    local name=$1
    local current=$2
    local target=$3

    printf "%-30s %-36s %-36s" "$name" "$current" "$target"

    if [ "$current" = "$target" ]; then
        echo -e " ${GREEN}✓${NC}"
    else
        echo -e " ${RED}✗${NC}"
        ((needs_fix++))
    fi
}

# ===============================================
# DOCKER OPERATION FUNCTIONS
# ===============================================

stop_docker_containers() {
    log_step "Stopping Docker containers..."

    # Find all running containers
    local running=$(docker ps -q)

    if [ -n "$running" ]; then
        log_info "Stopping $(echo "$running" | wc -l) container(s)..."
        docker stop $running
        log_success "All containers stopped"
    else
        log_info "No running containers"
    fi
}

start_docker_containers() {
    log_step "Starting Docker containers..."

    # Find docker-compose directories
    local compose_dirs=$(find /root -name "docker-compose.yml" -o -name "compose.yaml" 2>/dev/null | xargs -r dirname | sort -u)

    if [ -n "$compose_dirs" ]; then
        for dir in $compose_dirs; do
            log_info "Starting services in: $dir"
            cd "$dir"
            docker compose up -d 2>/dev/null || true
        done
        log_success "Docker services restarted"
    else
        log_info "No docker-compose files found"
    fi
}

# ===============================================
# PACKAGE MANAGEMENT FUNCTIONS
# ===============================================

unhold_packages() {
    log_step "Unholding Docker packages..."
    apt-mark unhold docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-compose-plugin 2>/dev/null || true
    log_success "Packages unheld"
}

hold_packages() {
    log_step "Holding Docker packages..."
    apt-mark hold docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-compose-plugin
    log_success "Packages held"
}

fix_versions() {
    log_step "Aligning Docker package versions..."
    echo ""

    # Unhold packages first
    unhold_packages

    # Update package lists
    log_info "Updating package lists..."
    apt-get update

    # Install specific versions
    log_info "Installing target versions..."
    apt-get install -y --allow-downgrades \
        docker-ce="${TARGET_DOCKER_CE}" \
        docker-ce-cli="${TARGET_DOCKER_CE_CLI}" \
        docker-ce-rootless-extras="${TARGET_DOCKER_CE_ROOTLESS}" \
        containerd.io="${TARGET_CONTAINERD}" \
        docker-compose-plugin="${TARGET_COMPOSE_PLUGIN}"

    log_success "All packages aligned to target versions"

    # Hold packages
    hold_packages
}

verify_holds() {
    log_step "Verifying package holds..."

    local held_packages=$(apt-mark showhold)
    local missing_holds=0

    for pkg in docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-compose-plugin; do
        if echo "$held_packages" | grep -q "^${pkg}$"; then
            log_success "$pkg is held"
        else
            log_error "$pkg is NOT held"
            ((missing_holds++))
        fi
    done

    if [ $missing_holds -gt 0 ]; then
        log_error "$missing_holds package(s) are not held"
        exit 1
    fi

    log_success "All Docker packages are held"
}

# ===============================================
# MAIN EXECUTION
# ===============================================

main() {
    print_banner

    log_info "Docker Version Alignment Script"
    log_info "Target versions:"
    echo "  docker-ce:                  $TARGET_DOCKER_CE"
    echo "  docker-ce-cli:              $TARGET_DOCKER_CE_CLI"
    echo "  docker-ce-rootless-extras:  $TARGET_DOCKER_CE_ROOTLESS"
    echo "  containerd.io:              $TARGET_CONTAINERD"
    echo "  docker-compose-plugin:      $TARGET_COMPOSE_PLUGIN"
    echo ""

    # Pre-flight checks
    check_root
    check_docker_installed

    # Check current versions
    if check_versions; then
        log_success "No action needed - all versions are correct"
        verify_holds
        exit 0
    fi

    # Ask for confirmation
    echo ""
    log_warning "This will:"
    echo "  1. Stop all running Docker containers"
    echo "  2. Downgrade/upgrade Docker packages"
    echo "  3. Restart Docker containers"
    echo ""
    read -p "Proceed? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Cancelled by user"
        exit 0
    fi

    echo ""

    # Stop containers
    stop_docker_containers

    # Fix versions
    fix_versions

    # Verify
    check_versions || {
        log_error "Version verification failed after fix"
        exit 1
    }

    verify_holds

    # Restart containers
    start_docker_containers

    echo ""
    log_success "Docker version alignment complete!"
    echo ""
    log_info "Verify services are running:"
    echo "  docker ps"
    echo "  cd /root/echo-mind/deployment/docker-cluster && ./cluster.sh -H status"
}

# Run main function
main "$@"
