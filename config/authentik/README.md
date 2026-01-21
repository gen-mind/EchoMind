# Authentik Configuration

Authentik configuration is handled via environment variables in docker-compose.yml.

## Initial Setup

### Bootstrap Admin Credentials

The default admin account is automatically created on first startup using environment variables:

- **Username:** `akadmin`
- **Password:** Set in `.env` file as `AUTHENTIK_BOOTSTRAP_PASSWORD`
- **Email:** Set in `.env` file as `AUTHENTIK_BOOTSTRAP_EMAIL`

**Configuration in `.env`:**
```bash
AUTHENTIK_BOOTSTRAP_PASSWORD=your_secure_password_here
AUTHENTIK_BOOTSTRAP_EMAIL=admin@echomind.local
```

These credentials are **only read on the first startup**. After initial setup, change the password through the Authentik admin interface.

### Access Authentik

1. **Navigate to:** http://auth.localhost
2. **Login with:**
   - Username: `akadmin`
   - Password: (from your `.env` file)

### Post-Setup Steps

1. **Configure OIDC Provider for EchoMind API:**
   - Go to Applications → Providers
   - Create new OAuth2/OIDC Provider
   - Name: `EchoMind API`
   - Client type: `Confidential`
   - Redirect URIs: `http://api.localhost/auth/callback`
   - Scopes: `openid`, `email`, `profile`
   - Note Client ID and Secret

2. **Create Application:**
   - Go to Applications → Applications
   - Create new Application
   - Name: `EchoMind`
   - Slug: `echomind`
   - Provider: Select `EchoMind API` provider

3. **Update API Configuration:**
   Add to `config/api/api.env`:
   ```bash
   API_AUTH_CLIENT_ID=<client-id-from-authentik>
   API_AUTH_CLIENT_SECRET=<client-secret-from-authentik>
   API_AUTH_JWKS_URL=http://authentik-server:9000/application/o/echomind/.well-known/jwks.json
   ```

## User Management

- Create users via Authentik admin panel
- Assign groups for role-based access
- Configure flows for custom authentication logic

## Production Recommendations

- Enable 2FA/MFA
- Configure email provider for notifications
- Set up SSO integrations (Google, Microsoft, etc.)
- Configure branding/custom templates
- Enable audit logging
- Set up backup for media files
