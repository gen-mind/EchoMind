# EchoMind Quick Start Guide

First-time setup after cloning from Git.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available
- Ports 80, 443, 8080 available

## Step 1: Environment Configuration

```bash
cd deployment/docker-cluster

# Copy environment template
cp .env.example .env

# Generate a secure Authentik secret key
SECRET_KEY=$(openssl rand -base64 32)
echo "Generated secret key: $SECRET_KEY"

# Edit .env and set:
# - POSTGRES_PASSWORD (choose a strong password)
# - AUTHENTIK_SECRET_KEY (paste the generated key)
# - MINIO_ROOT_PASSWORD (choose a strong password)
nano .env
```

### Required .env Values

```bash
# PostgreSQL - IMPORTANT: Set this BEFORE first start, it cannot be changed easily later
POSTGRES_PASSWORD=your_secure_password_here

# Authentik - Generate with: openssl rand -base64 32
AUTHENTIK_SECRET_KEY=your_generated_secret_key

# MinIO
MINIO_ROOT_PASSWORD=your_minio_password_here
```

## Step 2: Create Data Directories

```bash
# From deployment/docker-cluster directory
mkdir -p ../../data/{postgres,authentik/{media,custom-templates,certs},qdrant,minio,nats,traefik/certificates}
```

## Step 3: Start the Cluster

```bash
./cluster.sh start
```

Wait for all services to start (check with `./cluster.sh status`).

## Step 4: Configure Authentik (OIDC Provider)

### 4.1 Access Authentik Admin

- URL: http://auth.localhost
- Username: `akadmin`
- Password: value of `AUTHENTIK_BOOTSTRAP_PASSWORD` from your `.env`

### 4.2 Create OAuth2 Provider

1. Go to **Applications > Providers**
2. Click **Create**
3. Select **OAuth2/OpenID Provider**
4. Configure:

| Field | Value |
|-------|-------|
| Name | `EchoMind OAuth2` |
| Authorization flow | `default-provider-authorization-implicit-consent` |
| Client type | `Public` |
| Client ID | Copy this value (auto-generated) or set custom like `echomind-web` |
| Redirect URIs | `http://localhost:5173/callback` |
| Signing Key | Select any available key |

5. Under **Advanced protocol settings**:
   - Access token validity: `hours=1`
   - Scopes: Ensure `openid`, `profile`, `email` are selected

6. Click **Create**

### 4.3 Create Application

1. Go to **Applications > Applications**
2. Click **Create**
3. Configure:

| Field | Value |
|-------|-------|
| Name | `EchoMind` |
| Slug | `echo-mind` |
| Provider | Select `EchoMind OAuth2` (created above) |

4. Click **Create**

### 4.4 Note Your Configuration

After creating, note these values:

```
Client ID: <from provider settings>
Issuer URL: http://auth.localhost/application/o/echo-mind/
JWKS URL: http://auth.localhost/application/o/echo-mind/jwks/
```

## Step 5: Configure Web App

```bash
cd ../../web

# Copy environment template
cp .env.example .env

# Edit with your Authentik values
nano .env
```

Set these values in `web/.env`:

```bash
VITE_API_BASE_URL=http://api.localhost
VITE_OIDC_AUTHORITY=http://auth.localhost/application/o/echo-mind/
VITE_OIDC_CLIENT_ID=<your-client-id-from-step-4>
VITE_OIDC_REDIRECT_URI=http://localhost:5173/callback
VITE_OIDC_POST_LOGOUT_REDIRECT_URI=http://localhost:5173
VITE_OIDC_SCOPE=openid profile email
```

## Step 6: Update API Configuration

Edit `deployment/docker-cluster/docker-compose.yml` and update the API auth settings to match your Authentik configuration:

```yaml
# Find the api service and update these environment variables:
- API_AUTH_ISSUER=http://auth.localhost/application/o/echo-mind/
- API_AUTH_AUDIENCE=<your-client-id-from-step-4>
- API_AUTH_JWKS_URL=http://authentik-server:9000/application/o/echo-mind/jwks/
```

Then restart the API:

```bash
cd deployment/docker-cluster
./cluster.sh restart
```

## Step 7: Start Web App

```bash
cd web
npm install
npm run dev
```

Access the web app at http://localhost:5173

## Step 8: Verify Setup

### Check API Health

```bash
curl http://api.localhost/health
# Expected: {"status":"ok"}

curl http://api.localhost/ready
# Expected: {"status":"ready","checks":{...}}
```

### Check Services

```bash
./cluster.sh status
```

All services should show as "running" and "healthy".

## Service URLs

| Service | URL |
|---------|-----|
| Web App | http://localhost:5173 |
| API Docs | http://api.localhost/api/v1/docs |
| API Health | http://api.localhost/health |
| Authentik Admin | http://auth.localhost |
| MinIO Console | http://minio.localhost |
| Traefik Dashboard | http://localhost:8080 |

## Troubleshooting

### PostgreSQL Password Errors

If you see "password authentication failed for user echomind":

```bash
# The password in the volume doesn't match .env
# Option 1: Sync password (keeps data) - run from project root
../../scripts/fix-postgres-password.sh

# Option 2: Reset completely (loses all data)
./cluster.sh stop
rm -rf ../../data/postgres/*
./cluster.sh start
```

**Important**: `POSTGRES_PASSWORD` only applies on first initialization. If you change it later, you must run the fix script.

### Services Not Starting

```bash
# Check logs for specific service
./cluster.sh logs postgres
./cluster.sh logs api
./cluster.sh logs authentik-server
```

### Port Conflicts

```bash
# Check what's using port 80
sudo lsof -i :80
```

### Reset Everything

```bash
./cluster.sh stop
rm -rf ../../data/*
mkdir -p ../../data/{postgres,authentik/{media,custom-templates,certs},qdrant,minio,nats,traefik/certificates}
./cluster.sh start
```

## Next Steps

1. Create a test user in Authentik (Users > Create)
2. Login to the web app
3. Explore the API at http://api.localhost/api/v1/docs
4. Configure connectors for data ingestion

## Useful Commands

```bash
./cluster.sh start    # Start all services
./cluster.sh stop     # Stop all services
./cluster.sh restart  # Restart all services
./cluster.sh status   # Show service status
./cluster.sh logs     # View all logs
./cluster.sh logs api # View specific service logs
```
