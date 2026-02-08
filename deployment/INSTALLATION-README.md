# EchoMind Automated Server Installation

Complete automated installation system for deploying EchoMind on Hetzner dedicated servers.

## Features

✅ **Fully Automated** - Minimal manual intervention required
✅ **Idempotent** - Safe to re-run multiple times
✅ **Production-Ready** - HTTPS, fail2ban, UFW firewall
✅ **Auto-Generation** - Creates missing secrets automatically
✅ **Comprehensive Logging** - All steps logged for debugging
✅ **Validation** - Checks prerequisites and configuration

---

## Quick Start

### 1. Prepare Configuration

```bash
cd /root  # Or your preferred installation directory

# Clone repository (if not already cloned)
git clone https://github.com/gen-mind/EchoMind.git echo-mind
cd echo-mind/deployment

# Copy configuration template
cp echomind-install.conf.template echomind-install.conf

# Edit configuration
nano echomind-install.conf
```

### 2. Fill Required Fields

**Minimum required fields in `echomind-install.conf`:**

```bash
# Your domain (e.g., echomind.pinewood.com)
DOMAIN="echomind.pinewood.com"

# Server public IP
SERVER_IP="65.108.201.29"

# Email for Let's Encrypt SSL
ACME_EMAIL="admin@pinewood.com"

# PostgreSQL password (strong password)
POSTGRES_PASSWORD="your-strong-password-here"

# Authentik secret key (generate with: openssl rand -hex 32)
AUTHENTIK_SECRET_KEY="your-64-char-hex-string-here"

# Authentik admin password
AUTHENTIK_BOOTSTRAP_PASSWORD="your-admin-password-here"

# MinIO password (strong password)
MINIO_ROOT_PASSWORD="your-minio-password-here"
```

**Optional fields** (auto-generated if empty):
- Langfuse secrets (NEXTAUTH, SALT, ENCRYPTION_KEY, etc.)
- Grafana admin password (if ENABLE_OBSERVABILITY=true)

### 3. Configure DNS

**CRITICAL:** Before running installation, configure DNS records.

**Option A: Wildcard CNAME (Recommended)**
```
Type: A
Name: echomind
Value: 65.108.201.29

Type: CNAME
Name: *
Value: echomind.pinewood.com
```

**Option B: Individual A Records**

See `excluded/todo-installation.md` for detailed DNS setup instructions.

### 4. Run Installation

```bash
# Make script executable (if not already)
chmod +x install-echomind-server.sh

# Run installation
bash install-echomind-server.sh
```

The script will:
1. ✅ Validate configuration
2. ✅ Ask for confirmation
3. ✅ Install system packages (fail2ban, git, curl, etc.)
4. ✅ Configure UFW firewall (ports 22, 80, 443)
5. ✅ Install Docker (pinned version 28.5.2)
6. ✅ Clone repositories (echo-mind + echo-mind-webui)
7. ✅ Generate .env.host with your configuration
8. ✅ Create data directories with proper permissions
9. ✅ Deploy EchoMind cluster
10. ✅ Display access URLs and next steps

**Installation time:** ~15-30 minutes (depending on internet speed)

---

## Configuration File Reference

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `DOMAIN` | Base domain for all services | `echomind.pinewood.com` |
| `SERVER_IP` | Public IP of server | `65.108.201.29` |
| `ACME_EMAIL` | Email for Let's Encrypt | `admin@pinewood.com` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `strong-random-password` |
| `AUTHENTIK_SECRET_KEY` | Authentik secret (64 chars hex) | `openssl rand -hex 32` |
| `AUTHENTIK_BOOTSTRAP_PASSWORD` | Authentik admin password | `admin-password` |
| `MINIO_ROOT_PASSWORD` | MinIO password | `minio-password` |

### Optional Fields

| Field | Description | Default |
|-------|-------------|---------|
| `ENABLE_OBSERVABILITY` | Enable Grafana/Prometheus/Loki | `false` |
| `ENABLE_LANGFUSE` | Enable LLM tracing | `true` |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | Auto-generated |
| `HF_TOKEN` | HuggingFace token (for models) | Empty |
| `SKIP_INSTALLIMAGE` | Skip Ubuntu install step | `false` |
| `SKIP_DOCKER_INSTALL` | Skip Docker installation | `false` |
| `INSTALL_DIR` | Installation directory | `/root` |
| `TZ` | Timezone | `Europe/Zurich` |

### Auto-Generated Fields

These are automatically generated if not provided:

- `LANGFUSE_NEXTAUTH_SECRET`
- `LANGFUSE_SALT`
- `LANGFUSE_ENCRYPTION_KEY`
- `LANGFUSE_CLICKHOUSE_PASSWORD`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_INIT_PASSWORD`

---

## Post-Installation Steps

After successful installation, **REQUIRED** manual steps:

### 1. Configure Authentik OIDC

1. Login to Authentik: `https://auth.echomind.pinewood.com`
2. Create OAuth2 Provider for `echomind-web`
3. Update `.env.host` with client ID and secret
4. Restart cluster

**Detailed instructions:** `excluded/todo-installation.md` → Section 3

### 2. Test Access

Visit all service URLs to verify SSL certificates and accessibility:

- 🌐 **Web App:** `https://echomind.pinewood.com`
- 🔐 **Authentik:** `https://auth.echomind.pinewood.com`
- 🚀 **API Docs:** `https://api.echomind.pinewood.com/api/v1/docs`
- 🔍 **Qdrant:** `https://qdrant.echomind.pinewood.com`
- 📦 **MinIO:** `https://minio.echomind.pinewood.com`
- 🐳 **Portainer:** `https://portainer.echomind.pinewood.com`

### 3. Optional: PyCharm Docker Setup

Connect PyCharm to remote Docker for debugging.

**Detailed instructions:** `excluded/todo-installation.md` → Section 4

---

## File Structure

```
deployment/
├── install-echomind-server.sh          # Main installation script
├── echomind-install.conf.template      # Configuration template
├── echomind-install.conf               # Your configuration (create from template)
├── install-YYYYMMDD-HHMMSS.log         # Installation log (auto-generated)
├── INSTALLATION-README.md              # This file
└── docker-cluster/
    ├── cluster.sh                      # Cluster management script
    ├── docker-compose-host.yml         # Production Docker Compose
    └── .env.host                       # Generated environment config

excluded/
├── todo-installation.md                # Post-installation manual steps
└── installation-credentials.txt        # Generated credentials (mode 600)
```

---

## Useful Commands

### Cluster Management

```bash
cd /root/echo-mind/deployment/docker-cluster

# View status
./cluster.sh -H status

# View logs (all services)
./cluster.sh -H logs

# View logs (specific service)
./cluster.sh -H logs api

# Restart cluster
./cluster.sh -H restart

# Stop cluster
./cluster.sh -H stop

# Start cluster
./cluster.sh -H start

# Rebuild service (no cache)
./cluster.sh -H rebuild api
```

### Monitoring

```bash
# System resources
htop

# Container stats
docker stats

# Disk usage
df -h
du -sh /root/echo-mind/data/*

# Network connections
sudo ss -tulpen | egrep ':(22|80|443)\b'
```

### Logs

```bash
# Installation log
cat /root/echo-mind/deployment/install-*.log

# Service logs
docker logs echomind-api
docker logs echomind-traefik
docker logs echomind-authentik-server

# Follow logs
docker logs -f echomind-api
```

### Firewall

```bash
# Check UFW status
sudo ufw status verbose

# Allow additional port (if needed)
sudo ufw allow 8080/tcp

# Reload firewall
sudo ufw reload
```

---

## Troubleshooting

### Installation Fails

1. **Check log file:** `cat deployment/install-*.log`
2. **Verify configuration:** `nano deployment/echomind-install.conf`
3. **Check prerequisites:**
   ```bash
   docker --version       # Should be 28.5.2
   docker compose version # Should be 2.x
   ufw status            # Should be active
   ```

### DNS Not Resolving

```bash
# Test DNS propagation
dig echomind.pinewood.com +short
dig api.echomind.pinewood.com +short

# If not resolving, check:
# 1. DNS records created correctly
# 2. Wait 5-10 minutes for propagation
# 3. Try different DNS server: dig @8.8.8.8 echomind.pinewood.com
```

### SSL Certificates Not Generating

```bash
# Check Traefik logs
docker logs echomind-traefik 2>&1 | grep -i acme

# Common issues:
# - DNS not propagated (wait longer)
# - Port 443 blocked (check UFW)
# - Let's Encrypt rate limit (wait 1 week or use staging)
# - Invalid ACME email (check .env.host)
```

### Services Not Starting

```bash
# Check specific service logs
./cluster.sh -H logs <service-name>

# Common issues:
# - Database not ready: Check postgres health
# - Missing environment variables: Check .env.host
# - Port conflicts: Check if ports in use (netstat -tlpn)
# - Docker resource limits: Check docker stats
```

### Re-run Installation

The script is **idempotent** and can be re-run safely:

```bash
# Fix configuration
nano echomind-install.conf

# Re-run installation
bash install-echomind-server.sh

# Script will:
# - Skip already-completed steps
# - Regenerate .env.host with new config
# - Restart cluster with updated configuration
```

---

## Advanced Options

### Skip Steps

If you already have Ubuntu 24.04 and Docker installed:

```bash
# In echomind-install.conf:
SKIP_INSTALLIMAGE=true
SKIP_DOCKER_INSTALL=true
```

### Custom Installation Directory

```bash
# In echomind-install.conf:
INSTALL_DIR="/opt/echomind"
```

### Use Different Repositories

```bash
# In echomind-install.conf:
ECHOMIND_REPO="https://github.com/your-fork/EchoMind.git"
ECHOMIND_WEBUI_REPO="https://github.com/your-fork/echomind-webui.git"
ECHOMIND_BRANCH="develop"
ECHOMIND_WEBUI_BRANCH="feature/new-ui"
```

### Enable All Features

```bash
# In echomind-install.conf:
ENABLE_OBSERVABILITY=true
ENABLE_LANGFUSE=true
GRAFANA_ADMIN_PASSWORD="your-grafana-password"
```

---

## Security Considerations

### Generated Credentials

The installation script saves all credentials to:
```
/root/echo-mind/excluded/installation-credentials.txt
```

**File permissions:** `600` (owner read/write only)

**Contents:**
- PostgreSQL credentials
- Authentik admin credentials
- MinIO credentials
- Langfuse credentials (if enabled)
- Grafana credentials (if enabled)

**⚠️ IMPORTANT:** Keep this file secure! Consider:
1. Move to encrypted storage
2. Use password manager
3. Delete from server after copying

### Firewall Configuration

The installation script configures UFW to allow **ONLY**:
- Port 22 (SSH)
- Port 80 (HTTP, redirects to HTTPS)
- Port 443 (HTTPS)

All other ports are **DENIED** by default.

### SSH Hardening (Recommended)

After installation, consider:

```bash
# Disable root password login (key-only)
nano /etc/ssh/sshd_config
# Set: PermitRootLogin prohibit-password
# Set: PasswordAuthentication no
systemctl restart sshd

# Change SSH port (optional, reduces bot attacks)
# Set: Port 2222
# Don't forget: ufw allow 2222/tcp && ufw delete allow 22/tcp
```

---

## Support & Documentation

| Resource | Location |
|----------|----------|
| **Post-Installation Steps** | `excluded/todo-installation.md` |
| **DNS Setup Guide** | `excluded/todo-installation.md` → Section 1 |
| **Authentik OIDC Setup** | `excluded/todo-installation.md` → Section 3 |
| **PyCharm Docker Setup** | `excluded/todo-installation.md` → Section 4 |
| **Architecture Docs** | `docs/architecture.md` |
| **Service Docs** | `docs/services/*.md` |
| **API Specification** | `docs/api-spec.md` |
| **Deployment Guide** | `deployment/docker-cluster/README.md` |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-08 | Initial release |

---

**Author:** EchoMind Team
**License:** (See repository root LICENSE file)
**Repository:** https://github.com/gen-mind/EchoMind
