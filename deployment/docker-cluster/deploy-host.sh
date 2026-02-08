#!/bin/bash
# ===============================================
# EchoMind Host Deployment Script
# For demo.echomind.ch
# ===============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 EchoMind Host Deployment"
echo "==========================="

# Check if running as root or with sudo for UFW
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Note: Run with sudo for UFW firewall configuration"
fi

# Create data directories
echo "📁 Creating data directories..."
mkdir -p ../../data/{postgres,qdrant,minio,nats,portainer}
mkdir -p ../../data/traefik/certificates
mkdir -p ../../data/authentik/{media,custom-templates,certs}

# Set up .env file
if [ ! -f .env ]; then
    if [ -f .env.host ]; then
        echo "📄 Setting up .env from .env.host template..."
        cp .env.host .env
        echo ""
        echo "⚠️  IMPORTANT: Edit .env and replace ALL placeholder values!"
        echo "   - CHANGE_ME_* values must be replaced with real secrets"
        echo "   - your-domain.example.com → your actual domain"
        echo "   - Generate secrets with: openssl rand -hex 32"
        echo ""
        echo "After editing .env, run this script again."
        exit 1
    else
        echo "❌ Error: .env.host template not found!"
        exit 1
    fi
else
    echo "✅ .env already exists"

    # Check if .env still has placeholder values
    if grep -q "CHANGE_ME_" .env 2>/dev/null; then
        echo "⚠️  WARNING: .env contains placeholder values (CHANGE_ME_*)"
        echo "   Please edit .env and replace all CHANGE_ME_* values with real secrets"
        echo ""
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Configure UFW firewall (if available and running as root)
if command -v ufw &> /dev/null && [ "$EUID" -eq 0 ]; then
    echo "🔒 Configuring UFW firewall..."
    ufw --force enable
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp   # SSH
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    ufw reload
    echo "✅ Firewall configured (22, 80, 443 open)"
else
    echo "⚠️  Skipping UFW (not available or not root)"
    echo "   Manually run:"
    echo "   sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable"
fi

# Pull images first
echo "📦 Pulling Docker images..."
docker compose -f docker-compose-host.yml pull

# Deploy
echo "🐳 Starting services..."
docker compose -f docker-compose-host.yml up -d

# Wait for services
echo "⏳ Waiting for services to start..."
sleep 10

# Show status
echo ""
echo "📊 Service Status:"
docker compose -f docker-compose-host.yml ps

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Public Endpoints:"
echo "   API:        https://api.demo.echomind.ch"
echo "   Auth:       https://auth.demo.echomind.ch"
echo "   MinIO:      https://minio.demo.echomind.ch"
echo "   Qdrant:     https://qdrant.demo.echomind.ch"
echo "   Portainer:  https://portainer.demo.echomind.ch"
echo ""
echo "🔧 Local Access (via SSH tunnel):"
echo "   Traefik Dashboard: ssh -L 8080:127.0.0.1:8080 root@SERVER_IP"
echo "   PostgreSQL:        ssh -L 5432:127.0.0.1:5432 root@SERVER_IP"
echo ""
echo "📋 Useful commands:"
echo "   Logs:    docker compose -f docker-compose-host.yml logs -f"
echo "   Stop:    docker compose -f docker-compose-host.yml down"
echo "   Restart: docker compose -f docker-compose-host.yml restart"
