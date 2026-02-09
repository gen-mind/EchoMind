#!/bin/bash

# ===============================================
# EchoMind Server Automated Installation Script
# ===============================================
#
# DESCRIPTION:
#   Fully automated, idempotent installation script for EchoMind
#   on Hetzner dedicated servers running Ubuntu 24.04.
#
# FEATURES:
#   - Idempotent: Safe to re-run multiple times
#   - Auto-generation: Creates missing secrets automatically
#   - Full automation: Answers all interactive prompts
#   - Validation: Checks prerequisites and configuration
#
# USAGE:
#   1. Copy configuration template:
#      cp echomind-install.conf.template echomind-install.conf
#
#   2. Edit configuration file:
#      nano echomind-install.conf
#      Fill in: DOMAIN, SERVER_IP, ACME_EMAIL, passwords
#
#   3. Run installation:
#      bash install-echomind-server.sh
#
# REQUIREMENTS:
#   - Hetzner dedicated server
#   - Ubuntu 24.04 (installed via installimage or pre-installed)
#   - Root access
#   - Internet connectivity
#
# AUTHOR: EchoMind Team
# VERSION: 1.0.0
# ===============================================

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# ===============================================
# CONFIGURATION
# ===============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/echomind-install.conf"
LOG_FILE="${SCRIPT_DIR}/install-$(date +%Y%m%d-%H%M%S).log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ===============================================
# LOGGING FUNCTIONS
# ===============================================

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log_info() {
    log "${BLUE}ℹ️  ${NC}$1"
}

log_success() {
    log "${GREEN}✅ ${NC}$1"
}

log_warning() {
    log "${YELLOW}⚠️  ${NC}$1"
}

log_error() {
    log "${RED}❌ ${NC}$1"
}

log_step() {
    log "${CYAN}🚀 ${NC}$1"
}

log_skip() {
    log "${MAGENTA}⏭️  ${NC}$1"
}

print_banner() {
    log "${CYAN}"
    log "╔════════════════════════════════════════════════════╗"
    log "║     EchoMind Automated Server Installation         ║"
    log "║     Version 1.0.0                                  ║"
    log "╚════════════════════════════════════════════════════╝"
    log "${NC}"
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

load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        log_info "Create it from template:"
        log_info "  cp echomind-install.conf.template echomind-install.conf"
        log_info "  nano echomind-install.conf"
        exit 1
    fi

    log_step "Loading configuration from: $CONFIG_FILE"

    # Source config file
    set +u  # Allow undefined variables during source
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
    set -u

    log_success "Configuration loaded"
}

validate_config() {
    log_step "Validating configuration..."

    local errors=0

    # Required fields
    if [ -z "${DOMAIN:-}" ]; then
        log_error "DOMAIN is required in config file"
        ((errors++))
    fi

    if [ -z "${SERVER_IP:-}" ]; then
        log_error "SERVER_IP is required in config file"
        ((errors++))
    fi

    if [ -z "${ACME_EMAIL:-}" ]; then
        log_error "ACME_EMAIL is required in config file"
        ((errors++))
    fi

    if [ -z "${POSTGRES_PASSWORD:-}" ]; then
        log_error "POSTGRES_PASSWORD is required in config file"
        ((errors++))
    fi

    if [ -z "${AUTHENTIK_SECRET_KEY:-}" ]; then
        log_warning "AUTHENTIK_SECRET_KEY not set - will auto-generate"
        AUTHENTIK_SECRET_KEY="$(openssl rand -hex 32)"
        log_success "Generated: AUTHENTIK_SECRET_KEY"
    fi

    if [ -z "${AUTHENTIK_BOOTSTRAP_PASSWORD:-}" ]; then
        log_error "AUTHENTIK_BOOTSTRAP_PASSWORD is required in config file"
        ((errors++))
    fi

    if [ -z "${MINIO_ROOT_PASSWORD:-}" ]; then
        log_error "MINIO_ROOT_PASSWORD is required in config file"
        ((errors++))
    fi

    # Auto-generate Langfuse secrets if enabled
    if [ "${ENABLE_LANGFUSE:-true}" = "true" ]; then
        if [ -z "${LANGFUSE_NEXTAUTH_SECRET:-}" ]; then
            LANGFUSE_NEXTAUTH_SECRET="$(openssl rand -hex 32)"
            log_success "Generated: LANGFUSE_NEXTAUTH_SECRET"
        fi

        if [ -z "${LANGFUSE_SALT:-}" ]; then
            LANGFUSE_SALT="$(openssl rand -hex 32)"
            log_success "Generated: LANGFUSE_SALT"
        fi

        if [ -z "${LANGFUSE_ENCRYPTION_KEY:-}" ]; then
            LANGFUSE_ENCRYPTION_KEY="$(openssl rand -hex 32)"
            log_success "Generated: LANGFUSE_ENCRYPTION_KEY"
        fi

        if [ -z "${LANGFUSE_CLICKHOUSE_PASSWORD:-}" ]; then
            LANGFUSE_CLICKHOUSE_PASSWORD="$(openssl rand -hex 16)"
            log_success "Generated: LANGFUSE_CLICKHOUSE_PASSWORD"
        fi

        if [ -z "${LANGFUSE_PUBLIC_KEY:-}" ]; then
            LANGFUSE_PUBLIC_KEY="pk-echomind-$(openssl rand -hex 8)"
            log_success "Generated: LANGFUSE_PUBLIC_KEY"
        fi

        if [ -z "${LANGFUSE_SECRET_KEY:-}" ]; then
            LANGFUSE_SECRET_KEY="sk-echomind-$(openssl rand -hex 16)"
            log_success "Generated: LANGFUSE_SECRET_KEY"
        fi

        if [ -z "${LANGFUSE_INIT_PASSWORD:-}" ]; then
            LANGFUSE_INIT_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
            log_success "Generated: LANGFUSE_INIT_PASSWORD"
        fi

        if [ -z "${LANGFUSE_INIT_EMAIL:-}" ]; then
            LANGFUSE_INIT_EMAIL="${ACME_EMAIL}"
        fi
    fi

    # Observability
    if [ "${ENABLE_OBSERVABILITY:-false}" = "true" ] && [ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]; then
        log_error "GRAFANA_ADMIN_PASSWORD required when ENABLE_OBSERVABILITY=true"
        ((errors++))
    fi

    # Set defaults
    POSTGRES_USER="${POSTGRES_USER:-echomind}"
    POSTGRES_DB="${POSTGRES_DB:-postgres}"
    AUTHENTIK_BOOTSTRAP_EMAIL="${AUTHENTIK_BOOTSTRAP_EMAIL:-$ACME_EMAIL}"
    MINIO_ROOT_USER="${MINIO_ROOT_USER:-echomindadmin}"
    TZ="${TZ:-Europe/Zurich}"
    SKIP_INSTALLIMAGE="${SKIP_INSTALLIMAGE:-false}"
    SKIP_DOCKER_INSTALL="${SKIP_DOCKER_INSTALL:-false}"
    INSTALL_DIR="${INSTALL_DIR:-/root}"
    ECHOMIND_REPO="${ECHOMIND_REPO:-https://github.com/gen-mind/EchoMind.git}"
    ECHOMIND_WEBUI_REPO="${ECHOMIND_WEBUI_REPO:-https://github.com/gen-mind/echomind-webui.git}"
    ECHOMIND_BRANCH="${ECHOMIND_BRANCH:-main}"
    ECHOMIND_WEBUI_BRANCH="${ECHOMIND_WEBUI_BRANCH:-main}"
    # Docker version pinning (all components must match for stability)
    # Pinned to prevent auto-upgrades that may break IDE integrations (PyCharm, VSCode)
    DOCKER_VERSION="${DOCKER_VERSION:-5:28.5.2-1~ubuntu.24.04~noble}"
    DOCKER_CE_ROOTLESS_VERSION="${DOCKER_CE_ROOTLESS_VERSION:-5:28.5.2-1~ubuntu.24.04~noble}"
    CONTAINERD_VERSION="${CONTAINERD_VERSION:-2.2.1-1~ubuntu.24.04~noble}"
    DOCKER_COMPOSE_PLUGIN_VERSION="${DOCKER_COMPOSE_PLUGIN_VERSION:-5.0.2-1~ubuntu.24.04~noble}"
    ECHOMIND_VERSION="${ECHOMIND_VERSION:-0.1.0-beta.5}"

    if [ $errors -gt 0 ]; then
        log_error "Configuration validation failed with $errors error(s)"
        exit 1
    fi

    log_success "Configuration validated"
}

# ===============================================
# SYSTEM SETUP FUNCTIONS
# ===============================================

install_base_packages() {
    log_step "Installing base packages..."

    # Check if already installed
    if command -v fail2ban-client &> /dev/null && \
       command -v git &> /dev/null && \
       command -v curl &> /dev/null; then
        log_skip "Base packages already installed"
        return 0
    fi

    apt update
    apt install -y \
        fail2ban \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        htop \
        ufw

    log_success "Base packages installed"
}

configure_fail2ban() {
    log_step "Configuring fail2ban..."

    if systemctl is-enabled fail2ban &> /dev/null; then
        log_skip "fail2ban already configured"
        return 0
    fi

    systemctl enable --now fail2ban
    systemctl restart fail2ban

    log_success "fail2ban configured and running"
}

configure_firewall() {
    log_step "Configuring UFW firewall..."

    # Check if already configured
    if ufw status | grep -q "Status: active"; then
        log_skip "UFW already active"
        return 0
    fi

    # Allow SSH first (critical!)
    ufw allow OpenSSH
    ufw allow 22/tcp

    # Allow HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp

    # Set defaults
    ufw default deny incoming
    ufw default allow outgoing

    # Enable (non-interactive)
    echo "y" | ufw enable

    log_success "UFW firewall configured"
    ufw status verbose | tee -a "$LOG_FILE"
}

install_docker() {
    log_step "Installing Docker..."

    if command -v docker &> /dev/null; then
        CURRENT_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
        log_skip "Docker already installed: $CURRENT_VERSION"
        return 0
    fi

    # Remove conflicting packages
    for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
        apt-get remove -y "$pkg" 2>/dev/null || true
    done

    # Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
            gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
    fi

    # Add Docker repository
    if [ ! -f /etc/apt/sources.list.d/docker.list ]; then
        echo \
            "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
            $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" | \
            tee /etc/apt/sources.list.d/docker.list > /dev/null
    fi

    # Update and install Docker (pinned versions to prevent auto-upgrades)
    apt-get update
    apt-get install -y \
        docker-ce="${DOCKER_VERSION}" \
        docker-ce-cli="${DOCKER_VERSION}" \
        docker-ce-rootless-extras="${DOCKER_CE_ROOTLESS_VERSION}" \
        containerd.io="${CONTAINERD_VERSION}" \
        docker-compose-plugin="${DOCKER_COMPOSE_PLUGIN_VERSION}"

    # Hold ALL Docker packages to prevent auto-upgrade
    apt-mark hold docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-compose-plugin

    # Add root to docker group
    usermod -aG docker root || true

    # Verify installation
    docker --version
    docker compose version

    log_success "Docker installed: $(docker --version | cut -d' ' -f3 | tr -d ',')"
}

test_docker() {
    log_step "Testing Docker installation..."

    if docker run --rm hello-world &> /dev/null; then
        log_success "Docker is working correctly"
        docker rmi hello-world &> /dev/null || true
    else
        log_error "Docker test failed"
        exit 1
    fi
}

verify_docker_versions() {
    log_step "Verifying Docker package versions and holds..."

    local errors=0

    # Check installed versions
    local installed_docker_ce=$(dpkg -l | grep "^ii.*docker-ce " | awk '{print $3}')
    local installed_docker_ce_cli=$(dpkg -l | grep "^ii.*docker-ce-cli " | awk '{print $3}')
    local installed_rootless=$(dpkg -l | grep "^ii.*docker-ce-rootless-extras " | awk '{print $3}')
    local installed_containerd=$(dpkg -l | grep "^ii.*containerd.io " | awk '{print $3}')
    local installed_compose=$(dpkg -l | grep "^ii.*docker-compose-plugin " | awk '{print $3}')

    # Verify versions match
    if [ "$installed_docker_ce" != "$DOCKER_VERSION" ]; then
        log_error "docker-ce version mismatch: expected $DOCKER_VERSION, got $installed_docker_ce"
        ((errors++))
    fi

    if [ "$installed_docker_ce_cli" != "$DOCKER_VERSION" ]; then
        log_error "docker-ce-cli version mismatch: expected $DOCKER_VERSION, got $installed_docker_ce_cli"
        ((errors++))
    fi

    if [ "$installed_rootless" != "$DOCKER_CE_ROOTLESS_VERSION" ]; then
        log_error "docker-ce-rootless-extras version mismatch: expected $DOCKER_CE_ROOTLESS_VERSION, got $installed_rootless"
        ((errors++))
    fi

    if [ "$installed_containerd" != "$CONTAINERD_VERSION" ]; then
        log_error "containerd.io version mismatch: expected $CONTAINERD_VERSION, got $installed_containerd"
        ((errors++))
    fi

    if [ "$installed_compose" != "$DOCKER_COMPOSE_PLUGIN_VERSION" ]; then
        log_error "docker-compose-plugin version mismatch: expected $DOCKER_COMPOSE_PLUGIN_VERSION, got $installed_compose"
        ((errors++))
    fi

    # Verify packages are held
    local held_packages=$(apt-mark showhold)
    for pkg in docker-ce docker-ce-cli docker-ce-rootless-extras containerd.io docker-compose-plugin; do
        if ! echo "$held_packages" | grep -q "^${pkg}$"; then
            log_error "Package $pkg is not held"
            ((errors++))
        fi
    done

    if [ $errors -gt 0 ]; then
        log_error "Docker version verification failed with $errors error(s)"
        exit 1
    fi

    log_success "All Docker packages verified:"
    log "  docker-ce:                  $installed_docker_ce (held)"
    log "  docker-ce-cli:              $installed_docker_ce_cli (held)"
    log "  docker-ce-rootless-extras:  $installed_rootless (held)"
    log "  containerd.io:              $installed_containerd (held)"
    log "  docker-compose-plugin:      $installed_compose (held)"
}

# ===============================================
# REPOSITORY SETUP FUNCTIONS
# ===============================================

clone_repositories() {
    log_step "Cloning repositories..."

    cd "$INSTALL_DIR"

    # Clone EchoMind backend
    if [ -d "echo-mind/.git" ]; then
        log_skip "echo-mind repository already exists"
        cd echo-mind
        git fetch origin
        git checkout "$ECHOMIND_BRANCH"
        git pull origin "$ECHOMIND_BRANCH"
        cd "$INSTALL_DIR"
    else
        if [ -d "echo-mind" ]; then
            log_warning "Removing incomplete echo-mind directory"
            rm -rf echo-mind
        fi
        git clone "$ECHOMIND_REPO" echo-mind
        cd echo-mind
        git checkout "$ECHOMIND_BRANCH"
        cd "$INSTALL_DIR"
        log_success "Cloned echo-mind repository"
    fi

    # Clone EchoMind WebUI
    if [ -d "echo-mind-webui/.git" ]; then
        log_skip "echo-mind-webui repository already exists"
        cd echo-mind-webui
        git fetch origin
        git checkout "$ECHOMIND_WEBUI_BRANCH"
        git pull origin "$ECHOMIND_WEBUI_BRANCH"
        cd "$INSTALL_DIR"
    else
        if [ -d "echo-mind-webui" ]; then
            log_warning "Removing incomplete echo-mind-webui directory"
            rm -rf echo-mind-webui
        fi
        git clone "$ECHOMIND_WEBUI_REPO" echo-mind-webui
        cd echo-mind-webui
        git checkout "$ECHOMIND_WEBUI_BRANCH"
        cd "$INSTALL_DIR"
        log_success "Cloned echo-mind-webui repository"
    fi
}

# ===============================================
# CONFIGURATION GENERATION FUNCTIONS
# ===============================================

generate_env_host() {
    log_step "Generating .env.host configuration..."

    local env_file="${INSTALL_DIR}/echo-mind/deployment/docker-cluster/.env.host"

    # Backup existing file
    if [ -f "$env_file" ]; then
        log_warning "Backing up existing .env.host"
        cp "$env_file" "${env_file}.backup.$(date +%Y%m%d-%H%M%S)"
    fi

    # Generate new .env.host
    cat > "$env_file" <<EOF
# ===============================================
# EchoMind Docker Cluster Configuration
# Production deployment
# Generated by install-echomind-server.sh
# Date: $(date)
# ===============================================

# ===============================================
# HuggingFace Access Token (for Docker build)
# ===============================================
HF_TOKEN=${HF_TOKEN:-}

# ===============================================
# Versioning
# ===============================================
ECHOMIND_VERSION=${ECHOMIND_VERSION}
API_VERSION=\${ECHOMIND_VERSION}
MIGRATION_VERSION=\${ECHOMIND_VERSION}
EMBEDDER_VERSION=\${ECHOMIND_VERSION}
ORCHESTRATOR_VERSION=\${ECHOMIND_VERSION}
CONNECTOR_VERSION=\${ECHOMIND_VERSION}
INGESTOR_VERSION=\${ECHOMIND_VERSION}
GUARDIAN_VERSION=\${ECHOMIND_VERSION}
PROJECTOR_VERSION=\${ECHOMIND_VERSION}
WEBUI_VERSION=\${ECHOMIND_VERSION}

# ===============================================
# Paths
# ===============================================
CONFIG_PATH=../../config
DATA_PATH=../../data

# ===============================================
# Domain Configuration
# ===============================================
DOMAIN=${DOMAIN}
AUTHENTIK_DOMAIN=auth.\${DOMAIN}
API_DOMAIN=api.\${DOMAIN}
QDRANT_DOMAIN=qdrant.\${DOMAIN}
MINIO_DOMAIN=minio.\${DOMAIN}
S3_DOMAIN=s3.\${DOMAIN}
PORTAINER_DOMAIN=portainer.\${DOMAIN}
POSTGRES_DOMAIN=db.\${DOMAIN}
NATS_DOMAIN=nats.\${DOMAIN}
GRAFANA_DOMAIN=grafana.\${DOMAIN}
PROMETHEUS_DOMAIN=prometheus.\${DOMAIN}
TENSORBOARD_DOMAIN=tensorboard.\${DOMAIN}
LANGFUSE_DOMAIN=langfuse.\${DOMAIN}

# ===============================================
# URL Configuration
# ===============================================
PROTOCOL=https
WEB_URL=\${PROTOCOL}://\${DOMAIN}
API_URL=\${PROTOCOL}://\${API_DOMAIN}
AUTHENTIK_URL=\${PROTOCOL}://\${AUTHENTIK_DOMAIN}
WS_URL=wss://\${API_DOMAIN}/api/v1/ws/chat
CORS_ORIGINS=\${PROTOCOL}://\${DOMAIN},\${PROTOCOL}://\${API_DOMAIN}

# ===============================================
# Timezone
# ===============================================
TZ=${TZ}

# ===============================================
# SSL Configuration
# ===============================================
ACME_EMAIL=${ACME_EMAIL}

# ===============================================
# PostgreSQL Configuration
# ===============================================
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
AUTHENTIK_DB_NAME=authentik
API_DB_NAME=echomind

# ===============================================
# Authentik Configuration
# ===============================================
AUTHENTIK_SECRET_KEY=${AUTHENTIK_SECRET_KEY}
AUTHENTIK_BOOTSTRAP_PASSWORD=${AUTHENTIK_BOOTSTRAP_PASSWORD}
AUTHENTIK_BOOTSTRAP_EMAIL=${AUTHENTIK_BOOTSTRAP_EMAIL}

# ===============================================
# MinIO Configuration
# ===============================================
MINIO_ROOT_USER=${MINIO_ROOT_USER}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}

# ===============================================
# WebUI Build
# ===============================================
BUILD_HASH=prod

# ===============================================
# OIDC Settings (Configure after Authentik setup)
# ===============================================
WEB_OIDC_AUTHORITY=\${AUTHENTIK_URL}/application/o/echomind-web/
WEB_OIDC_CLIENT_ID=PASTE_CLIENT_ID_FROM_AUTHENTIK
WEB_OIDC_CLIENT_SECRET=PASTE_CLIENT_SECRET_FROM_AUTHENTIK
WEB_OIDC_SCOPE="openid profile email"

# ===============================================
# API Authentication
# ===============================================
API_AUTH_ISSUER=\${WEB_OIDC_AUTHORITY}
API_AUTH_AUDIENCE=\${WEB_OIDC_CLIENT_ID}
API_AUTH_JWKS_URL=http://authentik-server:9000/application/o/echomind-web/jwks/

# ===============================================
# Observability
# ===============================================
ENABLE_OBSERVABILITY=${ENABLE_OBSERVABILITY}
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-changeme}
GRAFANA_OAUTH_ENABLED=false
GRAFANA_OAUTH_CLIENT_ID=
GRAFANA_OAUTH_CLIENT_SECRET=

# ===============================================
# Langfuse v3 (LLM Observability + RAG Eval)
# ===============================================
ENABLE_LANGFUSE=${ENABLE_LANGFUSE}
LANGFUSE_NEXTAUTH_SECRET=${LANGFUSE_NEXTAUTH_SECRET}
LANGFUSE_SALT=${LANGFUSE_SALT}
LANGFUSE_ENCRYPTION_KEY=${LANGFUSE_ENCRYPTION_KEY}
LANGFUSE_CLICKHOUSE_PASSWORD=${LANGFUSE_CLICKHOUSE_PASSWORD}
LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
LANGFUSE_INIT_EMAIL=${LANGFUSE_INIT_EMAIL}
LANGFUSE_INIT_PASSWORD=${LANGFUSE_INIT_PASSWORD}
LANGFUSE_OAUTH_ENABLED=false
LANGFUSE_OAUTH_CLIENT_ID=
LANGFUSE_OAUTH_CLIENT_SECRET=
RAGAS_SAMPLE_RATE=0.1
EOF

    log_success "Generated .env.host configuration"
}

setup_data_directories() {
    log_step "Creating data directories..."

    local data_dir="${INSTALL_DIR}/echo-mind/data"

    mkdir -p "$data_dir"/{postgres,qdrant,minio,nats,portainer,tensorboard}
    mkdir -p "$data_dir"/authentik/{media,custom-templates,certs}
    mkdir -p "$data_dir"/traefik/certificates

    if [ "${ENABLE_OBSERVABILITY:-false}" = "true" ]; then
        mkdir -p "$data_dir"/{prometheus,loki,grafana}
        # Set ownership for non-root containers
        chown -R 65534:65534 "$data_dir"/prometheus  # prometheus runs as nobody
        chown -R 10001:10001 "$data_dir"/loki        # loki runs as uid 10001
        chown -R 472:472 "$data_dir"/grafana         # grafana runs as uid 472
    fi

    if [ "${ENABLE_LANGFUSE:-true}" = "true" ]; then
        mkdir -p "$data_dir"/{clickhouse,clickhouse-logs}
    fi

    # Set permissions (world-writable for Docker volume mounts)
    chmod -R 777 "$data_dir"

    log_success "Data directories created"
}

# ===============================================
# DEPLOYMENT FUNCTIONS
# ===============================================

deploy_echomind() {
    log_step "Deploying EchoMind cluster..."

    cd "${INSTALL_DIR}/echo-mind/deployment/docker-cluster"

    # Ensure cluster.sh is executable
    chmod +x cluster.sh

    # Pull images first
    log_info "Pulling Docker images..."
    ./cluster.sh --host pull

    # Start cluster
    log_info "Starting EchoMind cluster..."
    ./cluster.sh --host start

    log_success "EchoMind cluster deployed"
}

# ===============================================
# POST-INSTALLATION FUNCTIONS
# ===============================================

print_summary() {
    log ""
    log "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    log "${GREEN}             EchoMind Installation Complete!${NC}"
    log "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    log ""

    log_info "Installation Summary:"
    log "  📦 Docker Version:     $(docker --version | cut -d' ' -f3 | tr -d ',')"
    log "  🌐 Domain:             ${DOMAIN}"
    log "  📧 ACME Email:         ${ACME_EMAIL}"
    log "  🔒 SSL:                Let's Encrypt (HTTPS)"
    log "  📊 Observability:      ${ENABLE_OBSERVABILITY}"
    log "  🔬 Langfuse:           ${ENABLE_LANGFUSE}"
    log ""

    log_info "Service URLs:"
    log "  🌐 Web App:            https://${DOMAIN}"
    log "  🔐 Authentik:          https://auth.${DOMAIN}"
    log "  🚀 API:                https://api.${DOMAIN}"
    log "  🔍 Qdrant:             https://qdrant.${DOMAIN}"
    log "  📦 MinIO Console:      https://minio.${DOMAIN}"
    log "  💾 S3 API:             https://s3.${DOMAIN}"
    log "  📡 NATS:               https://nats.${DOMAIN}"
    log "  🗄️  PostgreSQL:         https://db.${DOMAIN} (Adminer)"
    log "  🐳 Portainer:          https://portainer.${DOMAIN}"
    log "  🎨 TensorBoard:        https://tensorboard.${DOMAIN}"

    if [ "${ENABLE_OBSERVABILITY}" = "true" ]; then
        log "  📊 Grafana:            https://grafana.${DOMAIN}"
        log "  📈 Prometheus:         https://prometheus.${DOMAIN}"
    fi

    if [ "${ENABLE_LANGFUSE}" = "true" ]; then
        log "  🔬 Langfuse:           https://langfuse.${DOMAIN}"
    fi

    log ""
    log_info "API Documentation:"
    log "  📚 Swagger UI:         https://api.${DOMAIN}/api/v1/docs"
    log "  📖 ReDoc:              https://api.${DOMAIN}/api/v1/redoc"
    log ""

    log_info "SSH Tunnels (for local access):"
    log "  📊 Traefik:            ssh -L 8080:127.0.0.1:8080 root@${SERVER_IP}"
    log "  🐘 PostgreSQL:         ssh -L 5432:127.0.0.1:5432 root@${SERVER_IP}"
    log ""

    log_warning "NEXT STEPS (CRITICAL):"
    log ""
    log "  1️⃣  Configure DNS Records:"
    log "     📄 See: ${INSTALL_DIR}/echo-mind/excluded/todo-installation.md"
    log ""
    log "  2️⃣  Configure Authentik OIDC:"
    log "     - Login: https://auth.${DOMAIN}"
    log "     - Email: ${AUTHENTIK_BOOTSTRAP_EMAIL}"
    log "     - Password: ${AUTHENTIK_BOOTSTRAP_PASSWORD}"
    log "     - Create OAuth2 Provider for 'echomind-web'"
    log "     - Update .env.host with WEB_OIDC_CLIENT_ID and WEB_OIDC_CLIENT_SECRET"
    log "     - Restart: cd ${INSTALL_DIR}/echo-mind/deployment/docker-cluster && ./cluster.sh -H restart"
    log ""
    log "  3️⃣  Access Langfuse (if enabled):"
    log "     - URL: https://langfuse.${DOMAIN}"
    log "     - Email: ${LANGFUSE_INIT_EMAIL}"
    log "     - Password: ${LANGFUSE_INIT_PASSWORD}"
    log ""
    log "  4️⃣  Useful Commands:"
    log "     - View logs:      ./cluster.sh -H logs [service]"
    log "     - Check status:   ./cluster.sh -H status"
    log "     - Restart:        ./cluster.sh -H restart"
    log "     - Stop:           ./cluster.sh -H stop"
    log ""

    log_success "Installation log saved to: $LOG_FILE"
    log ""

    # Save credentials to secure file
    local creds_file="${INSTALL_DIR}/echo-mind/excluded/installation-credentials.txt"
    mkdir -p "${INSTALL_DIR}/echo-mind/excluded"
    cat > "$creds_file" <<EOF
# EchoMind Installation Credentials
# Generated: $(date)
# KEEP THIS FILE SECURE - Contains sensitive passwords

DOMAIN=${DOMAIN}
SERVER_IP=${SERVER_IP}

PostgreSQL:
  User: ${POSTGRES_USER}
  Password: ${POSTGRES_PASSWORD}
  Database: ${POSTGRES_DB}

Authentik:
  URL: https://auth.${DOMAIN}
  Email: ${AUTHENTIK_BOOTSTRAP_EMAIL}
  Password: ${AUTHENTIK_BOOTSTRAP_PASSWORD}
  Secret Key: ${AUTHENTIK_SECRET_KEY}

MinIO:
  Console: https://minio.${DOMAIN}
  User: ${MINIO_ROOT_USER}
  Password: ${MINIO_ROOT_PASSWORD}

EOF

    if [ "${ENABLE_LANGFUSE}" = "true" ]; then
        cat >> "$creds_file" <<EOF
Langfuse:
  URL: https://langfuse.${DOMAIN}
  Email: ${LANGFUSE_INIT_EMAIL}
  Password: ${LANGFUSE_INIT_PASSWORD}
  Public Key: ${LANGFUSE_PUBLIC_KEY}
  Secret Key: ${LANGFUSE_SECRET_KEY}

EOF
    fi

    if [ "${ENABLE_OBSERVABILITY}" = "true" ]; then
        cat >> "$creds_file" <<EOF
Grafana:
  URL: https://grafana.${DOMAIN}
  User: admin
  Password: ${GRAFANA_ADMIN_PASSWORD}

EOF
    fi

    chmod 600 "$creds_file"
    log_warning "Credentials saved to: $creds_file (mode 600)"
}

# ===============================================
# MAIN INSTALLATION FLOW
# ===============================================

main() {
    print_banner

    log_info "Starting EchoMind installation at $(date)"
    log_info "Log file: $LOG_FILE"
    log ""

    # Pre-flight checks
    check_root
    load_config
    validate_config

    log ""
    log_info "Installation Configuration:"
    log "  Domain:        ${DOMAIN}"
    log "  Server IP:     ${SERVER_IP}"
    log "  Email:         ${ACME_EMAIL}"
    log "  Install Dir:   ${INSTALL_DIR}"
    log "  Observability: ${ENABLE_OBSERVABILITY}"
    log "  Langfuse:      ${ENABLE_LANGFUSE}"
    log ""

    # Ask for confirmation
    read -p "Proceed with installation? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Installation cancelled by user"
        exit 0
    fi

    log ""

    # System setup
    if [ "${SKIP_INSTALLIMAGE}" = "false" ]; then
        log_warning "SKIP_INSTALLIMAGE=false - Please run 'installimage' manually and reboot"
        log_info "After reboot, set SKIP_INSTALLIMAGE=true in config and re-run this script"
        exit 0
    fi

    install_base_packages
    configure_fail2ban
    configure_firewall

    if [ "${SKIP_DOCKER_INSTALL}" = "false" ]; then
        install_docker
        test_docker
        verify_docker_versions
    else
        log_skip "Docker installation skipped (SKIP_DOCKER_INSTALL=true)"
    fi

    # Repository setup
    clone_repositories
    generate_env_host
    setup_data_directories

    # Deploy
    deploy_echomind

    # Summary
    print_summary

    log_success "Installation completed successfully!"
}

# Run main function
main "$@"
