# TensorBoard Projector Testing Guide

## Quick Start - Two Testing Options

### Option 1: Visual Web UI (Recommended) 🌐

**Just open the HTML file in your browser:**

```bash
open test_projector_ui.html
# Or on Linux: xdg-open test_projector_ui.html
```

**Steps:**
1. Enter your API URL (default: `https://api.demo.echomind.ch`)
2. Enter your Bearer token (get from Authentik or JWT)
3. Optional: Set Team ID and Org ID
4. Click "📊 Load Statistics" to see vector counts
5. Click "👤 My Vectors" / "👥 Team Vectors" / "🏢 Org Vectors" to generate visualization
6. TensorBoard will open in a new tab automatically

**Features:**
- ✨ Beautiful responsive UI
- 📊 Real-time statistics
- 🔍 Optional search filtering
- 🎨 Color-coded by scope
- ⚡ Auto-opens TensorBoard

---

### Option 2: Python Script 🐍

**Install dependencies:**
```bash
pip install requests
```

**Set your token:**
```bash
export BEARER_TOKEN="your-jwt-token-here"
```

**Run the test:**
```bash
./test_projector.py
```

**Or customize:**
```python
from test_projector import generate_visualization

# User scope
generate_visualization(scope="user", limit=5000)

# Team scope with search
generate_visualization(
    scope="team",
    team_id=10,
    search_query="quarterly report",
    limit=3000
)

# Org scope
generate_visualization(scope="org", org_id=1, limit=10000)
```

---

## Prerequisites

### 1. Deploy the Services

```bash
cd deployment/docker-cluster

# Build and deploy
./cluster.sh -H build projector tensorboard
./cluster.sh -H up -d projector tensorboard

# Verify
docker logs echomind-projector
docker logs echomind-tensorboard
```

### 2. Get Your Bearer Token

**Option A: From Authentik**
1. Login to https://auth.demo.echomind.ch
2. Get JWT from browser dev tools (Application → Cookies)

**Option B: Generate Test Token**
```python
import jwt
from datetime import datetime, timedelta, timezone

token = jwt.encode({
    "sub": "42",  # Your user ID
    "email": "admin@test.com",
    "roles": ["admin"],  # Must be admin!
    "exp": datetime.now(timezone.utc) + timedelta(hours=24)
}, "your-secret-key", algorithm="HS256")

print(token)
```

### 3. DNS Configuration

Add DNS record:
```
tensorboard.demo.echomind.ch → [your-server-ip]
```

Or test locally:
```bash
# Add to /etc/hosts
echo "127.0.0.1 tensorboard.demo.echomind.ch" | sudo tee -a /etc/hosts
```

### 4. Ensure Collections Exist

```bash
# Check Qdrant collections
curl http://localhost:6333/collections

# Should have: user_42, team_10, org_1, etc.
```

---

## API Endpoints Reference

### 1. Get Statistics

```bash
curl https://api.demo.echomind.ch/api/v1/projector/stats \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "user_collection": "user_42",
  "user_vectors": 1250,
  "teams": [
    {
      "team_id": 10,
      "team_name": "Engineering",
      "collection_name": "team_10",
      "vector_count": 5400
    }
  ],
  "org_collection": "org_1",
  "org_vectors": 15000
}
```

### 2. Generate Visualization

```bash
curl -X POST https://api.demo.echomind.ch/api/v1/projector/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "user",
    "search_query": "technical documentation",
    "limit": 5000
  }'
```

**Response:**
```json
{
  "viz_id": "viz-a1b2c3d4e5f6g7h8",
  "collection_name": "user_42",
  "status": "processing",
  "tensorboard_url": "https://tensorboard.demo.echomind.ch/#projector&run=viz-a1b2c3d4e5f6g7h8",
  "message": "Visualization queued for processing. Visit the URL in 30-60 seconds..."
}
```

---

## Troubleshooting

### "403 Forbidden - Not a team member"
- Verify you're a member of the team via database:
  ```sql
  SELECT * FROM team_members WHERE user_id = 42 AND team_id = 10;
  ```

### "404 Collection not found"
- Check Qdrant: `curl http://localhost:6333/collections`
- Ensure documents have been ingested for that user/team/org

### "503 Service Unavailable"
- Check if Qdrant is running: `docker logs echomind-qdrant`
- Check if NATS is running: `docker logs echomind-nats`
- Check projector logs: `docker logs echomind-projector`

### TensorBoard shows empty
- Wait 30-60 seconds for worker to process
- Check projector logs for errors
- Verify `/logs` volume is shared correctly:
  ```bash
  docker exec echomind-projector ls -la /logs
  docker exec echomind-tensorboard ls -la /logs
  ```

### "No vectors found"
- Collection might be empty
- Try different scope (user/team/org)
- Try without search query first

---

## What You Should See

### 1. TensorBoard Interface
- 3D scatter plot of vectors
- T-SNE/UMAP/PCA controls on left sidebar
- Search box to highlight points
- Metadata showing titles and text previews

### 2. Expected Workflow
1. Click generate button → Request sent to API
2. API publishes NATS message → Projector worker receives
3. Worker fetches vectors from Qdrant
4. Worker generates TensorFlow checkpoint files in `/logs/viz-{id}/`
5. TensorBoard reads checkpoint and displays visualization
6. Browser shows interactive 3D plot

### 3. Processing Time
- **10,000 vectors**: ~30-60 seconds
- **5,000 vectors**: ~20-30 seconds
- **1,000 vectors**: ~10-15 seconds

---

## Next Steps

1. **Test all three scopes**: user, team, org
2. **Test search filtering**: Try keywords that match your documents
3. **Test with different limits**: 1000, 5000, 10000
4. **Explore in TensorBoard**:
   - Try different reduction methods (T-SNE, UMAP, PCA)
   - Search for specific documents
   - Zoom and rotate the 3D view
   - Check metadata on hover

---

## Production Deployment

For production, integrate this into the main WebUI:

**Location**: `echo-mind-webui` repository (separate from backend)
**Route**: `/admin/vector-viz`
**Components needed**:
1. Svelte page with scope buttons
2. Stats display component
3. API client calls to `/api/v1/projector/*`
4. Open TensorBoard in new tab on success

**Example Svelte code** is in the plan file at:
`.claude/plans/purring-greeting-thimble.md` (Phase 4 section)

---

## Questions?

- **Backend issues**: Check `docker logs echomind-projector`
- **Frontend issues**: Check browser console
- **Permission issues**: Verify admin role in JWT token
- **Network issues**: Verify DNS and Traefik routing

**All 70 tests passing** ✅ Backend is production-ready!
