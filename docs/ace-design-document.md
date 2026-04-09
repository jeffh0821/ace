# Knowledgebase Q&A System — Requirements & Design Document

---

## 1. Overview

**Project Name:** ACE — Assistant for Connector Engineering  
**Type:** Standalone web application with extensible channel architecture  
**Core Functionality:** Ingest technical PDFs into a searchable knowledgebase; allow sales to ask questions against that knowledgebase; surface high-confidence answers with citations; escalate low-confidence questions to engineers for response.  
**Target Users:** Sales team, Engineers, Administrators  

---

## 2. Goals & Success Metrics

- Reduce engineering time spent on repetitive sales Q&A
- Improve sales team response speed and confidence
- Accelerate deal closure through faster, more accurate technical answers

---

## 3. User Roles & Permissions

| Role | Ask Questions | View Answers | Feedback | Escalations | Answer Escalations | Manage Docs | Analytics |
|------|--------------|-------------|----------|-------------|-------------------|-------------|-----------|
| Sales | ✓ | ✓ | ✓ | — | — | — | — |
| Engineer | ✓ | ✓ | ✓ | ✓ (view/reply) | ✓ | ✓ | — |
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## 4. Document Ingestion

### 4.1 Supported Formats
- PDF (primary, near-exclusive)
- Complex documents with text, tables, diagrams, illustrations

### 4.2 Source
- Manual uploads via web UI
- No automated sync or external integrations (self-contained)

### 4.3 Processing Requirements
- Full text extraction with structure preservation (headings, sections, page breaks)
- **Hybrid chunking strategy**: structure-aware splitting (headings, sections, page breaks) with fallback to fixed-size token chunks with overlap for long unstructured blocks. Preserve semantic boundaries where possible.
- OCR for scanned documents
- **Heavy OCR pipeline required** — expect a significant volume of scanned documents with diagrams and tables. Use Tesseract or equivalent robust OCR engine.
- Diagrams/illustrations: for MVP, extract text descriptions where possible using standard OCR/text extraction; exclude from Q&A if not parseable. **Post-MVP**: augment with a vision model (e.g., GPT-4o vision) to generate descriptions of diagrams and illustrations for improved retrieval.
- Tables: extracted as structured text with row/column context

### 4.4 Metadata
- Minimal required metadata
- Document title (extracted from filename or手动 entered)
- Upload date (auto-captured)
- Processed date (auto-captured)
- No mandatory author, category, or product tagging

### 4.5 Knowledgebase Storage
- Vector database: **Chroma** (self-hosted, lightweight, zero-cost, Python-native; ideal for small-to-medium document volumes)
- Defer final DB choice to implementer if Chroma proves insufficient at implementation time
- Self-hosted container or direct process (no managed cloud DB)
- Storage for original PDFs + extracted text chunks + vector embeddings

### 4.6 Document Management
- Upload via web UI (engineers and admins)
- List, view, delete documents (admins)
- No versioning in MVP; re-ingest on update

---

## 5. Question Answering

### 5.1 Interface
- Standalone web application (single-page app)
- Chat-style interface: user types question → system retrieves context → generates answer
- Architecture must support adding channels (Slack, Teams, etc.) in future without redesign

### 5.2 Retrieval & Generation Pipeline
1. User submits question
2. Question is embedded via self-hosted embedding model (sentence-transformers)
3. **Hybrid retrieval**: Top-K chunks retrieved from both ChromaDB (vector/cosine similarity) AND a BM25 keyword index simultaneously
4. **Reciprocal Rank Fusion (RRF)**: Results from both retrieval methods are merged using RRF, which ranks by reciprocal position rather than raw score (avoiding the problem of normalising disparate score distributions). RRF score for chunk = 1/(60+vector_rank) + 1/(60+bm25_rank)
5. Retrieved chunks passed to LLM with prompt asking for answer based on context
6. LLM generates answer with citations (document name, page/section, excerpt)

### 5.3 Confidence Scoring
- **Combined score**: retrieval_weight × retrieval_confidence + llm_weight × LLM_confidence
- **Retrieval confidence**: cosine similarity score from vector search (averaged across top-K chunks)
- **LLM confidence**: LLM returns a structured confidence score in its response (JSON output with a confidence field). Logprobs not used — structured output is more reliable across providers.
- **BM25-aware escalation bypass**: When the top-retrieved chunk has BM25 rank=1 AND BM25 score ≥ 2.0, the system skips escalation even if the combined score is below threshold. This is because a strong verbatim keyword match is itself a high-confidence retrieval signal — particularly important for named entities (e.g., "CEO") that carry low semantic weight in dense embeddings.
- **Threshold**: 60% default (lowered from 80%), admin-tuneable via config/UI
- Below threshold → escalation flow triggered (unless BM25 bypass fires)

### 5.4 Answer Output
- Answer text (clear, conversational)
- Citations: document title + relevant excerpt
- Link to source document (internal reference, not external URL)
- Confidence score displayed (optional, admin-configurable)
- **Below-threshold answers**: question enters "escalated" state on the sales user's dashboard. No partial or hedged answer shown — just an escalation status indicator.

### 5.5 Feedback Loop
- Thumbs up/down on every answer
- Positive feedback (thumbs up): Q&A pair stored as potential training/-tuning example
- Negative feedback (thumbs down): flagged for review, optionally fed back for tuning
- Feedback data stored separately, used for continuous improvement

### 5.6 Model Configuration
- OpenRouter as LLM provider
- Configurable model selection via config file or UI (admins)
- Default model recommended at implementation time (cost/performance balance)
- Embedding model: self-hosted sentence-transformers (configurable model name via config)

---

## 6. Escalation Workflow

### 6.1 Trigger
- Answer confidence < threshold (default 60%) AND top chunk has no strong BM25 keyword match
- **BM25 override**: If the top chunk has BM25 rank=1 and score ≥ 2.0, escalation is skipped regardless of the combined confidence score
- System marks question as "escalated" automatically

### 6.2 Escalation Queue (Dashboard)
- Engineer dashboard shows pending escalations
- Each escalation displays:
  - Original question
  - Retrieved context excerpts (what the system found but wasn't confident enough about)
  - Timestamp
  - Submitting user (sales rep name)
- No customer name, no full conversation history in MVP

### 6.3 Engineer Response
- Engineer types reply in dashboard
- Reply is sent back to sales user as the official answer
- Engineer can optionally mark as "answered" and include their own answer
- Escalation marked as resolved
- **Feedback into knowledgebase**: engineer responses to escalations are stored as validated Q&A pairs and fed back into the knowledgebase to improve future retrieval and answer quality.

### 6.5 Sales User Notification (MVP)
- No push notifications, email, or real-time alerts in MVP
- Sales user sees the engineer's response the next time they open the app (visible in their question history / dashboard)

### 6.4 Future Extensibility
- Email/Slack notification to engineer on escalation (deferred)
- Email/Slack reply integration (deferred)
- Engineer response auto-notifies sales user via same channel they submitted (deferred)

---

## 7. Authentication & Authorization

### 7.1 Current (MVP)
- Local user accounts stored in database (username/password, bcrypt hashed)
- No SSO, no external identity provider
- Sessions managed server-side
- **User provisioning**: accounts created manually by Admin role via dashboard. No self-registration.

### 7.2 Future (SAML SSO)
- Auth module must be modular/pluggable
- SAML 2.0 SSO with group-to-role mapping planned
- Architect must not hardcode local-only auth assumptions
- Users provisioned and assigned roles/groups via SAML identity provider

### 7.3 Session Management
- **JWT tokens** stored in httpOnly, secure, sameSite cookies (cleanest approach for SPA + REST API)
- No server-side session store required

---

## 8. Technical Stack

### 8.1 Core Stack
- **Backend:** Python (FastAPI — async, lightweight, good OpenRouter integration)
- **Frontend:** React (single-page app, chat UI)
- **Vector DB:** Chroma (self-hosted, zero-cost, sufficient for dozens of docs)
- **LLM Provider:** OpenRouter (API-compatible with OpenAI, flexible model switching)
- **Embeddings:** Self-hosted sentence-transformers (runs in Docker alongside other services)
- **Relational DB:** SQLite (zero-config, self-contained, fits single-server deployment; migrate to PostgreSQL if scale demands)

### 8.2 Infrastructure
- Fully self-contained
- All services run on a single Linux server
- No external managed services (no AWS, no cloud DB hosting)
- Docker Compose for easy deployment
- Designed for portable deployment to any Linux box via `docker-compose up`

### 8.3 Cost Minimization
- All open-source software
- Self-hosted where possible
- OpenRouter costs only (pay-per-token; small document volume = very low cost)

---

## 9. Application Structure

### 9.1 Pages/Views
- **Login page** — auth
- **Dashboard (Sales):** Ask question, view answer history, feedback on answers
- **Dashboard (Engineer):** Escalation queue, reply to escalations, document management
- **Dashboard (Admin):** All of above + document management + analytics + config

### 9.2 API Design (REST or GraphQL — defer to implementer)
Core endpoints:
- `POST /auth/login`
- `POST /auth/logout`
- `GET /documents` — list documents
- `POST /documents` — upload document
- `DELETE /documents/{id}` — delete document
- `POST /questions` — submit question, get answer
- `GET /questions` — list own question history (sales)
- `GET /escalations` — list pending escalations (engineer)
- `POST /escalations/{id}/respond` — engineer replies
- `POST /feedback` — submit thumbs up/down on answer
- `GET /analytics` — admin-only metrics

---

## 10. File Structure (Recommended)

```
ace/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── documents.py
│   │   │   ├── questions.py
│   │   │   ├── escalations.py
│   │   │   └── feedback.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── auth.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   ├── question.py
│   │   │   └── escalation.py
│   │   ├── services/
│   │   │   ├── ingestion.py
│   │   │   ├── retrieval.py
│   │   │   ├── llm.py
│   │   │   └── confidence.py
│   │   └── db/
│   │       ├── database.py
│   │       └── chroma_client.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/
│   ├── package.json
│   └── Dockerfile
└── README.md
```

---

## 11. MVP Scope

### 11.1 Design Decisions (Clarified)
- **Chunking**: Hybrid (structure-aware + token fallback with overlap)
- **OCR**: Heavy pipeline (Tesseract) — high volume of scanned docs expected
- **Diagrams**: MVP uses standard extraction only; vision model augmentation post-MVP
- **Embeddings**: Self-hosted sentence-transformers (no external API cost)
- **Confidence**: Structured JSON output from LLM (no logprobs)
- **Low-confidence UX**: "Escalated" status on dashboard; no partial answers shown
- **Notifications**: MVP has no push/email notifications; users check dashboard
- **Escalation feedback**: Engineer answers fed back into knowledgebase
- **User provisioning**: Admin-created accounts (MVP); SAML-provisioned (future)
- **Auth tokens**: JWT in httpOnly secure cookies
- **Frontend**: React
- **Relational DB**: SQLite
- **Deployment**: Docker Compose on any Linux box
- **Branding**: Functional MVP, no branding requirements

**In Scope:**
- PDF upload and ingestion with chunking/embedding
- Question answering with confidence scoring
- Citation + excerpt in answer
- Thumbs up/down feedback
- Escalation queue + engineer reply
- Local auth (username/password)
- Three roles (sales, engineer, admin)
- Document management (upload, list, delete)
- Configurable model selection

**Out of Scope (Future):**
- SAML SSO
- Slack/Teams integration
- Email escalation notifications
- Document versioning
- Conversation history tracking
- Advanced analytics

---

## 12. Configuration

All configuration via `config.yaml` or environment variables:

```yaml
llm:
  provider: openrouter
  model: gpt-4o-mini  # default, changeable
  embedding_model: all-MiniLM-L6-v2  # self-hosted sentence-transformers
  api_key: ${OPENROUTER_API_KEY}

confidence:
  threshold: 0.60
  retrieval_weight: 0.5
  llm_weight: 0.5

retrieval:
  top_k: 5

database:
  chroma_persist_dir: ./chroma_data

app:
  host: 0.0.0.0
  port: 8000
  secret_key: ${APP_SECRET_KEY}
```

---

## 13. Acceptance Criteria

1. **Document Ingestion:** Engineer/admin can upload a 100-page PDF and see it processed, chunked, and stored within 60 seconds
2. **Question Answering:** Sales user submits a question and receives an answer with citations in under 10 seconds (excluding LLM latency)
3. **Confidence Threshold:** Answers below 60% confidence trigger escalation and do NOT show a low-confidence answer to the user. Exception: if the top retrieved chunk has a strong BM25 keyword match (rank=1, score ≥ 2.0), escalation is bypassed regardless of confidence score.
4. **Feedback:** Sales user can thumbs-up/down an answer; feedback is stored and associated with the Q&A pair
5. **Escalation Flow:** Engineer sees escalated question in dashboard, replies, and sales user sees the engineer's answer
6. **Auth:** Users cannot access features outside their role; guests cannot access any feature without login
7. **Model Swap:** Admin can change the LLM model via config without redeploying

---

*Document version: 1.2 — Hybrid search (BM25 + Vector + RRF), BM25-aware escalation bypass, confidence threshold 0.60*
*Prepared for: Engineering handoff*
*Status: Implemented — clarifications integrated*
