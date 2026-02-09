# Google OAuth V1 Limitations & Known Issues

**Version:** 1.0
**Last Updated:** 2026-02-09
**Applies To:** EchoMind V1 (User Delegation Pattern)

This document outlines the current limitations, known issues, and workarounds for Google OAuth integration in EchoMind V1. These limitations are inherent to the V1 architecture (User Delegation pattern) and Google's OAuth implementation.

---

## Table of Contents

1. [Critical Limitations](#critical-limitations)
2. [Operational Limitations](#operational-limitations)
3. [Known Issues](#known-issues)
4. [Workarounds](#workarounds)
5. [V2 Improvements](#v2-improvements)
6. [References](#references)

---

## Critical Limitations

### 1. No Wildcard Subdomain Support ⚠️ **CRITICAL**

**Issue:**
Google OAuth **does not support wildcard subdomains** in authorized redirect URIs. You cannot use `https://*.echomind.ch/api/v1/google/auth/callback`.

**Impact:**
- **Manual setup required** for each customer subdomain
- **Time cost:** 5 minutes per new customer deployment
- **Risk:** Forgetting to add a subdomain breaks OAuth for that customer

**Evidence:**
- [Google OAuth2 Developers Group Discussion](https://groups.google.com/g/oauth2-dev/c/x7OPvf2xL0Q) (confirmed 2018, still valid 2026)
- Quote: "Redirect URIs must be an exact match. Wildcards are not supported for security reasons."

**Workaround:**
- Maintain list of customer subdomains in internal documentation
- Add new subdomain to Google Cloud Console when deploying for new customer
- See: [Adding New Customer Subdomains](./google-oauth-setup.md#adding-new-customer-subdomains)

**V2 Solution:**
Customer-managed OAuth apps (V2.3) allow customers to use their own domain, eliminating EchoMind admin involvement.

---

### 2. Per-User Authorization Required

**Issue:**
Each EchoMind user must individually authorize Google access. There is no "organization-wide" authorization in V1.

**Impact:**
- **Onboarding friction:** New users must click "Connect to Google" before using connectors
- **Higher OAuth volume:** More OAuth requests = higher risk of hitting rate limits
- **No shared resource access:** Users can only access their personal Google data (not org-wide Shared Drives)

**Example Scenario:**
- Company has 100 employees using EchoMind
- All 100 must individually connect their Google Drive
- If 10 users forget, their Drive data won't be indexed

**Workaround:**
- Provide clear onboarding instructions emphasizing Google connection
- Send reminder emails to users who haven't connected after 7 days
- Dashboard widget showing "Connect Google to unlock Drive search"

**V2 Solution:**
Service Account support (V2.1) enables admin to authorize once for entire organization.

---

### 3. Read-Only Access Only

**Issue:**
V1 uses **read-only scopes** (`drive.readonly`, `gmail.readonly`, etc.). Users cannot perform write operations from EchoMind.

**Impact:**
- Cannot create Drive documents
- Cannot send Gmail messages
- Cannot create Calendar events
- Cannot add Contacts

**Why Read-Only:**
- **Security:** Reduces attack surface (compromised EchoMind = data leak, not data modification)
- **Scope creep prevention:** Prevents feature requests like "Send email from EchoMind"
- **Trust:** Users more comfortable granting read access vs. write access

**Workaround:**
None (this is intentional design). If write access needed, request in V2.

**V2 Solution:**
Carefully scope write permissions per feature (e.g., `gmail.send` only if email integration feature enabled).

---

## Operational Limitations

### 4. No Automated Quota Monitoring

**Issue:**
Google APIs have daily quota limits (default: 10,000 requests/day per API). V1 has **no automated monitoring** of quota usage.

**Impact:**
- **Risk of hitting limits unexpectedly** during high-usage periods
- **No alerting** when approaching quota limit
- **Manual checking required** via Google Cloud Console

**Current Monitoring Process:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to "APIs & Services" > "Dashboard"
3. Select API (e.g., Google Drive API)
4. Click "Quotas" tab
5. Manually check usage percentage

**Workaround:**
- Set weekly calendar reminder to check quota usage
- Reduce connector sync frequency if usage is high (e.g., 120 min instead of 60 min)
- Request quota increase from Google if consistently hitting limits

**V2 Solution:**
Prometheus metrics + Grafana dashboard + auto-throttling (V2.2).

---

### 5. Token Refresh Edge Cases

**Issue:**
Google refresh tokens can become invalid in certain edge cases:

1. **User changed password:** Refresh token immediately invalidated
2. **User revoked access:** Token invalidated (expected)
3. **6 months of inactivity:** Google auto-revokes unused refresh tokens
4. **Maximum refresh tokens reached:** Google allows 50 refresh tokens per user per OAuth client. Oldest token auto-revoked when limit exceeded.

**Impact:**
- Connector sync fails silently
- User sees "Authorization failed" error when manually triggering sync
- User must re-authorize to fix

**Current Error Handling:**
```python
try:
    files = await fetch_drive_files(credential.access_token)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        # Token invalid — attempt refresh
        try:
            new_token = await refresh_google_token(credential.refresh_token)
        except Exception:
            # Refresh failed — notify user to re-authorize
            logger.error(f"Refresh token invalid for user {user_id}")
            # (Currently no user notification — V2 feature)
```

**Workaround:**
- Add monitoring for 401 errors in connector logs
- Send email notification when refresh fails: "Please reconnect your Google account"

**V2 Solution:**
- Proactive token health checks (weekly background job)
- In-app notification when token expires
- Auto-prompt re-authorization on next login

---

### 6. Single OAuth App for All Customers

**Issue:**
All customer deployments share the same Google OAuth app (same `client_id` and `client_secret`).

**Impact:**
- **Shared quota pool:** All customers' API requests count toward same daily quota (10,000 req/day per API)
- **Branding:** Users see "EchoMind" in OAuth consent screen (not customer's company name)
- **Audit trail:** Google Cloud Console logs show all customers' OAuth activity mixed together
- **Security:** If credentials leak, ALL customers' OAuth is compromised

**Workaround:**
- Monitor quota usage carefully
- Request quota increase from Google if needed
- Rotate `client_secret` regularly (every 90 days)

**V2 Solution:**
Customer-managed OAuth apps (V2.3) allow each customer to use their own OAuth app.

---

## Known Issues

### 7. False Success Toast on 422 Validation Error

**Status:** ✅ **FIXED** in V1.1 (2026-02-09)

**Issue (V1.0):**
When connector creation fails with 422 (validation error), frontend still showed "Connector created successfully" toast.

**Root Cause:**
`createConnector()` API function returned `null` on error, but `ConnectorCreateModal.handleSubmit()` didn't check for `null` before showing success toast.

**Fix:**
```typescript
// Before (V1.0)
const result = await createConnector(localStorage.token, data);
toast.success($i18n.t('Connector created successfully'));  // WRONG

// After (V1.1)
const result = await createConnector(localStorage.token, data);
if (!result) {
  toast.error($i18n.t('Failed to create connector. Please try again.'));
  return;
}
toast.success($i18n.t('Connector created successfully'));  // Correct
```

**Verification:**
- Test: Create Gmail connector without authorizing OAuth first
- Expected: Error toast "Please authorize with Google first using the button above"
- Actual (V1.1): ✅ Correct error shown

---

### 8. Generic Error Messages (Pre-V1.1)

**Status:** ✅ **FIXED** in V1.1 (2026-02-09)

**Issue (V1.0):**
All OAuth errors showed generic message: "Failed to connect gmail: Error: ..."

**Problems:**
- 501 (OAuth not configured) → Generic "failed" message (user doesn't know to contact admin)
- Popup blocked → Generic "failed" message (user doesn't know to allow popups)
- Timeout → Generic "failed" message

**Fix (V1.1):**
Added specific error messages in `Connectors.svelte`:
- 501: "Google integration is not configured on this server. Please contact your system administrator..."
- Popup blocked: "Popup was blocked by your browser. Please allow popups for this site..."
- Timeout: "Authorization timed out. Please try again."
- 401/403: "Authentication failed. Please sign in again."

**Additionally:** Admin sees console error with setup instructions for 501:
```javascript
console.error(
  '[ADMIN ACTION REQUIRED] Google OAuth not configured. Required environment variables:\n' +
  '  GOOGLE_CLIENT_ID=...\n' +
  '  GOOGLE_CLIENT_SECRET=...\n' +
  'Setup guide: https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred'
);
```

---

### 9. Missing OAuth Button in Connector Modal (Pre-V1.1)

**Status:** ✅ **FIXED** in V1.1 (2026-02-09)

**Issue (V1.0):**
When user clicked "+ Add Connector" and selected Google service (Drive, Gmail, etc.), modal showed message:
> "Requires Google OAuth. Use the Google Workspace section above to connect first."

**Problems:**
- No OAuth button in modal (user must go back to workspace section)
- Confusing UX (why can't I authorize from here?)
- Unnecessary navigation (workspace → modal → back to workspace → back to modal)

**Fix (V1.1):**
- Added **OAuth button directly in modal** when Google service selected
- Button appears automatically when service requires OAuth and user hasn't authorized
- Three states:
  1. **Not configured (backend):** Red error box "Google Service Not Available" (contact admin)
  2. **Not authorized (user):** Blue box with "Connect to Google" button
  3. **Authorized:** Green checkmark "Connected to Google" + continue with connector creation

**User Flow (V1.1):**
1. Click "+ Add Connector"
2. Select "Gmail"
3. See OAuth button ("Connect to Google")
4. Click button → OAuth popup opens
5. Authorize in popup
6. Popup closes, modal shows "Connected to Google"
7. Fill in connector name
8. Click "Create" → Connector created successfully

---

## Workarounds

### High OAuth Request Volume

**Problem:** Many users authorizing simultaneously (e.g., company-wide rollout) → risk of hitting rate limits.

**Workaround:**
- **Stagger onboarding:** Roll out to 20 users/day instead of all 100 at once
- **Off-peak hours:** Schedule onboarding during low-traffic hours (e.g., 2am UTC)
- **Increase quota:** Request quota increase from Google ([instructions](https://support.google.com/cloud/answer/6158857))

---

### Shared Drive Access

**Problem:** V1 User Delegation only accesses files user owns or has explicit access to. Cannot access org-wide Shared Drives.

**Workaround:**
- **Grant user access:** Admin adds users to Shared Drive with "Viewer" role
- **Use Service Account (V2):** Wait for V2.1 release with Service Account support

---

### Refresh Token Lost

**Problem:** User changed password → refresh token invalidated → connector stops syncing.

**Workaround:**
- User must manually reconnect Google account (click workspace card → authorize again)
- **Detection:** Check connector status page for "Last sync" timestamp (if > 1 day old, likely token issue)

---

## V2 Improvements

### Planned for V2.1 (Service Account Support)
- ✅ Organization-wide authorization (admin authorizes once for all users)
- ✅ Access to Shared Drives and organizational resources
- ✅ No per-user OAuth friction
- ⚠️ Requires Google Workspace (not personal gmail.com)

### Planned for V2.2 (Monitoring & Throttling)
- ✅ Prometheus metrics for OAuth success rate, API quota usage, errors
- ✅ Grafana dashboard with real-time quota usage visualization
- ✅ Alerts when approaching quota limits (80%, 90%, 95%)
- ✅ Auto-throttling to prevent hitting hard limits

### Planned for V2.3 (Customer-Managed OAuth)
- ✅ Customers can use their own OAuth app (own `client_id`/`client_secret`)
- ✅ Quota isolation (customer's requests don't affect others)
- ✅ Custom branding (company name in OAuth consent screen)
- ✅ Own domain support (e.g., `oauth.customer.com/callback`)

---

## References

### Google Documentation

- [OAuth 2.0 Wildcard Redirect URIs (Not Supported)](https://groups.google.com/g/oauth2-dev/c/x7OPvf2xL0Q)
- [OAuth 2.0 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)
- [Google Drive API Quotas](https://developers.google.com/drive/api/guides/limits)
- [Requesting Quota Increase](https://support.google.com/cloud/answer/6158857)

### EchoMind Documentation

- [Google OAuth Setup Guide](./google-oauth-setup.md) — Admin setup instructions
- [Google OAuth Architecture](../integrations/google-oauth-architecture.md) — How it works
- [Connecting Google Services](../user-guides/connecting-google-services.md) — User guide

---

**Last Updated:** 2026-02-09
**Document Version:** 1.0
**Status:** Current Limitations (V1)
