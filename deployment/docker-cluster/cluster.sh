#!/bin/bash

# ======================================
# EchoMind Docker Cluster Manager
# ======================================
#
# USAGE:
#   ./cluster.sh <--local|--host> <command>
#
# MODE (required):
#   --local, -L    Use local mode (docker-compose.yml for development)
#   --host, -H     Use host mode (docker-compose-host.yml for production)
#
# CLUSTER MANAGEMENT:
#   start          - Start the entire cluster with all services
#   stop           - Stop all cluster services
#   restart        - Restart all cluster services
#   status         - Show status of all running services
#   logs           - Show live logs for all services (Ctrl+C to exit)
#   logs <service> - Show live logs for specific service (e.g., api, postgres, authentik-server)
#
# IMAGE MANAGEMENT:
#   pull           - Pull latest images from Docker registries
#   build          - Build all local services (uses cache, fast if no changes)
#   build <svc>    - Build a specific service (uses cache)
#   rebuild <svc>  - Force rebuild (no cache) and restart a service
#   build-release  - Build API Docker image for Docker Hub with proper tags
#   push           - Push built API image to Docker Hub (requires 'docker login')
#   release        - Build and push API image to Docker Hub in one command
#
# EXAMPLES:
#   ./cluster.sh --local start      # Start local cluster
#   ./cluster.sh -L start           # Start local cluster (short flag)
#   ./cluster.sh --host start       # Start production cluster (demo.echomind.ch)
#   ./cluster.sh -H logs api        # View API logs on host
#   ./cluster.sh -L build           # Build all local services
#   ./cluster.sh -H rebuild webui   # Rebuild webui on host
#
# REQUIREMENTS:
#   - Docker and Docker Compose installed
#   - .env file configured (copy from .env.example or .env.host)
#   - For push/release: docker login with username 'gsantopaolo'
#
# VERSIONING:
#   - Version is read from ECHOMIND_VERSION in .env file
#   - Current: 0.1.0-beta.2 (Semantic Versioning 2.0)
#   - Images tagged as: <version>, latest, beta
#
# ======================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Mode detection (--host/-H or --local/-L flag) - REQUIRED
MODE=""
COMPOSE_FILE=""
ENV_SOURCE=""
DOMAIN=""
COMPOSE_ENV_FLAG=""

# Parse mode flag (must be first argument)
if [ "${1:-}" = "--host" ] || [ "${1:-}" = "-H" ]; then
    MODE="host"
    COMPOSE_FILE="docker-compose-host.yml"
    ENV_SOURCE=".env.host"
    COMPOSE_ENV_FLAG="--env-file .env.host"
    DOMAIN="demo.echomind.ch"
    shift  # Remove the flag from arguments
elif [ "${1:-}" = "--local" ] || [ "${1:-}" = "-L" ]; then
    MODE="local"
    COMPOSE_FILE="docker-compose.yml"
    ENV_SOURCE=".env"
    COMPOSE_ENV_FLAG="--env-file .env"
    DOMAIN="localhost"
    shift  # Remove the flag from arguments
elif [ "${1:-}" = "help" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    # Allow help without mode flag
    MODE="local"
    COMPOSE_FILE="docker-compose.yml"
else
    echo -e "\033[0;31m❌ Error: Mode flag is required!\033[0m"
    echo ""
    echo "Usage: ./cluster.sh <--local|--host> <command>"
    echo ""
    echo "  --local, -L    Local development (docker-compose.yml)"
    echo "  --host, -H     Production host (docker-compose-host.yml)"
    echo ""
    echo "Examples:"
    echo "  ./cluster.sh --local start"
    echo "  ./cluster.sh -H rebuild web"
    echo ""
    echo "Run './cluster.sh help' for full usage information."
    exit 1
fi

# Source environment file and export all variables
# This ensures docker-compose can interpolate variables without warnings
cd "$SCRIPT_DIR"
if [ -f "$ENV_SOURCE" ]; then
    set -a  # Automatically export all variables
    source "$ENV_SOURCE"
    set +a  # Stop auto-exporting
fi

# Read ENABLE_OBSERVABILITY from .env (or .env.host for host mode)
OBSERVABILITY_PROFILE=""
OBSERVABILITY_FILES=""
_obs_enabled=false
if [ -f "$SCRIPT_DIR/.env" ] && grep -q "^[[:space:]]*ENABLE_OBSERVABILITY[[:space:]]*=[[:space:]]*true" "$SCRIPT_DIR/.env" 2>/dev/null; then
    _obs_enabled=true
elif [ "$MODE" = "host" ] && [ -f "$SCRIPT_DIR/.env.host" ] && grep -q "^[[:space:]]*ENABLE_OBSERVABILITY[[:space:]]*=[[:space:]]*true" "$SCRIPT_DIR/.env.host" 2>/dev/null; then
    _obs_enabled=true
fi
if [ "$_obs_enabled" = true ]; then
    OBSERVABILITY_PROFILE="--profile observability"
    OBSERVABILITY_FILES="-f docker-compose-observability.yml"
    if [ "$MODE" = "host" ]; then
        OBSERVABILITY_FILES="$OBSERVABILITY_FILES -f docker-compose-observability-host.yml"
    fi
fi

# Read ENABLE_LANGFUSE from .env (or .env.host for host mode)
LANGFUSE_PROFILE=""
LANGFUSE_FILES=""
_langfuse_enabled=false
if [ -f "$SCRIPT_DIR/.env" ] && grep -q "^[[:space:]]*ENABLE_LANGFUSE[[:space:]]*=[[:space:]]*true" "$SCRIPT_DIR/.env" 2>/dev/null; then
    _langfuse_enabled=true
elif [ "$MODE" = "host" ] && [ -f "$SCRIPT_DIR/.env.host" ] && grep -q "^[[:space:]]*ENABLE_LANGFUSE[[:space:]]*=[[:space:]]*true" "$SCRIPT_DIR/.env.host" 2>/dev/null; then
    _langfuse_enabled=true
fi
if [ "$_langfuse_enabled" = true ]; then
    LANGFUSE_PROFILE="--profile langfuse"
    LANGFUSE_FILES="-f docker-compose-langfuse.yml"
    if [ "$MODE" = "host" ]; then
        LANGFUSE_FILES="$LANGFUSE_FILES -f docker-compose-langfuse-host.yml"
    fi
fi

# Functions
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
    echo "╔════════════════════════════════════════╗"
    echo "║     EchoMind Docker Cluster Manager    ║"
    echo "╚════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_step "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    log_success "Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    log_success "Docker Compose: $(docker compose version --short)"
    
    # Check .env file
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        if [ "$MODE" = "host" ] && [ -f "$SCRIPT_DIR/.env.host" ]; then
            log_info "Copying .env.host to .env..."
            cp "$SCRIPT_DIR/.env.host" "$SCRIPT_DIR/.env"
            log_success ".env created from .env.host"
        else
            log_error ".env file not found"
            log_info "Copy .env.example to .env and configure it:"
            echo -e "  ${YELLOW}cp .env.example .env${NC}"
            echo -e "  ${YELLOW}nano .env${NC}"
            exit 1
        fi
    else
        log_success ".env file found"
    fi
}

create_directories() {
    log_step "Creating data directories..."

    mkdir -p "$PROJECT_ROOT/data/postgres"
    mkdir -p "$PROJECT_ROOT/data/qdrant"
    mkdir -p "$PROJECT_ROOT/data/minio"
    mkdir -p "$PROJECT_ROOT/data/nats"
    mkdir -p "$PROJECT_ROOT/data/tensorboard"
    mkdir -p "$PROJECT_ROOT/data/authentik/media"
    mkdir -p "$PROJECT_ROOT/data/authentik/custom-templates"
    mkdir -p "$PROJECT_ROOT/data/authentik/certs"
    mkdir -p "$PROJECT_ROOT/data/traefik/certificates"

    # Host mode includes portainer
    if [ "$MODE" = "host" ]; then
        mkdir -p "$PROJECT_ROOT/data/portainer"
    fi

    # Observability data directories (containers run as non-root users)
    if [ -n "$OBSERVABILITY_PROFILE" ]; then
        mkdir -p "$PROJECT_ROOT/data/prometheus"
        mkdir -p "$PROJECT_ROOT/data/loki"
        mkdir -p "$PROJECT_ROOT/data/grafana"
        chown -R 65534:65534 "$PROJECT_ROOT/data/prometheus"  # prometheus runs as nobody
        chown -R 10001:10001 "$PROJECT_ROOT/data/loki"        # loki runs as uid 10001
        chown -R 472:472 "$PROJECT_ROOT/data/grafana"         # grafana runs as uid 472
    fi

    # Langfuse data directories (ClickHouse)
    if [ -n "$LANGFUSE_PROFILE" ]; then
        mkdir -p "$PROJECT_ROOT/data/clickhouse"
        mkdir -p "$PROJECT_ROOT/data/clickhouse-logs"
    fi

    log_success "Data directories created"
}

start_cluster() {
    print_banner

    log_info "Mode: ${CYAN}${MODE}${NC} (${COMPOSE_FILE})"
    echo ""

    check_prerequisites
    create_directories

    log_step "Starting EchoMind cluster..."
    echo ""

    cd "$SCRIPT_DIR"
    # Use down + up to ensure env vars from .env are always applied
    # (--force-recreate alone doesn't always work)
    docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE down 2>/dev/null || true
    docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE up -d

    echo ""
    log_success "Cluster started successfully!"
    echo ""

    if [ "$MODE" = "host" ]; then
        # Host mode URLs (production)
        log_info "Application:"
        echo -e "  ${GREEN}🌐 Web App:${NC}       ${PROTOCOL}://${DOMAIN}"
        echo ""

        log_info "Core Services:"
        echo -e "  ${GREEN}🔐 Authentik:${NC}     ${PROTOCOL}://${AUTHENTIK_DOMAIN}"
        echo -e "  ${GREEN}🚀 API:${NC}           ${PROTOCOL}://${API_DOMAIN}"
        echo -e "  ${GREEN}🔍 Qdrant:${NC}        ${PROTOCOL}://${QDRANT_DOMAIN}"
        echo -e "  ${GREEN}📦 MinIO:${NC}         ${PROTOCOL}://${MINIO_DOMAIN}"
        echo -e "  ${GREEN}💾 S3 API:${NC}        ${PROTOCOL}://${S3_DOMAIN}"
        echo -e "  ${GREEN}📡 NATS:${NC}          ${PROTOCOL}://${NATS_DOMAIN}"
        echo -e "  ${GREEN}🗄️  PostgreSQL:${NC}   ${PROTOCOL}://${POSTGRES_DOMAIN}"
        echo -e "  ${GREEN}🐳 Portainer:${NC}     ${PROTOCOL}://${PORTAINER_DOMAIN}"
        echo -e "  ${GREEN}🎨 TensorBoard:${NC}   ${PROTOCOL}://${TENSORBOARD_DOMAIN}"
        echo ""

        if [ -n "$OBSERVABILITY_PROFILE" ]; then
            log_info "Observability Stack:"
            echo -e "  ${GREEN}📊 Grafana:${NC}       ${PROTOCOL}://${GRAFANA_DOMAIN}"
            echo -e "  ${GREEN}📈 Prometheus:${NC}    ${PROTOCOL}://${PROMETHEUS_DOMAIN}"
            echo ""
        fi

        if [ -n "$LANGFUSE_PROFILE" ]; then
            log_info "LLM Tracing:"
            echo -e "  ${GREEN}🔬 Langfuse:${NC}      ${PROTOCOL}://${LANGFUSE_DOMAIN}"
            echo ""
        fi

        log_info "API Endpoints:"
        echo -e "  ${CYAN}📚 Swagger UI:${NC}    ${PROTOCOL}://${API_DOMAIN}/api/v1/docs"
        echo -e "  ${CYAN}📖 ReDoc:${NC}         ${PROTOCOL}://${API_DOMAIN}/api/v1/redoc"
        echo -e "  ${CYAN}💚 Health:${NC}        ${PROTOCOL}://${API_DOMAIN}/health"
        echo ""

        log_info "Local access (via SSH tunnel):"
        echo -e "  ${CYAN}📊 Traefik:${NC}       ssh -L 8080:127.0.0.1:8080 root@SERVER_IP"
        echo -e "  ${CYAN}🐘 PostgreSQL:${NC}   ssh -L 5432:127.0.0.1:5432 root@SERVER_IP"
        echo ""

        log_info "Useful commands:"
        echo -e "  ${YELLOW}./cluster.sh -H logs${NC}      - View logs"
        echo -e "  ${YELLOW}./cluster.sh -H status${NC}    - Check status"
        echo -e "  ${YELLOW}./cluster.sh -H stop${NC}      - Stop cluster"
        echo ""
    else
        # Local mode URLs (development)
        log_info "Application:"
        echo -e "  ${GREEN}🌐 Web App:${NC}       ${PROTOCOL}://${DOMAIN}"
        echo ""

        log_info "Core Services:"
        echo -e "  ${GREEN}🔐 Authentik:${NC}     ${PROTOCOL}://${AUTHENTIK_DOMAIN}"
        echo -e "  ${GREEN}🚀 API:${NC}           ${PROTOCOL}://${API_DOMAIN}"
        echo -e "  ${GREEN}🔍 Qdrant:${NC}        ${PROTOCOL}://${QDRANT_DOMAIN}"
        echo -e "  ${GREEN}📦 MinIO:${NC}         ${PROTOCOL}://${MINIO_DOMAIN}"
        echo -e "  ${GREEN}💾 S3 API:${NC}        ${PROTOCOL}://${S3_DOMAIN}"
        echo -e "  ${GREEN}📡 NATS:${NC}          ${PROTOCOL}://${NATS_DOMAIN}"
        echo -e "  ${GREEN}🗄️  PostgreSQL:${NC}   ${PROTOCOL}://${POSTGRES_DOMAIN}"
        echo -e "  ${GREEN}🐳 Portainer:${NC}     ${PROTOCOL}://${PORTAINER_DOMAIN}"
        echo -e "  ${GREEN}🎨 TensorBoard:${NC}   ${PROTOCOL}://${TENSORBOARD_DOMAIN}"
        echo -e "  ${GREEN}📊 Traefik:${NC}       ${PROTOCOL}://${DOMAIN}:8080"
        echo ""

        if [ -n "$OBSERVABILITY_PROFILE" ]; then
            log_info "Observability Stack:"
            echo -e "  ${GREEN}📊 Grafana:${NC}       ${PROTOCOL}://${GRAFANA_DOMAIN}"
            echo -e "  ${GREEN}📈 Prometheus:${NC}    ${PROTOCOL}://${PROMETHEUS_DOMAIN}"
            echo ""
        fi

        if [ -n "$LANGFUSE_PROFILE" ]; then
            log_info "LLM Tracing:"
            echo -e "  ${GREEN}🔬 Langfuse:${NC}      ${PROTOCOL}://${LANGFUSE_DOMAIN}"
            echo ""
        fi

        log_info "API Endpoints:"
        echo -e "  ${CYAN}📚 Swagger UI:${NC}    ${PROTOCOL}://${API_DOMAIN}/api/v1/docs"
        echo -e "  ${CYAN}📖 ReDoc:${NC}         ${PROTOCOL}://${API_DOMAIN}/api/v1/redoc"
        echo -e "  ${CYAN}💚 Health:${NC}        ${PROTOCOL}://${API_DOMAIN}/health"
        echo -e "  ${CYAN}🔍 Readiness:${NC}     ${PROTOCOL}://${API_DOMAIN}/ready"
        echo ""
        echo -e "  ${YELLOW}Note:${NC} The API root path (/) returns 404. Use the endpoints above."
        echo ""

        log_info "API Resources (require authentication):"
        echo -e "  ${CYAN}👤 Users:${NC}        http://api.localhost/api/v1/users"
        echo -e "  ${CYAN}🤖 Assistants:${NC}   http://api.localhost/api/v1/assistants"
        echo -e "  ${CYAN}💬 Chat:${NC}         http://api.localhost/api/v1/chat"
        echo -e "  ${CYAN}🔗 Connectors:${NC}   http://api.localhost/api/v1/connectors"
        echo -e "  ${CYAN}📄 Documents:${NC}    http://api.localhost/api/v1/documents"
        echo -e "  ${CYAN}🧠 LLMs:${NC}         http://api.localhost/api/v1/llms"
        echo -e "  ${CYAN}📊 Embeddings:${NC}   http://api.localhost/api/v1/embedding-models"
        echo ""

        log_info "Useful commands:"
        echo -e "  ${YELLOW}./cluster.sh -L logs${NC}      - View logs"
        echo -e "  ${YELLOW}./cluster.sh -L status${NC}    - Check status"
        echo -e "  ${YELLOW}./cluster.sh -L stop${NC}      - Stop cluster"
        echo ""
    fi
}

stop_cluster() {
    print_banner

    log_info "Mode: ${CYAN}${MODE}${NC} (${COMPOSE_FILE})"
    log_step "Stopping EchoMind cluster..."
    echo ""

    cd "$SCRIPT_DIR"
    docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE down

    echo ""
    log_success "Cluster stopped successfully!"
    echo ""
}

restart_cluster() {
    print_banner

    log_info "Mode: ${CYAN}${MODE}${NC} (${COMPOSE_FILE})"
    log_step "Restarting EchoMind cluster..."
    log_info "Using down + up to ensure env vars are refreshed"
    echo ""

    create_directories

    cd "$SCRIPT_DIR"
    docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE down
    docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE up -d

    echo ""
    log_success "Cluster restarted successfully!"
    echo ""
}

show_logs() {
    cd "$SCRIPT_DIR"

    if [ -z "$1" ]; then
        log_info "Showing logs for all services (Ctrl+C to exit)..."
        docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE logs -f
    else
        log_info "Showing logs for service: $1 (Ctrl+C to exit)..."
        docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE logs -f "$1"
    fi
}

show_status() {
    print_banner

    log_info "Mode: ${CYAN}${MODE}${NC} (${COMPOSE_FILE})"
    log_step "Cluster status:"
    echo ""

    cd "$SCRIPT_DIR"
    docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE ps

    echo ""
}

pull_images() {
    print_banner

    log_info "Mode: ${CYAN}${MODE}${NC} (${COMPOSE_FILE})"
    log_step "Pulling latest images..."
    echo ""

    cd "$SCRIPT_DIR"
    docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE pull

    echo ""
    log_success "Images updated successfully!"
    echo ""
}

build_services() {
    print_banner

    SERVICE="${1:-}"

    cd "$SCRIPT_DIR"

    log_info "Mode: ${CYAN}${MODE}${NC} (${COMPOSE_FILE})"

    if [ -z "$SERVICE" ]; then
        # Build all local services (uses cache - fast if no changes)
        log_step "Building all local services..."
        echo ""

        # All services with build contexts
        local services=("api" "migration" "embedder" "orchestrator" "connector" "ingestor" "guardian" "webui")

        for svc in "${services[@]}"; do
            log_info "Building ${svc}..."
            # Pass HF_TOKEN as build arg if set (for model pre-download)
            if [ -n "${HF_TOKEN:-}" ]; then
                log_info "  Using HF_TOKEN for ${svc}"
                docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE build --build-arg HF_TOKEN="$HF_TOKEN" "$svc"
            else
                docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE build "$svc"
            fi
            log_success "${svc} built"
        done

        echo ""
        log_success "All local services built!"
    else
        # Build specific service
        log_step "Building ${SERVICE}..."
        echo ""

        # Pass HF_TOKEN as build arg if set (for model pre-download)
        if [ -n "${HF_TOKEN:-}" ]; then
            log_info "Using HF_TOKEN for build"
            docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE build --build-arg HF_TOKEN="$HF_TOKEN" "$SERVICE"
        else
            docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE build "$SERVICE"
        fi

        echo ""
        log_success "${SERVICE} built!"
    fi

    local flag="-L"
    [ "$MODE" = "host" ] && flag="-H"
    log_info "Run ${YELLOW}./cluster.sh ${flag} start${NC} to start with new images"
    echo ""
}

rebuild_service() {
    print_banner

    SERVICE="${1:-api}"

    log_info "Mode: ${CYAN}${MODE}${NC} (${COMPOSE_FILE})"
    log_step "Rebuilding ${SERVICE} service..."
    echo ""

    create_directories

    cd "$SCRIPT_DIR"
    # Pass HF_TOKEN as build arg if set (for model pre-download)
    if [ -n "${HF_TOKEN:-}" ]; then
        log_info "Using HF_TOKEN for build"
        docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE build --no-cache --build-arg HF_TOKEN="$HF_TOKEN" "$SERVICE"
    else
        docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE build --no-cache "$SERVICE"
    fi
    docker compose $COMPOSE_ENV_FLAG -f "$COMPOSE_FILE" $OBSERVABILITY_FILES $OBSERVABILITY_PROFILE $LANGFUSE_FILES $LANGFUSE_PROFILE up -d --force-recreate "$SERVICE"

    echo ""
    log_success "${SERVICE} service rebuilt and restarted!"
    echo ""
}

get_version() {
    # Read version from .env file
    if [ -f "$SCRIPT_DIR/.env" ]; then
        grep -E "^ECHOMIND_VERSION=" "$SCRIPT_DIR/.env" | cut -d'=' -f2 | tr -d '\n\r '
    else
        echo "0.1.0-beta.1"
    fi
}

build_for_dockerhub() {
    print_banner
    
    VERSION=$(get_version)
    IMAGE_NAME="gsantopaolo/echomind-api"
    
    log_step "Building Docker image for Docker Hub..."
    log_info "Version: ${YELLOW}${VERSION}${NC}"
    log_info "Image: ${YELLOW}${IMAGE_NAME}:${VERSION}${NC}"
    echo ""
    
    cd "$SCRIPT_DIR"
    
    # Build with version tag and latest tag
    log_info "Building with tags: ${VERSION}, latest, beta"
    docker build \
        -t "${IMAGE_NAME}:${VERSION}" \
        -t "${IMAGE_NAME}:latest" \
        -t "${IMAGE_NAME}:beta" \
        -f "$PROJECT_ROOT/src/api/Dockerfile" \
        "$PROJECT_ROOT/src"
    
    echo ""
    log_success "Image built successfully!"
    log_info "Tagged as:"
    echo -e "  🏷️  ${GREEN}${IMAGE_NAME}:${VERSION}${NC}"
    echo -e "  🏷️  ${GREEN}${IMAGE_NAME}:latest${NC}"
    echo -e "  🏷️  ${GREEN}${IMAGE_NAME}:beta${NC}"
    echo ""
    log_info "Ready to push! Run: ${YELLOW}./cluster.sh push${NC}"
    echo ""
}

push_to_dockerhub() {
    print_banner
    
    VERSION=$(get_version)
    IMAGE_NAME="gsantopaolo/echomind-api"
    
    log_step "Pushing to Docker Hub..."
    log_info "Version: ${YELLOW}${VERSION}${NC}"
    echo ""
    
    # Check if logged in to Docker Hub
    if ! docker info 2>/dev/null | grep -q "Username"; then
        log_warning "Not logged in to Docker Hub"
        log_info "Please login first: ${YELLOW}docker login${NC}"
        exit 1
    fi
    
    log_info "Pushing ${IMAGE_NAME}:${VERSION}..."
    docker push "${IMAGE_NAME}:${VERSION}"
    
    log_info "Pushing ${IMAGE_NAME}:latest..."
    docker push "${IMAGE_NAME}:latest"
    
    log_info "Pushing ${IMAGE_NAME}:beta..."
    docker push "${IMAGE_NAME}:beta"
    
    echo ""
    log_success "Images pushed to Docker Hub!"
    log_info "Available at:"
    echo -e "  🐳 ${CYAN}https://hub.docker.com/r/gsantopaolo/echomind-api${NC}"
    echo ""
    log_info "Pull with:"
    echo -e "  ${YELLOW}docker pull ${IMAGE_NAME}:${VERSION}${NC}"
    echo -e "  ${YELLOW}docker pull ${IMAGE_NAME}:latest${NC}"
    echo -e "  ${YELLOW}docker pull ${IMAGE_NAME}:beta${NC}"
    echo ""
}

build_and_push() {
    print_banner
    
    VERSION=$(get_version)
    
    log_step "Building and pushing EchoMind API v${VERSION}"
    echo ""
    
    # Build
    log_info "Step 1/2: Building image..."
    build_for_dockerhub > /dev/null 2>&1 || {
        log_error "Build failed!"
        exit 1
    }
    log_success "Build complete"
    
    # Push
    log_info "Step 2/2: Pushing to Docker Hub..."
    push_to_dockerhub
}

show_help() {
    print_banner

    VERSION=$(get_version)

    echo "Usage: ./cluster.sh <--local|--host> <command>"
    echo ""
    echo -e "Current Version: ${CYAN}${VERSION}${NC}"
    echo ""
    echo "Mode (required):"
    echo -e "  ${GREEN}--local, -L${NC}  Local development (docker-compose.yml)"
    echo -e "  ${GREEN}--host, -H${NC}   Production host (docker-compose-host.yml)"
    echo ""
    echo "Cluster Management:"
    echo -e "  ${GREEN}start${NC}        Start the cluster"
    echo -e "  ${GREEN}stop${NC}         Stop the cluster"
    echo -e "  ${GREEN}restart${NC}      Restart the cluster"
    echo -e "  ${GREEN}status${NC}       Show cluster status"
    echo -e "  ${GREEN}logs${NC}         Show logs for all services"
    echo -e "  ${GREEN}logs <svc>${NC}   Show logs for specific service"
    echo ""
    echo "Image Management:"
    echo -e "  ${GREEN}pull${NC}           Pull latest images from registries"
    echo -e "  ${GREEN}build${NC}          Build all local services (uses cache)"
    echo -e "  ${GREEN}build <svc>${NC}    Build a specific service (uses cache)"
    echo -e "  ${GREEN}rebuild <svc>${NC}  Force rebuild (no cache) and restart"
    echo -e "  ${GREEN}build-release${NC}  Build API image for Docker Hub"
    echo -e "  ${GREEN}push${NC}           Push API image to Docker Hub"
    echo -e "  ${GREEN}release${NC}        Build and push API to Docker Hub"
    echo ""
    echo "Other:"
    echo -e "  ${GREEN}help${NC}         Show this help message"
    echo ""
    echo "Examples:"
    echo -e "  ${YELLOW}./cluster.sh --local start${NC}      # Start local cluster"
    echo -e "  ${YELLOW}./cluster.sh -L start${NC}           # Start local cluster (short)"
    echo -e "  ${YELLOW}./cluster.sh --host start${NC}       # Start production cluster"
    echo -e "  ${YELLOW}./cluster.sh -H logs api${NC}        # View API logs on host"
    echo -e "  ${YELLOW}./cluster.sh -L build${NC}           # Build all local services"
    echo -e "  ${YELLOW}./cluster.sh -H rebuild webui${NC}   # Rebuild webui on host"
    echo -e "  ${YELLOW}./cluster.sh -L stop${NC}            # Stop local cluster"
    echo ""
}

# Main (note: --host flag already shifted, so $1 is now the command)
case "${1:-}" in
    start)
        start_cluster
        ;;
    stop)
        stop_cluster
        ;;
    restart)
        restart_cluster
        ;;
    logs)
        shift  # Remove 'logs' from args
        show_logs "$1"
        ;;
    status)
        show_status
        ;;
    pull)
        pull_images
        ;;
    build)
        shift  # Remove 'build' from args
        build_services "$1"
        ;;
    rebuild)
        shift  # Remove 'rebuild' from args
        rebuild_service "$1"
        ;;
    build-release)
        build_for_dockerhub
        ;;
    push)
        push_to_dockerhub
        ;;
    release)
        build_and_push
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac
