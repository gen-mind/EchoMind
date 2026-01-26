# EchoMind Web UI

React + TypeScript web application for EchoMind RAG platform.

## Tech Stack

- **React 18** + **TypeScript** + **Vite**
- **TailwindCSS** + **shadcn/ui** - Styling
- **TanStack Query** - Server state management
- **React Router** - Routing
- **oidc-client-ts** - OIDC authentication

## Development Setup

### Prerequisites

- Node.js 18+
- npm or yarn
- Running EchoMind API backend
- Authentik (or compatible OIDC provider)

### 1. Install Dependencies

```bash
cd web
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_OIDC_AUTHORITY` | Yes | Authentik OpenID Provider URL |
| `VITE_OIDC_CLIENT_ID` | Yes | OAuth2 Client ID from Authentik |
| `VITE_OIDC_REDIRECT_URI` | Yes | Callback URL (must match Authentik) |
| `VITE_API_BASE_URL` | No | API base URL (default: `/api/v1`) |
| `VITE_WS_URL` | No | WebSocket URL for chat |

### 3. Authentik Setup

1. Create an **OAuth2/OpenID Provider** in Authentik:
   - Name: `echomind-web`
   - Client Type: `Public`
   - Redirect URIs: `http://localhost:5173/auth/callback`
   - Scopes: `openid`, `profile`, `email`, `offline_access`

2. Create an **Application** linked to the provider

3. Copy the Client ID to your `.env`

### 4. Run Development Server

```bash
npm run dev
```

App runs at http://localhost:5173

The Vite dev server proxies API requests to `http://api.localhost` (configured in `vite.config.ts`).

## Production Build

```bash
npm run build
```

Output is in `dist/` - serve with any static file server.

### Production Environment Variables

For production, set these at build time or in your hosting platform:

```bash
VITE_OIDC_AUTHORITY=https://auth.example.com/application/o/echomind/
VITE_OIDC_CLIENT_ID=your-client-id
VITE_OIDC_REDIRECT_URI=https://app.example.com/auth/callback
VITE_OIDC_POST_LOGOUT_REDIRECT_URI=https://app.example.com/
VITE_API_BASE_URL=https://api.example.com/api/v1
VITE_WS_URL=wss://api.example.com/api/v1/ws/chat
```

## Project Structure

```
src/
├── App.tsx                 # Main app with routing
├── main.tsx                # Entry point
├── auth/                   # OIDC authentication
├── api/                    # API client & endpoints
│   ├── client.ts          # Fetch wrapper with auth
│   ├── ws.ts              # WebSocket for chat
│   └── endpoints/         # Typed API endpoints
├── components/
│   ├── layout/            # Sidebar, MainLayout
│   ├── theme-provider.tsx # Light/dark theme
│   └── ui/                # shadcn/ui components
├── features/              # Feature pages
│   ├── chat/              # Chat with streaming
│   ├── documents/
│   ├── connectors/
│   ├── embedding-models/
│   ├── llms/
│   ├── assistants/
│   ├── users/
│   └── settings/
├── models/                # Auto-generated TypeScript types
└── pages/                 # Login page
```

## TypeScript Models

Models in `src/models/` are auto-generated from protobuf definitions.

**Do not edit manually** - regenerate with:

```bash
cd .. && ./scripts/generate_proto.sh typescript
```

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start dev server |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |
