# EchoMind WebUI Navigation Guide

This document describes where to find EchoMind-specific pages in the WebUI (Open WebUI fork).

## Overview

EchoMind extends Open WebUI with custom pages for managing documents, connectors, teams, assistants, and AI models. These pages are organized into two main areas:

1. **Workspace** - User-facing features for document and connector management
2. **Admin Panel** - Administrative features for system configuration

## Workspace Pages

Accessible to all authenticated users via the sidebar.

| Page | URL | Description |
|------|-----|-------------|
| **Documents** | `/workspace/documents` | View, upload, and manage ingested documents |
| **Connectors** | `/workspace/connectors` | Configure and monitor data source connectors |

### How to Access

1. Log in to EchoMind WebUI
2. Click **Workspace** in the left sidebar
3. Select the **Documents** or **Connectors** tab

## Admin Panel Pages

Accessible only to users with `admin` role.

| Page | URL | Description |
|------|-----|-------------|
| **Users** | `/admin` | Manage user accounts and roles |
| **Teams** | `/admin/teams` | Create and manage teams with shared resources |
| **Assistants** | `/admin/assistants` | Configure AI assistants with custom prompts |
| **LLMs** | `/admin/llms` | Manage LLM providers and models |
| **Embedding Models** | `/admin/embedding-models` | Configure embedding models for vector search |
| **Evaluations** | `/admin/evaluations` | Review and evaluate chat sessions |
| **Functions** | `/admin/functions` | Manage custom functions and tools |
| **Settings** | `/admin/settings` | System-wide configuration |

### How to Access

1. Log in to EchoMind WebUI as an admin user
2. Click the **Admin Panel** option (gear icon or user menu)
3. Use the tab navigation at the top to switch between sections

## Page Functionality

### Documents (`/workspace/documents`)

- **List View**: Shows all documents with status, size, and ingestion date
- **Upload**: Drag-and-drop or click to upload new documents
- **Actions**: View details, re-ingest, or delete documents
- **Filters**: Filter by status (pending, processing, completed, failed)

### Connectors (`/workspace/connectors`)

- **List View**: Shows configured connectors with sync status
- **Add Connector**: Configure new data sources (Teams, Drive, SharePoint, etc.)
- **Sync Controls**: Trigger manual sync or view sync history
- **Status Monitoring**: View last sync time and error messages

### Teams (`/admin/teams`)

- **Team Management**: Create, edit, and delete teams
- **Member Assignment**: Add/remove users from teams
- **Resource Sharing**: Configure shared assistants and documents per team

### Assistants (`/admin/assistants`)

- **Assistant Configuration**: Create AI personalities with custom system prompts
- **LLM Assignment**: Link assistants to specific LLM models
- **Team Assignment**: Make assistants available to specific teams

### LLMs (`/admin/llms`)

- **Provider Management**: Configure LLM providers (OpenAI, Anthropic, local models)
- **Model Registration**: Add available models with their capabilities
- **Usage Tracking**: Monitor token usage and costs

### Embedding Models (`/admin/embedding-models`)

- **Model Configuration**: Set up embedding models for vector search
- **Dimension Settings**: Configure embedding dimensions per model
- **Default Selection**: Set the default model for new documents

## Technical Details

### File Locations (for developers)

```
echomind-webui/src/
├── lib/
│   ├── apis/echomind/           # API client modules
│   │   ├── documents.ts
│   │   ├── connectors.ts
│   │   ├── teams.ts
│   │   ├── assistants.ts
│   │   ├── llms.ts
│   │   └── embedding-models.ts
│   └── components/
│       ├── workspace/
│       │   ├── Documents.svelte
│       │   └── Connectors.svelte
│       └── admin/
│           ├── Teams.svelte
│           ├── Assistants.svelte
│           ├── LLMs.svelte
│           └── EmbeddingModels.svelte
└── routes/(app)/
    ├── workspace/
    │   ├── +layout.svelte       # Workspace tabs
    │   ├── documents/+page.svelte
    │   └── connectors/+page.svelte
    └── admin/
        ├── +layout.svelte       # Admin tabs
        ├── teams/+page.svelte
        ├── assistants/+page.svelte
        ├── llms/+page.svelte
        └── embedding-models/+page.svelte
```

### Branch Information

Custom EchoMind pages are on the `echomind-customizations` branch:

```bash
# Ensure you're on the correct branch
git checkout echomind-customizations

# Rebuild after switching branches
./cluster.sh rebuild webui        # local
./cluster.sh -H rebuild webui     # production
```
