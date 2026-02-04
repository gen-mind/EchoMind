# EchoMind WebUI Implementation Plan

## Executive Summary

All API clients are **fully implemented** - the backend supports all required operations. The gap is in the **frontend UI**: create/edit modals are missing across all pages. Buttons exist but clicking them does nothing because the modal components aren't rendered.

---

## Current State Matrix

| Component | List | View | Create | Edit | Delete | Special |
|-----------|:----:|:----:|:------:|:----:|:------:|:-------:|
| Documents | OK | - | MISSING | - | OK | Search OK |
| Connectors | OK | - | SHELL | SHELL | OK | Sync OK |
| Teams | OK | Members OK | SHELL | SHELL | OK | - |
| Assistants | OK | - | SHELL | SHELL | OK | - |
| LLMs | OK | - | SHELL | - | OK | Test OK |
| EmbeddingModels | OK | - | SHELL | - | - | Activate OK |

**Legend:**
- OK = Fully working
- SHELL = Button exists, modal missing
- MISSING = No UI at all
- `-` = Not applicable or not needed

---

## Page-by-Page Implementation Plans

---

## 1. Documents Page (`/workspace/documents`)

### Current State
- List with pagination and status filtering
- Semantic search functionality
- Delete with confirmation
- **Missing**: Upload functionality

### API Endpoints Available
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/documents` | Used |
| GET | `/api/v1/documents/{id}` | Not used |
| DELETE | `/api/v1/documents/{id}` | Used |
| GET | `/api/v1/documents/search` | Used |
| POST | `/api/v1/documents/upload/initiate` | Not used |
| POST | `/api/v1/documents/upload/complete` | Not used |
| POST | `/api/v1/documents/upload/abort` | Not used |

### Implementation Tasks

#### Task 1.1: Fix Status Filter Dropdown
**File**: `src/lib/components/workspace/Documents.svelte`
**Lines**: 166-169
**Issue**: Dropdown values don't match API enum format
**Change**:
```svelte
<!-- Current (broken) -->
<option value="pending">Pending</option>
<option value="processing">Processing</option>

<!-- Fixed -->
<option value="DOCUMENT_STATUS_PENDING">Pending</option>
<option value="DOCUMENT_STATUS_PROCESSING">Processing</option>
<option value="DOCUMENT_STATUS_COMPLETED">Completed</option>
<option value="DOCUMENT_STATUS_FAILED">Failed</option>
```

#### Task 1.2: Add Document Upload Modal
**New Component**: `src/lib/components/workspace/DocumentUploadModal.svelte`
**Requirements**:
- Drag-and-drop file zone
- File type validation (PDF, DOC, DOCX, TXT, MD, etc.)
- File size display
- Upload progress indicator
- Three-step upload flow:
  1. Call `initiateUpload()` to get pre-signed URL
  2. Upload file directly to MinIO using pre-signed URL
  3. Call `completeUpload()` to trigger ingestion

**API Client Functions to Use**:
```typescript
// From src/lib/apis/echomind/upload.ts (needs to be created)
initiateUpload(filename, contentType, size) → { documentId, uploadUrl, expiresIn }
completeUpload(documentId) → Document
abortUpload(documentId) → { success }
```

#### Task 1.3: Add Document Details Modal
**New Component**: `src/lib/components/workspace/DocumentDetailsModal.svelte`
**Requirements**:
- Show full document metadata
- Display chunk count and content type
- Show ingestion status with error message if failed
- Re-ingest button for failed documents
- Link to source URL if available

#### Task 1.4: Upload API Client
**File**: `src/lib/apis/echomind/upload.ts` (ALREADY EXISTS)
**Functions available**:
- `initiateUpload()` - Get pre-signed URL
- `uploadFileToPresignedUrl()` - Upload to MinIO with progress
- `completeUpload()` - Trigger document processing
- `abortUpload()` - Cancel upload
- `uploadDocument()` - Complete flow helper

**No changes needed** - just import and use in modal.

### Estimated Complexity: Medium
- 1 new API client file
- 2 new modal components
- 1 fix to existing component

---

## 2. Connectors Page (`/workspace/connectors`)

### Current State
- List with sync status and metadata
- Trigger sync functionality
- Delete with confirmation
- **Missing**: Create and Edit modals

### API Endpoints Available
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/connectors` | Used |
| GET | `/api/v1/connectors/{id}` | Not used |
| POST | `/api/v1/connectors` | API ready, UI missing |
| PUT | `/api/v1/connectors/{id}` | API ready, UI missing |
| DELETE | `/api/v1/connectors/{id}` | Used |
| POST | `/api/v1/connectors/{id}/sync` | Used |
| GET | `/api/v1/connectors/{id}/status` | Not used |

### Implementation Tasks

#### Task 2.1: Create Connector Modal
**New Component**: `src/lib/components/workspace/ConnectorCreateModal.svelte`
**Requirements**:
- Multi-step form wizard:
  1. Select connector type (Teams, Drive, OneDrive, Web, File)
  2. Configure type-specific settings
  3. Set sync frequency
  4. Set scope (User, Team, Org)
- Type-specific configuration forms:

**Teams Connector Config**:
```typescript
{
  tenant_id: string;
  client_id: string;
  client_secret: string;
  team_ids?: string[];  // Optional: specific teams
}
```

**Google Drive Config**:
```typescript
{
  credentials_json: string;  // Service account JSON
  folder_ids?: string[];
  include_shared?: boolean;
}
```

**OneDrive Config**:
```typescript
{
  tenant_id: string;
  client_id: string;
  client_secret: string;
  drive_ids?: string[];
}
```

**Web Connector Config**:
```typescript
{
  urls: string[];
  depth?: number;  // Crawl depth
  include_patterns?: string[];
  exclude_patterns?: string[];
}
```

**File Connector Config**:
```typescript
{
  // No config needed - files are manually uploaded
}
```

#### Task 2.2: Edit Connector Modal
**New Component**: `src/lib/components/workspace/ConnectorEditModal.svelte`
**Requirements**:
- Pre-populate form with existing connector data
- Allow editing name, config, sync frequency
- Cannot change connector type (create new instead)
- Show current sync status

#### Task 2.3: Add Edit Button Handler
**File**: `src/lib/components/workspace/Connectors.svelte`
**Change**: Add click handler to edit button
```svelte
<button on:click={() => openEditModal(connector)}>
  Edit
</button>
```

#### Task 2.4: Wire Up Create Modal
**File**: `src/lib/components/workspace/Connectors.svelte`
**Change**: Add modal rendering
```svelte
{#if showCreateModal}
  <ConnectorCreateModal
    on:close={() => showCreateModal = false}
    on:created={handleConnectorCreated}
  />
{/if}
```

### Estimated Complexity: High
- 2 new modal components with complex forms
- Type-specific configuration UI
- Multi-step wizard pattern

---

## 3. Teams Page (`/admin/teams`)

### Current State
- List teams with member count
- View team members in modal
- Delete with confirmation
- **Missing**: Create and Edit modals, Member management UI

### API Endpoints Available
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/teams` | Used |
| GET | `/api/v1/teams/me` | Not used |
| GET | `/api/v1/teams/{id}` | Used (for members) |
| POST | `/api/v1/teams` | API ready, UI missing |
| PUT | `/api/v1/teams/{id}` | API ready, UI missing |
| DELETE | `/api/v1/teams/{id}` | Used |
| POST | `/api/v1/teams/{id}/members` | API ready, UI missing |
| DELETE | `/api/v1/teams/{id}/members/{userId}` | API ready, UI missing |
| PUT | `/api/v1/teams/{id}/members/{userId}/role` | API ready, UI missing |

### Implementation Tasks

#### Task 3.1: Create Team Modal
**New Component**: `src/lib/components/admin/TeamCreateModal.svelte`
**Requirements**:
- Form fields:
  - Name (required, text)
  - Description (optional, textarea)
  - Leader (optional, user dropdown)
- User search/select for leader field
- Validation: name required, max length

#### Task 3.2: Edit Team Modal
**New Component**: `src/lib/components/admin/TeamEditModal.svelte`
**Requirements**:
- Pre-populate with existing team data
- Same fields as create
- Show creation date (read-only)

#### Task 3.3: Enhanced Members Modal
**File**: `src/lib/components/admin/Teams.svelte`
**Enhancements to existing members modal**:
- Add "Add Member" button
- User search to add new members
- Role dropdown (Member/Lead) for each member
- Remove member button with confirmation
- Inline role editing

#### Task 3.4: Users API Client (for dropdowns)
**File**: `src/lib/apis/echomind/users.ts` (ALREADY EXISTS)
**Functions available**:
- `getUsers()` - List users with pagination
- `getUserById()` - Get single user
- `getCurrentUser()` - Get logged-in user
- `updateCurrentUser()` - Update current user

**No changes needed** - just import and use in team member dropdowns.

#### Task 3.5: Wire Up Modals
**File**: `src/lib/components/admin/Teams.svelte`
**Changes**:
- Add edit button click handler
- Render create modal
- Render edit modal

### Estimated Complexity: Medium-High
- 2 new modal components
- User search/select component needed
- Member management in existing modal

---

## 4. Assistants Page (`/admin/assistants`)

### Current State
- List assistants with metadata
- Delete with confirmation
- **Missing**: Create and Edit modals

### API Endpoints Available
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/assistants` | Used |
| GET | `/api/v1/assistants/{id}` | Not used |
| POST | `/api/v1/assistants` | API ready, UI missing |
| PUT | `/api/v1/assistants/{id}` | API ready, UI missing |
| DELETE | `/api/v1/assistants/{id}` | Used |

### Implementation Tasks

#### Task 4.1: Create Assistant Modal
**New Component**: `src/lib/components/admin/AssistantCreateModal.svelte`
**Requirements**:
- Form fields:
  - Name (required, text)
  - Description (optional, textarea)
  - LLM (required, dropdown from LLMs API)
  - System Prompt (required, large textarea with markdown preview)
  - Task Prompt (optional, textarea)
  - Starter Messages (optional, list with add/remove)
  - Is Default (checkbox)
  - Is Visible (checkbox)
  - Display Priority (number)
- LLM dropdown populated from `/api/v1/llms`
- System prompt template suggestions

#### Task 4.2: Edit Assistant Modal
**New Component**: `src/lib/components/admin/AssistantEditModal.svelte`
**Requirements**:
- Pre-populate with existing assistant data
- Same fields as create
- Show current usage stats if available

#### Task 4.3: Starter Messages Editor
**Sub-component**: Reusable list editor for starter messages
- Add new message button
- Remove message button
- Reorder messages (drag or up/down buttons)

#### Task 4.4: Wire Up Modals
**File**: `src/lib/components/admin/Assistants.svelte`
**Changes**:
- Add edit button click handler (line 145)
- Render create modal
- Render edit modal

### Estimated Complexity: Medium
- 2 new modal components
- LLM dropdown integration
- Starter messages list editor

---

## 5. LLMs Page (`/admin/llms`)

### Current State
- List LLMs with provider info
- Test connection with latency
- Delete with confirmation
- **Missing**: Create and Edit modals

### API Endpoints Available
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/llms` | Used |
| GET | `/api/v1/llms/{id}` | Not used |
| POST | `/api/v1/llms` | API ready, UI missing |
| PUT | `/api/v1/llms/{id}` | API ready, UI missing |
| DELETE | `/api/v1/llms/{id}` | Used |
| POST | `/api/v1/llms/{id}/test` | Used |

### Implementation Tasks

#### Task 5.1: Create LLM Modal
**New Component**: `src/lib/components/admin/LLMCreateModal.svelte`
**Requirements**:
- Form fields:
  - Name (required, text)
  - Provider (required, dropdown: OPENAI_COMPATIBLE, ANTHROPIC, ANTHROPIC_TOKEN)
  - Model ID (required, text - e.g., "gpt-4", "claude-3-opus")
  - Endpoint (conditional, URL - required for OPENAI_COMPATIBLE)
  - API Key (required, password field)
  - Max Tokens (optional, number)
  - Temperature (optional, slider 0-2)
  - Is Default (checkbox)
  - Is Active (checkbox)
- Provider-specific field visibility:
  - OPENAI_COMPATIBLE: Show endpoint field
  - ANTHROPIC/ANTHROPIC_TOKEN: Hide endpoint (uses Anthropic API)
- Test connection button before save

#### Task 5.2: Edit LLM Modal
**New Component**: `src/lib/components/admin/LLMEditModal.svelte`
**Requirements**:
- Pre-populate with existing LLM data
- API key shows as "••••••••" with option to change
- Same fields as create
- Test connection button

#### Task 5.3: Add Edit Button
**File**: `src/lib/components/admin/LLMs.svelte`
**Change**: Add edit button to each LLM card
```svelte
<button on:click={() => openEditModal(llm)}>
  <Pencil class="w-4 h-4" />
</button>
```

#### Task 5.4: Wire Up Modals
**File**: `src/lib/components/admin/LLMs.svelte`
**Changes**:
- Add showEditModal state
- Render create modal
- Render edit modal

### Estimated Complexity: Medium
- 2 new modal components
- Provider-specific conditional fields
- Test connection integration

---

## 6. Embedding Models Page (`/admin/embedding-models`)

### Current State
- List embedding models
- Activate model with reindex warning
- **Missing**: Create modal, Delete functionality

### API Endpoints Available
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/embedding-models` | Used |
| GET | `/api/v1/embedding-models/active` | Not used |
| POST | `/api/v1/embedding-models` | API ready, UI missing |
| PUT | `/api/v1/embedding-models/{id}/activate` | Used |

### Implementation Tasks

#### Task 6.1: Create Embedding Model Modal
**New Component**: `src/lib/components/admin/EmbeddingModelCreateModal.svelte`
**Requirements**:
- Form fields:
  - Model Name (required, text - display name)
  - Model ID (required, text - e.g., "sentence-transformers/all-MiniLM-L6-v2")
  - Model Dimension (required, number - e.g., 384, 768, 1536)
  - Endpoint (optional, URL - for remote embedding service)
- Common model presets:
  - all-MiniLM-L6-v2 (384 dimensions)
  - all-mpnet-base-v2 (768 dimensions)
  - text-embedding-ada-002 (1536 dimensions)
- Dimension auto-fill when selecting preset

#### Task 6.2: Add Delete Functionality
**File**: `src/lib/components/admin/EmbeddingModels.svelte`
**Changes**:
- Add delete button (with warning: cannot delete active model)
- Add deleteEmbeddingModel API call
- Note: API may need DELETE endpoint added

#### Task 6.3: Wire Up Create Modal
**File**: `src/lib/components/admin/EmbeddingModels.svelte`
**Changes**:
- Render create modal when showCreateModal is true

### Estimated Complexity: Low-Medium
- 1 new modal component
- Model presets helper
- Delete functionality (may need backend)

---

## Shared Components & Patterns

### Modal Pattern (from Open WebUI)
**File**: `src/lib/components/common/Modal.svelte`
**Already exists** - reuse this exact pattern:

```svelte
<script lang="ts">
  import { getContext, createEventDispatcher } from 'svelte';
  import { toast } from 'svelte-sonner';
  import Modal from '$lib/components/common/Modal.svelte';

  const i18n = getContext('i18n');
  const dispatch = createEventDispatcher();

  export let show = false;

  let name = '';
  let loading = false;
</script>

<Modal size="md" bind:show>
  <div class="p-6">
    <!-- Header with close button -->
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-medium">{$i18n.t('Create Item')}</h3>
      <button on:click={() => show = false}>
        <XMark />
      </button>
    </div>

    <!-- Form -->
    <form on:submit|preventDefault={handleSubmit}>
      <div class="space-y-4">
        <input bind:value={name} required />
      </div>

      <!-- Footer buttons -->
      <div class="flex justify-end gap-2 mt-6">
        <button type="button" on:click={() => show = false}>
          {$i18n.t('Cancel')}
        </button>
        <button type="submit" disabled={loading}>
          {loading ? $i18n.t('Saving...') : $i18n.t('Save')}
        </button>
      </div>
    </form>
  </div>
</Modal>
```

### Form Input Components
**Reuse from Open WebUI**:
- Text input (native HTML)
- Textarea (native HTML)
- Select/dropdown (native HTML)
- Checkbox (native HTML)
- Number input (native HTML)
- Password input (native HTML)
- RichTextInput (for large text areas)

### User Search/Select Component
**New Component**: `src/lib/components/common/UserSelect.svelte`
**Requirements**:
- Search users by name/email
- Single or multi-select mode
- Show user avatar and name
- Used by: Teams (leader, members)

### Confirmation Dialog
**Already exists** - reuse from delete functionality

### Toast Notifications
```typescript
import { toast } from 'svelte-sonner';
toast.success($i18n.t('Created successfully'));
toast.error($i18n.t('Failed to create'));
```

---

## Implementation Priority

### Phase 1: Critical Path (High Impact)
1. **LLMs Create/Edit** - Required to configure AI models
2. **Assistants Create/Edit** - Required to create AI personalities
3. **Teams Create/Edit + Members** - Required for team-based access

### Phase 2: User Features
4. **Documents Upload** - Core user feature
5. **Connectors Create/Edit** - Data source configuration

### Phase 3: Polish
6. **Embedding Models Create** - Admin configuration
7. **Documents Details Modal** - Enhanced UX
8. **Status filter fix** - Bug fix

---

## File Summary

### New Files to Create
| File | Type | Priority |
|------|------|----------|
| `src/lib/components/workspace/DocumentUploadModal.svelte` | Component | P2 |
| `src/lib/components/workspace/DocumentDetailsModal.svelte` | Component | P3 |
| `src/lib/components/workspace/ConnectorCreateModal.svelte` | Component | P2 |
| `src/lib/components/workspace/ConnectorEditModal.svelte` | Component | P2 |
| `src/lib/components/admin/TeamCreateModal.svelte` | Component | P1 |
| `src/lib/components/admin/TeamEditModal.svelte` | Component | P1 |
| `src/lib/components/admin/AssistantCreateModal.svelte` | Component | P1 |
| `src/lib/components/admin/AssistantEditModal.svelte` | Component | P1 |
| `src/lib/components/admin/LLMCreateModal.svelte` | Component | P1 |
| `src/lib/components/admin/LLMEditModal.svelte` | Component | P1 |
| `src/lib/components/admin/EmbeddingModelCreateModal.svelte` | Component | P3 |
| `src/lib/components/common/UserSelect.svelte` | Component | P1 |

### Files to Modify
| File | Changes | Priority |
|------|---------|----------|
| `Documents.svelte` | Fix status filter, add upload button, wire modals | P2-P3 |
| `Connectors.svelte` | Add edit handler, wire modals | P2 |
| `Teams.svelte` | Add edit handler, wire modals, enhance members modal | P1 |
| `Assistants.svelte` | Add edit handler, wire modals | P1 |
| `LLMs.svelte` | Add edit button, wire modals | P1 |
| `EmbeddingModels.svelte` | Wire create modal, add delete | P3 |

---

## API Gaps Identified

1. **Embedding Models**: No DELETE endpoint in API
2. **Documents**: No UPDATE endpoint (intentional - re-ingest instead)
3. **Users List**: Need to verify `/api/v1/users` endpoint exists for user dropdowns

---

## Testing Checklist

For each modal implementation:
- [ ] Form validation works
- [ ] API errors display properly
- [ ] Success refreshes list
- [ ] Cancel closes without side effects
- [ ] Loading states during API calls
- [ ] Keyboard navigation (Escape to close)
- [ ] Mobile responsive layout
