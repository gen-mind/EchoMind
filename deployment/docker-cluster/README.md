# EchoMind Docker Cluster

Complete Docker Compose setup for EchoMind development and production deployment.

## Architecture

### Services

- **Traefik** - Reverse proxy with automatic routing
- **PostgreSQL** - Shared database (Authentik + API)
- **Redis** - Cache for Authentik
- **Authentik** - OIDC authentication provider
- **Qdrant** - Vector database for embeddings
- **MinIO** - S3-compatible object storage
- **NATS** - Message bus for microservices
- **EchoMind API** - FastAPI application

### Networks

- **frontend** - External-facing services (Traefik, Authentik, API)
- **backend** - Internal services (PostgreSQL, Redis, Qdrant, MinIO, NATS)

## Quick Start

### 1. Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available

### 2. Setup

```bash
# Navigate to deployment directory
cd deployment/docker-cluster

# Copy environment template
cp .env.example .env

# Edit .env with your values
nano .env
```

### 3. Required Configuration

Edit `.env` and set:

```bash
# PostgreSQL
POSTGRES_PASSWORD=<strong_password>

# Authentik
AUTHENTIK_SECRET_KEY=$(openssl rand -base64 32)

# MinIO
MINIO_ROOT_PASSWORD=<strong_password>
```

### 4. Create Data Directories

```bash
# From project root
mkdir -p data/{postgres,authentik/{redis,media,custom-templates,certs},qdrant,minio,nats,traefik/certificates}
```

### 5. Start Services

```bash
# Build and start all services
docker compose up -d

# View logs
docker compose logs -f

# Check service status
docker compose ps
```

## Service Access

### Local Development (HTTP)

| Service | URL | Description |
|---------|-----|-------------|
| **Authentik** | http://auth.localhost | OIDC authentication provider |
| **MinIO Console** | http://minio.localhost | Object storage management |
| **Traefik Dashboard** | http://localhost:8080 | Reverse proxy dashboard |

### API Endpoints (Base: http://api.localhost)

> **Note**: The API root path (`/`) returns `{"detail":"Not Found"}` - this is expected behavior. Use the specific endpoints below.

#### Health & Documentation (No Auth Required)

| Endpoint | URL | Description |
|----------|-----|-------------|
| **Health Check** | http://api.localhost/health | Liveness probe - returns `{"status":"ok"}` |
| **Readiness** | http://api.localhost/ready | Checks all dependencies (DB, Qdrant, NATS, etc.) |
| **Swagger UI** | http://api.localhost/api/v1/docs | Interactive API documentation |
| **ReDoc** | http://api.localhost/api/v1/redoc | API reference documentation |
| **OpenAPI Spec** | http://api.localhost/api/v1/openapi.json | OpenAPI 3.0 specification |

#### API Resources (Authentication Required)

| Resource | URL | Description |
|----------|-----|-------------|
| **Users** | http://api.localhost/api/v1/users | User management |
| **Assistants** | http://api.localhost/api/v1/assistants | AI assistant configurations |
| **Chat** | http://api.localhost/api/v1/chat | Chat sessions and messages |
| **Connectors** | http://api.localhost/api/v1/connectors | Data source connections |
| **Documents** | http://api.localhost/api/v1/documents | Ingested documents |
| **LLMs** | http://api.localhost/api/v1/llms | LLM model configurations |
| **Embedding Models** | http://api.localhost/api/v1/embedding-models | Embedding model configurations |

#### WebSocket

| Endpoint | URL | Description |
|----------|-----|-------------|
| **Chat Stream** | ws://api.localhost/api/v1/ws/chat | Real-time chat streaming |

### Production (HTTPS - after enabling SSL)

| Service | URL |
|---------|-----|
| **Authentik** | https://auth.echomind.genmind.ch |
| **MinIO Console** | https://minio.echomind.genmind.ch |
| **API Health** | https://api.echomind.genmind.ch/health |
| **API Docs** | https://api.echomind.genmind.ch/api/v1/docs |

## Switching to Production (HTTPS)

### 1. Update `.env`

```bash
DOMAIN=echomind.genmind.ch
```

### 2. Uncomment SSL Config in `docker-compose.yml`

Find and uncomment these sections:

**Traefik service** (lines ~73-76):
```yaml
- "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
- "--certificatesresolvers.letsencrypt.acme.email=gp@genmind.it"
- "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
- "--entrypoints.web.http.redirections.entryPoint.to=websecure"
- "--entrypoints.web.http.redirections.entryPoint.scheme=https"
```

**Service labels** - For each service (api, authentik, minio):
```yaml
# - "traefik.http.routers.<service>.entrypoints=websecure"
# - "traefik.http.routers.<service>.tls.certresolver=letsencrypt"
```

### 3. Restart Services

```bash
docker compose down
docker compose up -d
```

## Database Management

### PostgreSQL Databases

The init script creates two databases:
- `authentik` - Authentik authentication
- `echomind` - API application data

### Connect to PostgreSQL

```bash
docker compose exec postgres psql -U echomind -d echomind
```

### Run Migrations

```bash
# API migrations (Alembic)
docker compose exec api alembic upgrade head
```

## Backup & Restore

### Backup PostgreSQL

```bash
docker compose exec postgres pg_dumpall -U echomind > backup.sql
```

### Backup Qdrant

```bash
tar -czf qdrant-backup.tar.gz data/qdrant/
```

### Backup MinIO

```bash
tar -czf minio-backup.tar.gz data/minio/
```

## Troubleshooting

### Service Not Starting

```bash
# Check logs
docker compose logs <service_name>

# Example: Check API logs
docker compose logs api
```

### Reset Everything

```bash
# Stop and remove containers
docker compose down -v

# Remove data (WARNING: deletes all data)
rm -rf ../../data/*

# Recreate and start
mkdir -p ../../data/{postgres,authentik/redis,qdrant,minio,nats,traefik/certificates}
docker compose up -d
```

### Port Conflicts

If ports 80/443 are in use:

```bash
# Check what's using the port
sudo lsof -i :80
sudo lsof -i :443

# Stop conflicting services
sudo systemctl stop nginx  # or apache2
```

## Quick API Tests

Verify the API is working correctly:

```bash
# Health check (should return {"status":"ok"})
curl http://api.localhost/health

# Readiness probe (checks all dependencies)
curl http://api.localhost/ready

# OpenAPI spec (JSON)
curl http://api.localhost/api/v1/openapi.json | head -100
```

## Monitoring

### Health Checks

```bash
# All services
docker compose ps

# Specific service health
docker inspect echomind-api --format='{{.State.Health.Status}}'
```

### Resource Usage

```bash
docker stats
```

## Configuration Files

### Directory Structure

```
EchoMind/
├── deployment/docker-cluster/
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── .env
│   └── README.md
├── config/
│   ├── api/
│   │   └── api.env
│   ├── postgres/
│   │   └── init-db.sql
│   ├── authentik/
│   ├── qdrant/
│   ├── minio/
│   └── nats/
└── data/                    # Gitignored
    ├── postgres/
    ├── authentik/
    ├── qdrant/
    ├── minio/
    ├── nats/
    └── traefik/
```

## Security Notes

### Development
- Default passwords in `.env.example` are NOT secure
- HTTP is used (no encryption)

### Production
- Generate strong passwords
- Enable HTTPS with Let's Encrypt
- Use secrets management (Docker Secrets or external vault)
- Configure firewall rules
- Enable Authentik 2FA

## Next Steps

1. **Configure Authentik**:
   - Access http://auth.localhost
   - Complete initial setup
   - Create OIDC provider for API

2. **Configure MinIO**:
   - Access http://minio.localhost
   - Create buckets for documents

3. **Test API**:
   - Health check: `curl http://api.localhost/health`
   - API docs: http://api.localhost/api/v1/docs
   - Readiness: `curl http://api.localhost/ready`

4. **Run Migrations**:
   ```bash
   docker compose exec api alembic upgrade head
   ```

## Support

For issues or questions, refer to the main project documentation.
