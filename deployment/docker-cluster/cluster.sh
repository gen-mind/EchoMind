#!/bin/bash

# ======================================
# EchoMind Docker Cluster Manager
# ======================================
#
# USAGE:
#   ./cluster.sh <command>
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
#   rebuild        - Rebuild API service locally and restart it
#   build          - Build API Docker image for Docker Hub with proper tags
#   push           - Push built API image to Docker Hub (requires 'docker login')
#   release        - Build and push API image to Docker Hub in one command
#
# EXAMPLES:
#   ./cluster.sh start              # Start the cluster
#   ./cluster.sh logs api           # View API logs
#   ./cluster.sh build              # Build image for Docker Hub
#   ./cluster.sh release            # Build and push to Docker Hub
#   ./cluster.sh stop               # Stop the cluster
#
# REQUIREMENTS:
#   - Docker and Docker Compose installed
#   - .env file configured (copy from .env.example)
#   - For push/release: docker login with username 'gsantopaolo'
#
# VERSIONING:
#   - Version is read from /VERSION file at project root
#   - Current: 0.1.0-beta.1 (Semantic Versioning 2.0)
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
        log_error ".env file not found"
        log_info "Copy .env.example to .env and configure it:"
        echo -e "  ${YELLOW}cp .env.example .env${NC}"
        echo -e "  ${YELLOW}nano .env${NC}"
        exit 1
    fi
    log_success ".env file found"
}

create_directories() {
    log_step "Creating data directories..."
    
    mkdir -p "$PROJECT_ROOT/data/postgres"
    mkdir -p "$PROJECT_ROOT/data/qdrant"
    mkdir -p "$PROJECT_ROOT/data/minio"
    mkdir -p "$PROJECT_ROOT/data/nats"
    mkdir -p "$PROJECT_ROOT/data/authentik/media"
    mkdir -p "$PROJECT_ROOT/data/authentik/custom-templates"
    mkdir -p "$PROJECT_ROOT/data/authentik/certs"
    mkdir -p "$PROJECT_ROOT/data/traefik/certificates"
    
    log_success "Data directories created"
}

start_cluster() {
    print_banner
    
    check_prerequisites
    create_directories
    
    log_step "Starting EchoMind cluster..."
    echo ""
    
    cd "$SCRIPT_DIR"
    docker compose up -d
    
    echo ""
    log_success "Cluster started successfully!"
    echo ""
    
    log_info "Services available at:"
    echo -e "  ${GREEN}🔐 Authentik:${NC}  http://auth.localhost"
    echo -e "  ${GREEN}📦 MinIO:${NC}      http://minio.localhost"
    echo -e "  ${GREEN}📊 Traefik:${NC}    http://localhost:8080"
    echo ""

    log_info "API Endpoints (base: http://api.localhost):"
    echo -e "  ${CYAN}📚 Swagger UI:${NC}   http://api.localhost/api/v1/docs"
    echo -e "  ${CYAN}📖 ReDoc:${NC}        http://api.localhost/api/v1/redoc"
    echo -e "  ${CYAN}💚 Health:${NC}       http://api.localhost/health"
    echo -e "  ${CYAN}🔍 Readiness:${NC}    http://api.localhost/ready"
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
    echo -e "  ${YELLOW}./cluster.sh logs${NC}      - View logs"
    echo -e "  ${YELLOW}./cluster.sh status${NC}    - Check status"
    echo -e "  ${YELLOW}./cluster.sh stop${NC}      - Stop cluster"
    echo ""
}

stop_cluster() {
    print_banner
    
    log_step "Stopping EchoMind cluster..."
    echo ""
    
    cd "$SCRIPT_DIR"
    docker compose down
    
    echo ""
    log_success "Cluster stopped successfully!"
    echo ""
}

restart_cluster() {
    print_banner
    
    log_step "Restarting EchoMind cluster..."
    echo ""
    
    cd "$SCRIPT_DIR"
    docker compose restart
    
    echo ""
    log_success "Cluster restarted successfully!"
    echo ""
}

show_logs() {
    cd "$SCRIPT_DIR"
    
    if [ -z "$2" ]; then
        log_info "Showing logs for all services (Ctrl+C to exit)..."
        docker compose logs -f
    else
        log_info "Showing logs for service: $2 (Ctrl+C to exit)..."
        docker compose logs -f "$2"
    fi
}

show_status() {
    print_banner
    
    log_step "Cluster status:"
    echo ""
    
    cd "$SCRIPT_DIR"
    docker compose ps
    
    echo ""
}

pull_images() {
    print_banner
    
    log_step "Pulling latest images..."
    echo ""
    
    cd "$SCRIPT_DIR"
    docker compose pull
    
    echo ""
    log_success "Images updated successfully!"
    echo ""
}

rebuild_api() {
    print_banner
    
    log_step "Rebuilding API service..."
    echo ""
    
    cd "$SCRIPT_DIR"
    docker compose build --no-cache api
    docker compose up -d api
    
    echo ""
    log_success "API service rebuilt and restarted!"
    echo ""
}

get_version() {
    # Read version from VERSION file at project root
    if [ -f "$PROJECT_ROOT/VERSION" ]; then
        cat "$PROJECT_ROOT/VERSION" | tr -d '\n\r '
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
    
    echo "Usage: ./cluster.sh [COMMAND]"
    echo ""
    echo -e "Current Version: ${CYAN}${VERSION}${NC}"
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
    echo -e "  ${GREEN}pull${NC}         Pull latest images from registries"
    echo -e "  ${GREEN}rebuild${NC}      Rebuild API service locally"
    echo -e "  ${GREEN}build${NC}        Build API image for Docker Hub"
    echo -e "  ${GREEN}push${NC}         Push API image to Docker Hub"
    echo -e "  ${GREEN}release${NC}      Build and push API to Docker Hub"
    echo ""
    echo "Other:"
    echo -e "  ${GREEN}help${NC}         Show this help message"
    echo ""
    echo "Examples:"
    echo -e "  ${YELLOW}./cluster.sh start${NC}"
    echo -e "  ${YELLOW}./cluster.sh logs api${NC}"
    echo -e "  ${YELLOW}./cluster.sh build${NC}"
    echo -e "  ${YELLOW}./cluster.sh release${NC}"
    echo -e "  ${YELLOW}./cluster.sh stop${NC}"
    echo ""
}

# Main
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
        show_logs "$@"
        ;;
    status)
        show_status
        ;;
    pull)
        pull_images
        ;;
    rebuild)
        rebuild_api
        ;;
    build)
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
