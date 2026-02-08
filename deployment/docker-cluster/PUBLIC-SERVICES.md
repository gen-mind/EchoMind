# EchoMind Public Services Reference

This document lists all publicly accessible services in the EchoMind platform.

## 🌐 Application Services

| Service | URL | Description | Auth Required |
|---------|-----|-------------|---------------|
| **Web App** | `https://demo.echomind.ch` | Main web application UI | ✅ Yes (OIDC) |
| **API** | `https://api.demo.echomind.ch` | REST API backend | ✅ Yes (JWT) |

## 🔐 Authentication & Access Control

| Service | URL | Description | Auth Required |
|---------|-----|-------------|---------------|
| **Authentik** | `https://auth.demo.echomind.ch` | SSO/OIDC provider, user management | ✅ Yes (admin account) |

## 🗄️ Data Services

| Service | URL | Description | Auth Required |
|---------|-----|-------------|---------------|
| **Qdrant** | `https://qdrant.demo.echomind.ch` | Vector database web UI | ❌ No (public) |
| **Adminer** | `https://postgres.demo.echomind.ch` | PostgreSQL admin interface | ✅ Yes (Authentik SSO) |
| **MinIO Console** | `https://minio.demo.echomind.ch` | S3-compatible storage web UI | ✅ Yes (Authentik SSO) |
| **S3 API** | `https://s3.demo.echomind.ch` | S3-compatible API endpoint | ✅ Yes (access keys) |

## 🏗️ Infrastructure

| Service | URL | Description | Auth Required |
|---------|-----|-------------|---------------|
| **NATS** | `https://nats.demo.echomind.ch` | Message queue monitoring UI | ✅ Yes (Authentik SSO) |
| **Portainer** | `https://portainer.demo.echomind.ch` | Container management UI | ✅ Yes (Portainer account) |
| **Traefik** | `http://localhost:8080` (SSH tunnel) | Reverse proxy dashboard | ❌ No (localhost only) |

## 🧠 ML & Analytics

| Service | URL | Description | Auth Required |
|---------|-----|-------------|---------------|
| **TensorBoard** | `https://tensorboard.demo.echomind.ch` | ML training metrics visualization | ✅ Yes (Authentik SSO) |

## 📊 Observability (Optional - enabled via `.env`)

| Service | URL | Description | Auth Required |
|---------|-----|-------------|---------------|
| **Grafana** | `https://grafana.demo.echomind.ch` | Metrics dashboards | ✅ Yes (Grafana/Authentik) |
| **Prometheus** | `https://prometheus.demo.echomind.ch` | Metrics database & query UI | ✅ Yes (Authentik SSO) |

## 🔬 LLM Observability (Optional - enabled via `.env`)

| Service | URL | Description | Auth Required |
|---------|-----|-------------|---------------|
| **Langfuse** | `https://langfuse.demo.echomind.ch` | LLM tracing, evaluation & analytics | ✅ Yes (Langfuse account) |

---

## 📡 API Endpoints

### Documentation
- **Swagger UI**: `https://api.demo.echomind.ch/api/v1/docs` (Interactive API documentation)
- **ReDoc**: `https://api.demo.echomind.ch/api/v1/redoc` (Alternative API documentation)

### Health Checks
- **Health**: `https://api.demo.echomind.ch/health`
- **Readiness**: `https://api.demo.echomind.ch/ready`

### Resources (require JWT authentication)
- **Users**: `/api/v1/users`
- **Assistants**: `/api/v1/assistants`
- **Chat**: `/api/v1/chat`
- **Connectors**: `/api/v1/connectors`
- **Documents**: `/api/v1/documents`
- **LLMs**: `/api/v1/llms`
- **Embedding Models**: `/api/v1/embedding-models`

---

## 🔒 Security Notes

### Authentik SSO Protection
The following services are protected by Authentik forward auth (SSO required):
- Adminer (PostgreSQL UI)
- MinIO Console
- NATS UI
- Portainer
- TensorBoard
- Grafana (optional OAuth)
- Prometheus

### Public Access (No Auth)
⚠️ **WARNING**: The following services are publicly accessible:
- Qdrant Web UI

### Local Access Only
The following services are only accessible via SSH tunnel:
- Traefik Dashboard: `ssh -L 8080:127.0.0.1:8080 root@SERVER_IP` → `http://localhost:8080`
- PostgreSQL Direct: `ssh -L 5432:127.0.0.1:5432 root@SERVER_IP` → `psql -h localhost`

---

## 🌍 Environment Variables

All domain names are derived from the `DOMAIN` variable in `.env`:

```bash
DOMAIN=demo.echomind.ch

# Derived subdomains:
AUTHENTIK_DOMAIN=auth.${DOMAIN}
API_DOMAIN=api.${DOMAIN}
QDRANT_DOMAIN=qdrant.${DOMAIN}
MINIO_DOMAIN=minio.${DOMAIN}
S3_DOMAIN=s3.${DOMAIN}
NATS_DOMAIN=nats.${DOMAIN}
POSTGRES_DOMAIN=postgres.${DOMAIN}  # Adminer UI
PORTAINER_DOMAIN=portainer.${DOMAIN}
TENSORBOARD_DOMAIN=tensorboard.${DOMAIN}

# Observability (if enabled):
GRAFANA_DOMAIN=grafana.${DOMAIN}
PROMETHEUS_DOMAIN=prometheus.${DOMAIN}

# LLM Observability (if enabled):
LANGFUSE_DOMAIN=langfuse.${DOMAIN}
```

---

## 📋 Service Status Check

To view all running services:
```bash
./cluster.sh -H status
```

To view logs:
```bash
./cluster.sh -H logs              # All services
./cluster.sh -H logs api          # Specific service
```

---

## 🔧 Troubleshooting

### Service Not Accessible
1. Check service is running: `./cluster.sh -H status`
2. Check Traefik routes: `docker logs echomind-traefik | grep -i "rule=Host"`
3. Check SSL certificate: `docker logs echomind-traefik | grep -i acme`
4. Verify DNS: `nslookup <subdomain>.demo.echomind.ch`

### Authentication Issues
1. Verify Authentik is running: `docker logs echomind-authentik-server`
2. Check OIDC configuration in `.env`: `WEB_OIDC_CLIENT_ID`, `WEB_OIDC_CLIENT_SECRET`
3. Test Authentik directly: `https://auth.demo.echomind.ch`

### SSL Certificate Issues
1. Check Let's Encrypt rate limits (5 certs/week per domain)
2. Verify `ACME_EMAIL` in `.env`
3. Check Traefik acme.json: `ls -lh /path/to/data/traefik/certificates/acme.json`
