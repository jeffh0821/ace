# ACE — Assistant for Connector Engineering

A RAG-powered Q&A web application for PEI-Genesis. Sales teams ask natural-language questions about electrical connectors and the system retrieves answers from ingested technical PDF documents, citing sources with confidence scoring. Low-confidence answers are automatically escalated to engineers for human review.

## Features

- **PDF Ingestion** — Upload technical PDFs; text is extracted (with OCR for scanned documents), chunked, embedded, and stored in a vector database
- **Q&A with Citations** — Ask questions in a chat interface; get answers backed by specific document excerpts and page numbers
- **Confidence Scoring** — Combined retrieval + LLM confidence determines answer quality; below-threshold answers trigger escalation
- **Escalation Workflow** — Engineers review low-confidence questions, provide answers, and those answers feed back into the knowledgebase
- **Role-Based Access** — Three roles (Sales, Engineer, Admin) with granular permissions
- **Admin Dashboard** — Analytics, user management, document management, runtime configuration
- **Feedback Loop** — Thumbs up/down on answers, tracked for continuous improvement
- **Self-Hosted** — Everything runs on a single Linux server via Docker Compose; only external dependency is OpenRouter for LLM inference

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────────┐
│   Browser    │────▶│  Nginx (frontend container, port 80)             │
│  React SPA   │     │  Serves static React build + proxies /api/       │
└─────────────┘     └────────────────────┬─────────────────────────────┘
                                         │ /api/*
                                         ▼
                    ┌──────────────────────────────────────────────────┐
                    │  FastAPI Backend (port 8000)                      │
                    │                                                  │
                    │  ┌─────────┐  ┌──────────┐  ┌────────────────┐  │
                    │  │ Auth    │  │ Document  │  │ Q&A Pipeline   │  │
                    │  │ (JWT)   │  │ Ingestion │  │ retrieve→LLM   │  │
                    │  └─────────┘  └──────────┘  └────────────────┘  │
                    │                                                  │
                    │  ┌──────────────────┐  ┌──────────────────────┐  │
                    │  │ sentence-        │  │ OpenRouter API       │  │
                    │  │ transformers     │  │ (LLM inference)      │  │
                    │  │ (embeddings)    │  │                      │  │
                    │  └──────────────────┘  └──────────────────────┘  │
                    │  ┌─────────────────────────────────────────┐  │
                    │  │ Hybrid Retrieval: ChromaDB (vector) +     │  │
                    │  │ BM25 (keyword) + Reciprocal Rank Fusion   │  │
                    │  └─────────────────────────────────────────┘  │
                    └───────┬──────────────────────┬───────────────────┘
                            │                      │
                    ┌───────▼──────┐       ┌───────▼──────┐
                    │   SQLite     │       │   ChromaDB   │
                    │  (users,     │       │  (vectors,   │
                    │   questions, │       │   document   │
                    │   etc.)     │       │   chunks)    │
                    └──────────────┘       └──────────────┘
```

### Data Flows

**Document Ingestion:**
Upload PDF → Extract text (PyMuPDF + Tesseract OCR fallback) → Hybrid chunking (structure-aware + token-size) → Embed via sentence-transformers (all-MiniLM-L6-v2) → Store in ChromaDB

**Question Answering:**
User question → Embed query → Simultaneously retrieve top-K chunks from ChromaDB (vector) and BM25 (keyword) → Fuse results with Reciprocal Rank Fusion → Send top chunks to LLM via OpenRouter → LLM returns structured JSON (answer + confidence + citations) → Compute combined score (retrieval_weight × retrieval + llm_weight × LLM) → If ≥ threshold: show answer; if < threshold but top chunk has strong BM25 match (rank=1, score ≥ 2.0): show answer (bypass escalation); else: escalate to engineer

**Escalation Resolution:**
Engineer views escalated question + retrieved context → Writes response → Response shown to sales user on next visit → Q&A pair embedded and stored in Chroma (improving future answers)

---

## Prerequisites

### Docker Deployment (Recommended)
- Docker Engine 20+
- Docker Compose v2+
- An [OpenRouter](https://openrouter.ai) API key

### Local Development
- Python 3.11+
- Node.js 20+
- Tesseract OCR (`apt-get install tesseract-ocr tesseract-ocr-eng`)
- An [OpenRouter](https://openrouter.ai) API key

---

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone git@github.com:jeffh0821/ace.git
cd ace

# 2. Configure environment
cp .env.example .env
# Edit .env — set your OpenRouter API key and a strong secret:
#   OPENROUTER_API_KEY=sk-or-v1-...
#   APP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 3. Build and start
docker-compose up --build -d

# 4. Open the app
# Frontend: http://localhost
# API:      http://localhost:8000/health

# 5. Login with default admin account
# Username: admin
# Password: changeme
# ⚠️  CHANGE THIS PASSWORD — create a new admin user and deactivate the default one
```

### Data Persistence

Docker Compose mounts these volumes to `./data/`:
- `./data/uploads/` — Original uploaded PDF files
- `./data/chroma/` — ChromaDB vector index
- `./data/db/` — SQLite database file

Back up `./data/` regularly in production.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | **Yes** | — | API key from [OpenRouter](https://openrouter.ai/keys) |
| `APP_SECRET_KEY` | Recommended | `change-me-in-production` | Secret for JWT signing. Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ACE_DATABASE_URL` | No | `sqlite+aiosqlite:///./ace.db` | SQLAlchemy async database URL |
| `ACE_SECRET_KEY` | No | from config.yaml | Alternative to APP_SECRET_KEY |

Any `Settings` field can be overridden with the `ACE_` prefix (e.g., `ACE_LLM_MODEL=claude-3-haiku`).

---

## Configuration (config.yaml)

The backend reads `backend/config.yaml` at startup. Environment variables take precedence.

```yaml
llm:
  provider: openrouter           # LLM provider (only openrouter supported)
  model: gpt-4o-mini             # OpenRouter model ID (changeable at runtime via admin UI)
  embedding_model: all-MiniLM-L6-v2  # sentence-transformers model (requires restart to change)
  api_key: ${OPENROUTER_API_KEY}     # Resolved from env var

confidence:
  threshold: 0.60                # Below this → escalate (0.0–1.0, changeable at runtime). BM25 keyword match bypasses escalation regardless of this threshold.
  retrieval_weight: 0.5          # Weight for retrieval similarity in combined score
  llm_weight: 0.5                # Weight for LLM self-reported confidence

retrieval:
  top_k: 5                       # Number of chunks retrieved per query (changeable at runtime)

database:
  chroma_persist_dir: ./chroma_data  # ChromaDB storage path

app:
  host: 0.0.0.0
  port: 8000
  secret_key: ${APP_SECRET_KEY}
```

**Runtime-changeable settings** (via admin Settings page, no restart needed):
- `llm.model` — Switch LLM models instantly
- `confidence.threshold` — Adjust escalation sensitivity
- `retrieval.top_k` — Change how many chunks are retrieved

---

## Local Development

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ensure Tesseract is installed (for OCR)
# Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-eng
# macOS: brew install tesseract

# Set required environment variable
export OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Start the server (with hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On first startup:
- SQLite database is created automatically
- Default admin user is seeded (admin / changeme)
- First question will trigger download of the sentence-transformers model (~90MB)

API docs (Swagger): http://localhost:8000/docs

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api to backend on port 8000)
npm run dev
```

Frontend dev server: http://localhost:5173

The Vite dev server proxies all `/api/*` requests to `http://localhost:8000` automatically.

### Running Both Together (Local)

Terminal 1:
```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

Terminal 2:
```bash
cd frontend && npm run dev
```

Open http://localhost:5173

---

## User Guide

### Roles and Permissions

| Capability | Sales | Engineer | Admin |
|------------|-------|----------|-------|
| Ask questions | ✓ | ✓ | ✓ |
| View own answer history | ✓ | ✓ | ✓ |
| Give feedback (thumbs up/down) | ✓ | ✓ | ✓ |
| View/respond to escalations | — | ✓ | ✓ |
| Upload/manage documents | — | ✓ | ✓ |
| Create/manage users | — | — | ✓ |
| View analytics | — | — | ✓ |
| Change settings | — | — | ✓ |

### First-Time Setup

1. **Login** as `admin` / `P3iG3n3s1s!` (change this immediately after first login)
2. **Create users** — Go to Users → Add User for each sales rep and engineer
3. **Upload documents** — Go to Documents → Upload PDF. Wait for status to show "completed"
4. **Configure** — Go to Settings to adjust the LLM model, confidence threshold, or retrieval depth
5. **Test** — Go to Ask and try a question related to your uploaded documents

### Asking Questions (Sales)

1. Navigate to the **Ask** page
2. Type your question in natural language (e.g., "What MIL-spec connectors are rated for 200°C?")
3. The system will:
   - Search the knowledgebase for relevant document chunks
   - Generate an answer with citations (document title + page number + excerpt)
   - Display the answer if confidence is above the threshold
   - Show "Question Escalated" if confidence is too low
4. Give thumbs up/down feedback on the answer quality
5. View past questions on the **History** page

### Handling Escalations (Engineers)

1. Navigate to the **Escalations** page
2. Filter by Pending / Resolved / All
3. For each pending escalation:
   - Read the original question
   - Expand "Retrieved context" to see what the system found in the documents
   - Type your response in the text area
   - Click Reply
4. Your response is:
   - Shown to the sales user when they next check their history
   - Added to the knowledgebase as a Q&A pair (improves future answers)

### Managing Documents (Engineers / Admins)

1. Navigate to the **Documents** page
2. Click "Upload PDF" to add new documents
3. Processing runs in background:
   - **Pending** → waiting to start
   - **Processing** → extracting text, chunking, embedding
   - **Completed** → ready for Q&A (check chunk count > 0)
   - **Failed** → check error message; may need OCR support or the PDF may be empty
4. Admins can delete documents (removes from database, vector store, and disk)
5. To update a document: delete the old version and re-upload

---

## API Reference

See **[docs/API.md](docs/API.md)** for the complete REST API reference with all 19 endpoints, request/response schemas, and examples.

Additional documentation:
- **[docs/ace-design-document.md](docs/ace-design-document.md)** — Full system requirements, architecture, and acceptance criteria (v1.2)
- **[docs/ace-implementation-plan.md](docs/ace-implementation-plan.md)** — Phase-by-phase build guide with all deviations documented

### Endpoint Summary

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| `GET` | `/health` | No | — | Health check |
| `POST` | `/api/auth/login` | No | — | Login (sets JWT cookie) |
| `POST` | `/api/auth/logout` | Yes | Any | Logout (clears cookie) |
| `GET` | `/api/auth/me` | Yes | Any | Current user info |
| `POST` | `/api/users/` | Yes | Admin | Create user |
| `GET` | `/api/users/` | Yes | Admin | List all users |
| `PATCH` | `/api/users/{id}/deactivate` | Yes | Admin | Deactivate user |
| `POST` | `/api/documents/` | Yes | Engineer, Admin | Upload PDF |
| `GET` | `/api/documents/` | Yes | Any | List documents |
| `GET` | `/api/documents/{id}` | Yes | Any | Get document details |
| `DELETE` | `/api/documents/{id}` | Yes | Admin | Delete document |
| `POST` | `/api/questions/` | Yes | Any | Ask a question |
| `GET` | `/api/questions/` | Yes | Any | List question history |
| `GET` | `/api/escalations/` | Yes | Engineer, Admin | List escalations |
| `POST` | `/api/escalations/{id}/respond` | Yes | Engineer, Admin | Respond to escalation |
| `POST` | `/api/feedback/` | Yes | Any | Submit feedback |
| `GET` | `/api/analytics/` | Yes | Admin | Get metrics |
| `GET` | `/api/config/` | Yes | Admin | Get runtime config |
| `PATCH` | `/api/config/` | Yes | Admin | Update runtime config |

---

## Testing

```bash
cd backend

# Install dependencies (if not already)
pip install -r requirements.txt

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_auth.py -v

# Run with short traceback
python -m pytest tests/ -v --tb=short
```

**Test coverage:** 46 tests across 5 test files:
- `test_auth.py` (8 tests) — Login, logout, JWT cookie, role enforcement
- `test_users.py` (9 tests) — User CRUD, permission checks, deactivation
- `test_confidence.py` (12 tests) — Score computation, threshold logic, edge cases
- `test_feedback.py` (5 tests) — Feedback submission, ownership checks
- `test_chunking.py` (12 tests) — Chunking strategies, metadata, edge cases

Tests use an in-memory SQLite database and mock all external services (sentence-transformers, Chroma, OpenRouter) — no API keys or GPU needed to run tests.

---

## Production Deployment Checklist

- [ ] **Set a strong secret key** — `APP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")`
- [ ] **Enable secure cookies** — In `backend/app/api/auth.py`, set `secure=True` on the cookie (requires HTTPS)
- [ ] **Use HTTPS** — Put behind a reverse proxy with TLS (Caddy, Traefik, or nginx with Let's Encrypt)
- [ ] **Change default admin password** — Create a new admin user, then deactivate the `admin` account
- [ ] **Restrict CORS origins** — Update `allow_origins` in `backend/app/main.py` to your actual domain
- [ ] **Back up data** — Schedule regular backups of `./data/` (uploads, Chroma index, SQLite DB)
- [ ] **Consider PostgreSQL** — For concurrent users, replace SQLite with PostgreSQL (update `ACE_DATABASE_URL`)
- [ ] **Monitor disk space** — PDF uploads and Chroma data grow over time
- [ ] **Set resource limits** — The embedding model uses ~500MB RAM; OCR on large PDFs can spike CPU

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No text could be extracted from document" | PDF may be image-only. Ensure Tesseract is installed and working: `tesseract --version` |
| First question is very slow | The sentence-transformers model downloads on first use (~90MB). Subsequent queries are fast. In Docker, the model is pre-downloaded at build time. |
| All questions are escalated | Check that documents were ingested successfully (Documents page shows status=completed and chunk_count > 0). Also check if the confidence threshold is too high (Settings page — default is 60%). Note: BM25 keyword matches (e.g., queries containing "CEO", part numbers, phone numbers) bypass escalation even with low vector similarity. |
| Login works but cookie not sent | Ensure frontend and backend are on the same origin, or that CORS `allow_credentials=True` and `withCredentials=true` are set (they are by default). |
| Docker build fails on sentence-transformers | The model download during build needs ~2GB of memory. Ensure Docker has sufficient resources. |
| "OCR failed on page X" | Tesseract may not be installed in the container. The Dockerfile installs it, but custom builds may miss it. Check: `tesseract --version` inside the container. |
| Chroma errors after upgrade | Delete `./data/chroma/` and re-upload documents. Chroma index format may change between versions. |
| API returns 401 on every request | JWT cookie may have expired (8-hour default). Login again. |

---

## Project Structure

```
ace/
├── docker-compose.yml              # Two-service stack (backend + frontend)
├── .env.example                    # Environment variable template
├── README.md                       # This file
├── docs/
│   ├── API.md                      # Complete REST API reference
│   ├── ace-design-document.md      # System requirements & design (v1.2)
│   └── ace-implementation-plan.md  # Phase-by-phase build guide
├── backend/
│   ├── Dockerfile                  # Python 3.11 + Tesseract + pre-downloaded model
│   ├── requirements.txt            # Python dependencies (pinned versions)
│   ├── config.yaml                 # Default configuration
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, lifespan, router registration
│   │   ├── api/
│   │   │   ├── auth.py             # Login, logout, current user
│   │   │   ├── users.py            # User CRUD (admin only)
│   │   │   ├── documents.py        # PDF upload, list, delete
│   │   │   ├── questions.py        # Q&A pipeline + history
│   │   │   ├── escalations.py      # Escalation queue + respond
│   │   │   ├── feedback.py         # Thumbs up/down
│   │   │   ├── analytics.py        # Admin metrics
│   │   │   └── config.py           # Runtime config management
│   │   ├── core/
│   │   │   ├── config.py           # Settings (YAML + env vars)
│   │   │   ├── security.py         # Password hashing (bcrypt) + JWT
│   │   │   └── auth.py             # Auth dependencies + role enforcement
│   │   ├── models/
│   │   │   ├── user.py             # User model (sales/engineer/admin)
│   │   │   ├── document.py         # Document model + processing status
│   │   │   ├── question.py         # Question model + confidence + feedback
│   │   │   └── escalation.py       # Escalation model
│   │   ├── services/
│   │   │   ├── embedding.py        # sentence-transformers (self-hosted)
│   │   │   ├── extraction.py       # PyMuPDF + Tesseract OCR
│   │   │   ├── chunking.py         # Hybrid chunking strategy
│   │   │   ├── ingestion.py        # Full pipeline orchestrator
│   │   │   ├── bm25.py             # BM25 keyword index (Okapi BM25 with NLTK stemming/stopwords)
│   │   │   ├── retrieval.py        # Hybrid retrieval: Chroma vector + BM25, fused via RRF
│   │   │   ├── llm.py              # OpenRouter LLM service
│   │   │   └── confidence.py       # Combined confidence scoring + BM25-aware escalation bypass
│   │   └── db/
│   │       ├── database.py         # Async SQLAlchemy + seed admin
│   │       └── chroma_client.py    # ChromaDB client singleton
│   └── tests/
│       ├── conftest.py             # Test fixtures, mocks, helpers
│       ├── test_auth.py            # Auth endpoint tests
│       ├── test_users.py           # User management tests
│       ├── test_confidence.py      # Scoring logic tests
│       ├── test_feedback.py        # Feedback tests
│       └── test_chunking.py        # Chunking logic tests
├── frontend/
│   ├── Dockerfile                  # Multi-stage: Node build → nginx serve
│   ├── nginx.conf                  # SPA fallback + API proxy
│   ├── package.json                # Node dependencies
│   ├── vite.config.js              # Vite + Tailwind + API proxy
│   └── src/
│       ├── main.jsx                # React entrypoint
│       ├── App.jsx                 # Router with all routes
│       ├── index.css               # Tailwind imports
│       ├── api/
│       │   └── client.js           # Axios instance (cookie auth, 401 redirect)
│       ├── context/
│       │   └── AuthContext.jsx     # Auth state management
│       ├── components/
│       │   ├── Layout.jsx          # Nav bar with role-aware links
│       │   └── ProtectedRoute.jsx  # Route guard + role check
│       └── pages/
│           ├── LoginPage.jsx       # Login form
│           ├── AskPage.jsx         # Chat-style Q&A interface
│           ├── HistoryPage.jsx     # Question history with expandable details
│           ├── EscalationsPage.jsx # Engineer escalation dashboard
│           ├── DocumentsPage.jsx   # PDF upload + document table
│           ├── UsersPage.jsx       # User management (admin)
│           ├── AnalyticsPage.jsx   # Metrics dashboard (admin)
│           └── SettingsPage.jsx    # Runtime config editor (admin)
```

---

## License

Proprietary — PEI-Genesis internal use only.
