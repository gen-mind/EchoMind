# Google OAuth 2.0 Setup Guide for EchoMind

**Version:** 1.0
**Last Updated:** 2026-02-09
**Applies To:** EchoMind V1 (User Delegation Pattern)

This guide walks you through setting up Google OAuth 2.0 for EchoMind's Google Workspace connectors (Drive, Gmail, Calendar, Contacts). This is a **one-time setup** that enables OAuth for **all customer deployments** on your `*.echomind.ch` subdomains.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Create Google Cloud Project](#step-1-create-google-cloud-project)
3. [Step 2: Enable Required APIs](#step-2-enable-required-apis)
4. [Step 3: Configure OAuth Consent Screen](#step-3-configure-oauth-consent-screen)
5. [Step 4: Create OAuth 2.0 Client ID](#step-4-create-oauth-20-client-id)
6. [Step 5: Configure Backend Environment Variables](#step-5-configure-backend-environment-variables)
7. [Adding New Customer Subdomains](#adding-new-customer-subdomains)
8. [Troubleshooting](#troubleshooting)
9. [Security Best Practices](#security-best-practices)
10. [References](#references)

---

## Prerequisites

- **Google Cloud Platform account** with billing enabled (OAuth is free, but requires billing account)
- **Admin access** to EchoMind backend `.env` files
- **SSH access** to customer deployment servers
- **Domain ownership verified** for `echomind.ch` (for subdomain redirect URIs)

**Estimated Time:** 20-30 minutes for initial setup, 5 minutes per additional customer subdomain.

---

## Step 1: Create Google Cloud Project

1. **Navigate to Google Cloud Console**
   - Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
   - Sign in with your Google account (preferably a dedicated service account email)

2. **Create a New Project**
   - Click the project dropdown in the top navigation bar
   - Click **"New Project"**
   - **Project Name:** `EchoMind OAuth` (or your preferred name)
   - **Organization:** Your organization (if applicable)
   - Click **"Create"**

3. **Select the Project**
   - Once created, ensure the project is selected in the project dropdown

**Why?** A dedicated project keeps OAuth credentials isolated and makes auditing easier.

---

## Step 2: Enable Required APIs

Google Workspace connectors require specific APIs to be enabled:

1. **Navigate to API Library**
   - In the left sidebar, go to **"APIs & Services" > "Library"**

2. **Enable the following APIs** (search for each and click "Enable"):
   - **Google Drive API** (for Drive connector)
   - **Gmail API** (for Gmail connector)
   - **Google Calendar API** (for Calendar connector)
   - **People API** (for Contacts connector)

3. **Verify Enabled APIs**
   - Go to **"APIs & Services" > "Enabled APIs & services"**
   - Confirm all four APIs are listed

**References:**
- [Enabling APIs](https://support.google.com/googleapi/answer/6158841)

---

## Step 3: Configure OAuth Consent Screen

The consent screen is what users see when authorizing EchoMind to access their Google data.

1. **Navigate to OAuth Consent Screen**
   - Go to **"APIs & Services" > "OAuth consent screen"**

2. **Select User Type**
   - **Internal:** Use if all users are within your Google Workspace organization
   - **External:** Use if users will authenticate with personal Google accounts or accounts from other orgs
   - For multi-customer deployments, choose **External**

3. **Fill in App Information**
   - **App name:** `EchoMind` (or `EchoMind - [Your Company Name]`)
   - **User support email:** Your support email (e.g., `support@yourcompany.com`)
   - **App logo:** Optional (upload EchoMind logo if available)
   - **Application home page:** `https://demo.echomind.ch` (or your main domain)
   - **Application privacy policy:** Link to your privacy policy
   - **Application terms of service:** Link to your terms of service
   - **Authorized domains:** Add `echomind.ch`
   - **Developer contact information:** Your email address

4. **Save and Continue**

5. **Add Scopes**
   - Click **"Add or Remove Scopes"**
   - Add the following scopes:
     ```
     https://www.googleapis.com/auth/drive.readonly
     https://www.googleapis.com/auth/drive.metadata.readonly
     https://www.googleapis.com/auth/gmail.readonly
     https://www.googleapis.com/auth/calendar.readonly
     https://www.googleapis.com/auth/contacts.readonly
     ```
   - Click **"Update"**
   - Click **"Save and Continue"**

6. **Add Test Users** (if using External and not yet published)
   - Add email addresses of users who will test the integration
   - For production, publish the app to **"In Production"** status

7. **Review and Submit**
   - Review all settings
   - Click **"Back to Dashboard"**

**References:**
- [Setting up OAuth 2.0](https://support.google.com/googleapi/answer/6158849)

---

## Step 4: Create OAuth 2.0 Client ID

1. **Navigate to Credentials**
   - Go to **"APIs & Services" > "Credentials"**

2. **Create Credentials**
   - Click **"+ Create Credentials"**
   - Select **"OAuth client ID"**

3. **Configure OAuth Client**
   - **Application type:** `Web application`
   - **Name:** `EchoMind Web Client` (or your preferred name)

4. **Add Authorized JavaScript Origins**
   - Click **"+ Add URI"** under "Authorized JavaScript origins"
   - Add your deployment domains (examples):
     ```
     https://demo.echomind.ch
     https://customer-a.echomind.ch
     https://customer-b.echomind.ch
     ```
   - Add one per customer deployment

5. **Add Authorized Redirect URIs** ⚠️ **CRITICAL**
   - Click **"+ Add URI"** under "Authorized redirect URIs"
   - **Pattern:** `https://<subdomain>.echomind.ch/api/v1/google/auth/callback`
   - **Examples:**
     ```
     https://demo.echomind.ch/api/v1/google/auth/callback
     https://customer-a.echomind.ch/api/v1/google/auth/callback
     https://customer-b.echomind.ch/api/v1/google/auth/callback
     ```
   - **IMPORTANT:** Each redirect URI must be an **exact match**. Google does **NOT support wildcard subdomains** (e.g., `https://*.echomind.ch/...` will NOT work).
   - Add one URI per customer deployment.

6. **Create Client**
   - Click **"Create"**
   - A dialog appears with your **Client ID** and **Client Secret**
   - **COPY BOTH VALUES IMMEDIATELY** — you'll need them for backend configuration

7. **Download JSON** (optional)
   - Click **"Download JSON"** to save credentials
   - Store securely in your password manager or secrets vault

**⚠️ Security Note:**
Your Client Secret is sensitive. **Never commit it to version control.** Store it securely (e.g., 1Password, HashiCorp Vault, AWS Secrets Manager).

**References:**
- [Using OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google OAuth 2.0 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)

---

## Step 5: Configure Backend Environment Variables

Now that you have your OAuth credentials, configure each EchoMind backend instance.

### 5.1 Local Development

Edit `/Users/gp/Developer/echo-mind/.env`:

```bash
# Google OAuth Configuration (V1 - User Delegation Pattern)
GOOGLE_CLIENT_ID=123456789-abcdefg.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret-here
GOOGLE_REDIRECT_URI=https://demo.echomind.ch/api/v1/google/auth/callback

# Frontend URL for OAuth redirects
OAUTH_FRONTEND_URL=https://demo.echomind.ch
```

**Replace:**
- `GOOGLE_CLIENT_ID`: Your Client ID from Step 4
- `GOOGLE_CLIENT_SECRET`: Your Client Secret from Step 4
- `GOOGLE_REDIRECT_URI`: The redirect URI for this deployment (must match Google Cloud Console exactly)
- `OAUTH_FRONTEND_URL`: Your frontend domain (no trailing slash)

### 5.2 Production Deployment

For each customer deployment (e.g., `customer-a.echomind.ch`):

1. **SSH into the server:**
   ```bash
   ssh user@customer-a.echomind.ch
   cd /path/to/echomind
   ```

2. **Edit `.env` file:**
   ```bash
   nano .env
   ```

3. **Add OAuth variables:**
   ```bash
   GOOGLE_CLIENT_ID=123456789-abcdefg.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-your-secret-here
   GOOGLE_REDIRECT_URI=https://customer-a.echomind.ch/api/v1/google/auth/callback
   OAUTH_FRONTEND_URL=https://customer-a.echomind.ch
   ```

4. **Restart services:**
   ```bash
   ./cluster.sh -H rebuild
   ```

### 5.3 Verify Configuration

Test the OAuth configuration endpoint:

```bash
curl https://customer-a.echomind.ch/api/v1/google/auth/configured
```

**Expected response:**
```json
{
  "configured": true
}
```

**If you get `"configured": false`:**
- Check `.env` file has all four variables
- Ensure variables are not empty or contain placeholder values
- Restart backend services
- Check logs: `docker logs echomind-api -f | grep -i google`

---

## Adding New Customer Subdomains

When deploying EchoMind for a new customer, you must **manually add their subdomain** to the Google Cloud Console.

### Steps:

1. **Go to Google Cloud Console**
   - Navigate to [API Credentials](https://console.cloud.google.com/apis/credentials)
   - Select the **EchoMind OAuth** project

2. **Edit OAuth Client**
   - Click your OAuth client ID (e.g., "EchoMind Web Client")

3. **Add New Redirect URI**
   - Scroll to **"Authorized redirect URIs"**
   - Click **"+ Add URI"**
   - Enter: `https://customer-new.echomind.ch/api/v1/google/auth/callback`
   - **Replace `customer-new`** with the actual subdomain

4. **Add JavaScript Origin** (optional)
   - Scroll to **"Authorized JavaScript origins"**
   - Click **"+ Add URI"**
   - Enter: `https://customer-new.echomind.ch`

5. **Save Changes**
   - Click **"Save"**
   - Changes take effect immediately (no waiting period)

6. **Configure Backend**
   - Follow [Step 5.2](#52-production-deployment) to configure the new deployment's `.env` file

**Estimated Time:** 5 minutes per subdomain.

---

## Troubleshooting

### Problem: "Google OAuth is not configured" error in frontend

**Symptoms:**
- Users see error: "Google integration is not configured on this server"
- `/api/v1/google/auth/configured` returns `{"configured": false}`

**Solutions:**
1. **Check `.env` file:**
   ```bash
   cat .env | grep GOOGLE
   ```
   All four variables (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `OAUTH_FRONTEND_URL`) must be set.

2. **Verify no empty values:**
   ```bash
   # Should NOT see any lines with empty values
   grep -E '^GOOGLE.*=\s*$' .env
   ```

3. **Restart services:**
   ```bash
   ./cluster.sh -H rebuild
   ```

4. **Check API logs:**
   ```bash
   docker logs echomind-api -f | grep -i google
   ```

---

### Problem: "redirect_uri_mismatch" error during OAuth

**Symptoms:**
- OAuth popup shows error: `Error 400: redirect_uri_mismatch`
- Full error: "The redirect URI in the request, `https://customer-x.echomind.ch/api/v1/google/auth/callback`, does not match the ones authorized for the OAuth client."

**Solutions:**
1. **Verify redirect URI in `.env` exactly matches Google Cloud Console:**
   - Open Google Cloud Console → [API Credentials](https://console.cloud.google.com/apis/credentials)
   - Click your OAuth client ID
   - Check "Authorized redirect URIs" section
   - **Exact match required** (case-sensitive, no trailing slashes)

2. **Add missing redirect URI:**
   - If the URI is missing, click **"+ Add URI"**
   - Enter the exact URI from your `.env` file
   - Click **"Save"**

3. **Common mistakes:**
   - Trailing slash: `https://demo.echomind.ch/api/v1/google/auth/callback/` ❌ (remove slash)
   - HTTP instead of HTTPS: `http://demo.echomind.ch/...` ❌ (use HTTPS)
   - Missing `/api/v1`: `https://demo.echomind.ch/google/auth/callback` ❌

**References:**
- [Redirect URI mismatch error](https://support.google.com/cloud/answer/15549257)

---

### Problem: Users see "Authorization was cancelled" but didn't cancel

**Symptoms:**
- OAuth popup closes immediately
- Frontend shows: "Authorization was cancelled or failed"

**Solutions:**
1. **Check browser popup blocker:**
   - Disable popup blocker for `*.echomind.ch`
   - Try again

2. **Check OAuth consent screen status:**
   - Go to Google Cloud Console → **"OAuth consent screen"**
   - If status is "Testing", ensure user is added to "Test users"
   - Consider publishing to "Production" status

3. **Check scope permissions:**
   - Ensure all required scopes are added to OAuth consent screen (Step 3)

---

### Problem: "No refresh token received from Google"

**Symptoms:**
- OAuth flow fails with: "No refresh token received from Google. Re-authorize with prompt=consent."

**Solutions:**
1. **User already authorized:** Google only sends refresh tokens on first authorization. To force re-consent:
   - User must revoke access: [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions)
   - Or, backend can call `prompt=consent` (already implemented for first-time auth)

2. **Incremental authorization issue:**
   - If user previously authorized with fewer scopes, Google may not send refresh token
   - Have user disconnect (via EchoMind UI) and reconnect

**References:**
- [Google OAuth refresh tokens](https://developers.google.com/identity/protocols/oauth2/web-server#offline)

---

### Problem: OAuth works on demo but fails on customer subdomain

**Checklist:**
1. ✅ **Redirect URI added to Google Cloud Console?** (Step 4.5)
2. ✅ **`.env` file updated on customer server?** (Step 5.2)
3. ✅ **Services restarted after `.env` change?** (`./cluster.sh -H rebuild`)
4. ✅ **DNS resolves?** (`nslookup customer-x.echomind.ch`)
5. ✅ **HTTPS certificate valid?** Check browser for certificate errors
6. ✅ **Redirect URI in `.env` exactly matches Google Cloud Console?**

---

## Security Best Practices

### 1. Rotate Client Secrets Regularly

**Recommendation:** Rotate every 90 days.

**Steps:**
1. Go to Google Cloud Console → [API Credentials](https://console.cloud.google.com/apis/credentials)
2. Click your OAuth client ID
3. Click **"Add secret"**
4. Update `.env` files across all deployments
5. After all deployments updated, delete old secret

### 2. Use Least-Privilege Scopes

EchoMind V1 uses **read-only scopes** only:
- `drive.readonly` (NOT `drive` full access)
- `gmail.readonly` (NOT `gmail.modify`)
- `calendar.readonly` (NOT `calendar`)
- `contacts.readonly`

**Never request write scopes** unless V2 explicitly requires them.

### 3. Monitor OAuth Usage

Google Cloud Console provides quota monitoring:
- Go to **"APIs & Services" > "Dashboard"**
- Select each API (Drive, Gmail, Calendar, People)
- Check **"Quotas"** tab
- Default limit: **10,000 requests/day** per API

**Set up alerts:**
- Go to **"Monitoring" > "Alerting"**
- Create alert when usage exceeds 80% of quota

### 4. Audit Authorized Users

Periodically review users who have authorized EchoMind:
- Users can revoke at: [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions)
- Backend admin can revoke via: `DELETE /api/v1/google/auth` (per-user)

### 5. Keep Client Secret Secure

- **Never commit** to version control
- Store in secrets manager (1Password, Vault, AWS Secrets Manager)
- Limit access to ops team only
- Use environment-specific secrets (dev vs prod)

**References:**
- [OAuth 2.0 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)

---

## References

### Official Google Documentation

1. **[Using OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)**
   Comprehensive guide for web server OAuth implementation.

2. **[Setting up OAuth 2.0](https://support.google.com/googleapi/answer/6158849)**
   Step-by-step setup guide from Google.

3. **[OAuth 2.0 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)**
   Security and implementation best practices.

4. **[Manage OAuth Clients](https://support.google.com/cloud/answer/15549257)**
   Guide to managing OAuth clients in Google Cloud Console.

5. **[Enabling APIs](https://support.google.com/googleapi/answer/6158841)**
   How to enable Google APIs in your project.

### EchoMind Documentation

- [Google OAuth Architecture](../integrations/google-oauth-architecture.md) — How OAuth works in EchoMind
- [Google OAuth Limitations](./google-oauth-limitations.md) — V1 limitations and V2 roadmap
- [Connecting Google Services (User Guide)](../user-guides/connecting-google-services.md) — For end users

### External Resources

- **Google Cloud Console:** [https://console.cloud.google.com/](https://console.cloud.google.com/)
- **API Credentials:** [https://console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)
- **OAuth 2.0 Playground:** [https://developers.google.com/oauthplayground/](https://developers.google.com/oauthplayground/) — Test OAuth flows

---

## Support

If you encounter issues not covered in this guide:

1. **Check EchoMind logs:**
   ```bash
   docker logs echomind-api -f | grep -i google
   ```

2. **Verify configuration:**
   ```bash
   curl https://your-domain.echomind.ch/api/v1/google/auth/configured
   ```

3. **Contact Support:**
   - Email: `support@yourcompany.com`
   - GitHub Issues: [https://github.com/gen-mind/echo-mind/issues](https://github.com/gen-mind/echo-mind/issues)

---

**Last Updated:** 2026-02-09
**Document Version:** 1.0
**Applies To:** EchoMind V1 (User Delegation Pattern)
