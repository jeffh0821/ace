# ACE Frontend

React SPA for the ACE (Assistant for Connector Engineering) application.

## Stack
- React 18, Vite, TailwindCSS
- Axios (API client with cookie auth)
- React Router (client-side routing with role-based guards)
- Lucide React (icons)

## Development

```bash
npm install
npm run dev
```

Dev server runs at http://localhost:5173 and proxies `/api/*` to `http://localhost:8000`.

## Build

```bash
npm run build
```

Output goes to `dist/` — served by nginx in production (see Dockerfile).

## Pages

| Page | Route | Role | Description |
|------|-------|------|-------------|
| Login | `/login` | Public | Username/password auth |
| Ask | `/` | Any | Chat-style Q&A interface |
| History | `/history` | Any | Question history with expandable details |
| Escalations | `/escalations` | Engineer, Admin | View/respond to escalated questions |
| Documents | `/documents` | Engineer, Admin | Upload PDFs, view processing status |
| Users | `/users` | Admin | Create/manage user accounts |
| Analytics | `/analytics` | Admin | Metrics dashboard |
| Settings | `/settings` | Admin | Runtime config (model, threshold, top-K) |

See the main [README](../README.md) for full documentation.
