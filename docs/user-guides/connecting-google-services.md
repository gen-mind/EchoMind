# Connecting Google Services to EchoMind

**Audience:** End Users
**Estimated Time:** 2-3 minutes per service
**Last Updated:** 2026-02-09

This guide shows you how to connect your Google account to EchoMind so you can search your Drive files, Gmail messages, Calendar events, and Contacts directly from EchoMind.

---

## Table of Contents

1. [Overview](#overview)
2. [Before You Begin](#before-you-begin)
3. [Connecting Google Services](#connecting-google-services)
4. [What Permissions Are Requested?](#what-permissions-are-requested)
5. [Managing Your Connection](#managing-your-connection)
6. [Troubleshooting](#troubleshooting)
7. [Privacy & Security](#privacy--security)
8. [FAQ](#faq)

---

## Overview

EchoMind can connect to your Google Workspace services to make your personal data searchable:

| Service | What Gets Indexed | Search Examples |
|---------|------------------|-----------------|
| **Google Drive** | Files you own or have access to | "Find the Q4 budget spreadsheet" |
| **Gmail** | Your email messages and attachments | "Emails from John about the project" |
| **Google Calendar** | Your calendar events and meeting notes | "What meetings do I have tomorrow?" |
| **Google Contacts** | Your contact information | "Find Sarah's phone number" |

**Important:** You must connect your Google account before these services become available in EchoMind.

---

## Before You Begin

### Requirements

- **Google Account:** Personal (gmail.com) or Google Workspace account
- **Browser:** Chrome, Firefox, Safari, or Edge (popup blocker disabled for EchoMind)
- **EchoMind Account:** You must be logged in to EchoMind

### Is Google OAuth Configured?

If you see an error message "Google integration is not configured," contact your system administrator. This means the EchoMind server hasn't been set up for Google OAuth yet.

---

## Connecting Google Services

### Method 1: Via Workspace Section (Recommended)

1. **Navigate to Connectors Page**
   - Click **"Workspace"** in the left sidebar
   - Then click **"Connectors"**

2. **Find Google Workspace Section**
   - You'll see four cards: Drive, Gmail, Calendar, Contacts
   - Each shows "Click to connect" or "Connected" status

3. **Click a Service Card**
   - Example: Click the **"Google Drive"** card (📁 icon)

4. **Authorize in Popup**
   - A popup window opens showing Google's consent screen
   - Select your Google account (if you have multiple)
   - Review the permissions (see [What Permissions Are Requested?](#what-permissions-are-requested))
   - Click **"Allow"**

5. **Confirmation**
   - Popup closes automatically
   - EchoMind shows "drive connected successfully" ✅
   - The card now shows "Connected" with a green badge
   - **A connector is automatically created** for you

6. **Repeat for Other Services**
   - Gmail, Calendar, Contacts can be connected the same way
   - Each service requires separate authorization

**Time:** ~30 seconds per service.

---

### Method 2: Via Add Connector Modal

1. **Navigate to Connectors Page**
   - Click **"Workspace" > "Connectors"**

2. **Click "+ Add Connector" Button**
   - Located in the top-right corner

3. **Select Google Service**
   - Choose from:
     - 📁 Google Drive
     - 📧 Gmail
     - 📅 Google Calendar
     - 👤 Google Contacts

4. **Click "Connect to Google" Button**
   - A blue button appears saying "Connect to Google" with Google logo
   - Click it to open the OAuth popup

5. **Authorize in Popup**
   - Same as Method 1 (select account, review permissions, click "Allow")

6. **Fill in Connector Details**
   - After authorization, the button changes to "Connected to Google" ✅
   - **Name:** Give your connector a name (e.g., "My Gmail")
   - **Drive ID:** (Google Drive only) Optional — leave empty for "My Drive"
   - **Visibility Scope:** Choose "Personal" (default)
   - **Sync Interval:** How often to check for new content (default: 60 minutes)

7. **Click "Create"**
   - Your connector is now active and will start syncing

**Time:** ~1-2 minutes per service.

---

## What Permissions Are Requested?

When you authorize EchoMind, you grant **read-only access** to your Google data. EchoMind **cannot** create, modify, or delete your files, emails, or calendar events.

### Google Drive Permissions

**Scopes:**
- `https://www.googleapis.com/auth/drive.readonly` — View files in your Drive
- `https://www.googleapis.com/auth/drive.metadata.readonly` — View file metadata (name, size, modified date)

**What EchoMind Can Do:**
- ✅ Read file contents (PDFs, Docs, Sheets, etc.)
- ✅ View file names, folders, and metadata
- ✅ Access files shared with you

**What EchoMind CANNOT Do:**
- ❌ Create, edit, or delete files
- ❌ Share files or change permissions
- ❌ Access files you don't have permission to view

---

### Gmail Permissions

**Scope:**
- `https://www.googleapis.com/auth/gmail.readonly` — View your email messages and settings

**What EchoMind Can Do:**
- ✅ Read email messages
- ✅ Read email attachments
- ✅ View labels and filters

**What EchoMind CANNOT Do:**
- ❌ Send emails
- ❌ Delete or modify emails
- ❌ Change settings or create filters

---

### Google Calendar Permissions

**Scope:**
- `https://www.googleapis.com/auth/calendar.readonly` — View your calendars

**What EchoMind Can Do:**
- ✅ Read calendar events
- ✅ View event details (title, description, attendees)

**What EchoMind CANNOT Do:**
- ❌ Create, edit, or delete events
- ❌ Invite attendees or send notifications

---

### Google Contacts Permissions

**Scope:**
- `https://www.googleapis.com/auth/contacts.readonly` — View your contacts

**What EchoMind Can Do:**
- ✅ Read contact information (names, emails, phone numbers)

**What EchoMind CANNOT Do:**
- ❌ Add, edit, or delete contacts

---

## Managing Your Connection

### View Connection Status

1. Go to **"Workspace" > "Connectors"**
2. Check the **Google Workspace section** at the top
3. Each service shows:
   - **Connected** (green badge) — You're authorized, connector is active
   - **Click to connect** — Not yet connected

### Disconnect Google Account

**To disconnect ALL Google services at once:**

1. Go to **"Workspace" > "Connectors"**
2. In the Google Workspace section, click **"Disconnect All"** button (top-right)
3. Confirm the action
4. All connectors (Drive, Gmail, Calendar, Contacts) will be removed
5. Your data remains in Google (not deleted)

**To disconnect a single service:**

1. Go to **"Workspace" > "Connectors"**
2. Find the connector in the list (e.g., "Google Drive")
3. Click the **trash icon** (🗑️) on the connector card
4. Confirm deletion

**Note:** You can reconnect anytime by following the [Connecting Google Services](#connecting-google-services) steps again.

---

### Revoke Access via Google

You can also revoke EchoMind's access directly from Google:

1. Go to [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions)
2. Find **"EchoMind"** in the list of apps
3. Click **"Remove Access"**

**Effect:** EchoMind will no longer be able to sync your Google data. You'll need to reconnect via EchoMind UI to restore functionality.

---

## Troubleshooting

### "Popup was blocked by your browser"

**Problem:** The OAuth popup didn't open.

**Solution:**
1. Look for a popup blocker icon in your browser's address bar (usually red or with an "X")
2. Click it and select **"Always allow popups from [your EchoMind domain]"**
3. Try connecting again

**Browsers:**
- **Chrome:** Click the icon at the end of the address bar → "Always allow"
- **Firefox:** Click the "🛡️ Blocked" notification → "Preferences" → Allow
- **Safari:** Safari menu → Preferences → Websites → Pop-up Windows → Allow

---

### "Authorization was cancelled or failed"

**Problem:** OAuth popup closed immediately or you clicked "Cancel."

**Solution:**
- **If you cancelled:** Just try again and click "Allow" this time
- **If it closed immediately:** Check if you have an ad blocker or privacy extension blocking OAuth
  - Try disabling extensions temporarily
  - Or use an incognito/private browsing window

---

### "Google Service Not Available"

**Problem:** You see a red error box saying "Google integration is not configured on this server."

**Solution:**
This means your EchoMind administrator hasn't set up Google OAuth yet. Contact your admin or support team with this message:

> "Please configure Google OAuth by setting `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` in the backend `.env` file. See the [Admin Setup Guide](https://github.com/gen-mind/echo-mind/docs/setup/google-oauth-setup.md) for instructions."

---

### "Authorization failed: Please sign in again"

**Problem:** Your Google session expired or you revoked access.

**Solution:**
1. Go to **"Workspace" > "Connectors"**
2. Click **"Disconnect All"** to clear old credentials
3. Reconnect by clicking the Google service card
4. Authorize again

---

### Connector Shows "Error" Status

**Problem:** Connector status shows red "Error" badge.

**Possible Causes:**
1. **Token expired:** Your Google authorization expired (rare, usually lasts indefinitely)
2. **Password changed:** Changing your Google password invalidates the token
3. **Access revoked:** You revoked EchoMind's access via [Google Permissions](https://myaccount.google.com/permissions)

**Solution:**
1. Disconnect and reconnect the service (see [Disconnect Google Account](#disconnect-google-account))
2. If problem persists, contact support

---

## Privacy & Security

### How is My Data Stored?

- **Google Credentials:** Stored encrypted in EchoMind's database (PostgreSQL)
- **Indexed Content:** Your Drive files, Gmail messages, etc. are indexed and stored in EchoMind's vector database (Qdrant)
- **Who Can See It:** Only you (unless you share via EchoMind's team/org features)

### Can EchoMind Modify My Google Data?

**No.** EchoMind only requests **read-only permissions**. It cannot:
- Send emails
- Delete or modify files
- Create calendar events
- Change your contacts

### What Happens If I Disconnect?

- **Your Google data is NOT deleted** (remains in Google)
- **EchoMind's indexed copy is deleted** (search results for Google data will disappear)
- **You can reconnect anytime** to restore functionality

### How Often Does EchoMind Sync?

- **Default:** Every 60 minutes
- **Configurable:** You can change sync frequency in connector settings (15 min - 1 week)
- **Manual Sync:** Click the sync button (🔄) on any connector card

### Where Can I Learn More?

- **OAuth Flow:** [Google OAuth Architecture](../integrations/google-oauth-architecture.md)
- **Admin Setup:** [Google OAuth Setup Guide](../setup/google-oauth-setup.md)
- **Limitations:** [Google OAuth Limitations (V1)](../setup/google-oauth-limitations.md)

---

## FAQ

### Do I need to connect each Google service separately?

**Yes.** Drive, Gmail, Calendar, and Contacts each require separate authorization. This follows Google's "incremental authorization" best practice — you only grant permissions for services you actually use.

### Can I connect multiple Google accounts?

**No (V1 limitation).** You can only connect one Google account per EchoMind user. If you need to search multiple Google accounts, create separate EchoMind users.

### What if I have a Google Workspace account?

**Works the same way.** Both personal (gmail.com) and Google Workspace accounts are supported.

### How long does authorization last?

**Indefinitely** (until you revoke it or change your Google password). You don't need to re-authorize regularly.

### What happens if Google's servers are down?

**Sync temporarily fails.** EchoMind will automatically retry. Once Google is back up, sync resumes normally. Your previously indexed data remains searchable.

### Can I connect my team's shared Google Drive?

**Partially (V1 limitation).** You can only access files you personally have permission to view. For org-wide Shared Drive access, wait for V2 (Service Account support).

### Does this use my personal Google storage quota?

**No.** EchoMind stores a copy of your content in its own database. Your Google storage usage remains unchanged.

---

## Need Help?

If you encounter issues not covered in this guide:

1. **Check Connector Status:** Go to Connectors page, look for error messages on connector cards
2. **Check Browser Console:** Press `F12` → Console tab → Look for errors (send screenshot to support)
3. **Contact Support:**
   - Email: `support@yourcompany.com`
   - In-app: Click "?" icon → "Contact Support"
   - GitHub: [Report an issue](https://github.com/gen-mind/echo-mind/issues)

---

**Happy Searching!** 🔍

---

**Last Updated:** 2026-02-09
**Document Version:** 1.0
**For:** EchoMind V1
