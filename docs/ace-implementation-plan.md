# ACE — Assistant for Connector Engineering: Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan phase-by-phase.

**Goal:** Build a self-contained RAG web application that ingests technical PDFs, answers sales questions with citations and confidence scoring, and escalates low-confidence questions to engineers.

**Architecture:** FastAPI backend serving a REST API + React SPA frontend. SQLite for relational data (users, questions, escalations, feedback). Chroma for vector storage. Self-hosted sentence-transformers for embeddings. OpenRouter for LLM inference. Tesseract for heavy OCR. All containerized via Docker Compose.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Chroma, sentence-transformers (all-MiniLM-L6-v2), Tesseract OCR, PyMuPDF, React 18, Vite, TailwindCSS, Docker Compose.

**Working Directory:** `~/.hermes/ace/`

**Design Document:** `ace-design-document.md` (v1.2, in this directory)

---

## Implementation Notes (v1.2 — Post-Build Deviations)

The following deviations from the original plan were made during implementation:

### Retrieval: Hybrid Search (BM25 + Vector + RRF)
- **Original plan:** Pure ChromaDB vector search
- **Implemented:** Dual retrieval — ChromaDB (vector cosine similarity) + BM25Okapi (keyword), fused via **Reciprocal Rank Fusion (RRF)** with k=60. RRF was chosen over alpha-weighting because it doesn't require normalising disparate score distributions.
- **New file:** `backend/app/services/bm25.py` — BM25Okapi index with NLTK stemming and stopword removal. Persists to `/app/bm25_index.json` inside container (mapped to host at `~/.hermes/ace/data/db/bm25_index.json`).
- **BM25 index rebuild:** Triggered on every document upload (full rebuild) and document deletion (full rebuild).
- **RRF_K = 60** used to dampen rank differences and treat both retrieval methods as roughly equally important.

### Confidence: BM25-Aware Escalation Bypass
- **Original plan:** Escalate when combined_score < threshold
- **Implemented:** `should_escalate()` in `confidence.py` checks if top chunk has BM25 rank=1 AND score ≥ 2.0. If so, escalation is skipped even when combined score is below threshold. This solves the named-entity problem where dense embeddings underweight specific names (e.g., "CEO", "Steven Fisher").
- **BM25_STRONG_SCORE = 2.0** threshold — "CEO" scores ~6.0; generic connector terms score ~0.

### Confidence Threshold: 0.60
- **Original plan:** 0.80 default
- **Implemented:** 0.60 default (lowered after testing). Still admin-tuneable at runtime.

### Extraction Hardening
- `FOOTER_PATTERNS` in `extraction.py` softened to be more targeted (phone numbers, URLs, specific boilerplate) and anchored to line boundaries to prevent accidental stripping of body text.
- `_strip_header_footer()` now always runs the regex pass even when no high-frequency repeating lines are found — ensuring pattern-based stripping always executes.
- Frequency-based header/footer detection requires 3+ pages to activate.

### Docker Hardening
- `rank-bm25==0.2.2` (not 3.0.2 which does not exist)
- NLTK data (`punkt`, `stopwords`) pre-downloaded in Dockerfile to prevent runtime download failures: `RUN python3 -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True)"`
- NLTK data stored at `/usr/share/nltk_data` inside container.

### Project Status
- **46 tests passing** across 5 test files
- **Default admin:** `admin / P3iG3n3s1s!`
- **Deployment:** Docker Compose on `apollo.philadelphia.com`

---

---

## Phase 0: Project Scaffolding & Infrastructure

### Task 0.1: Initialize Project Structure

**Objective:** Create the directory skeleton and initialize git repo.

**Files:**
- Create: `ace/` directory tree per design doc Section 10
- Create: `ace/.gitignore`
- Create: `ace/README.md`

**Steps:**

1. Create directory structure:
```bash
mkdir -p ~/.hermes/ace
cd ~/.hermes/ace
mkdir -p backend/app/{api,core,models,services,db}
mkdir -p backend/tests
mkdir -p frontend/src/{pages,components,api}
mkdir -p frontend/public
```

2. Create `.gitignore`:
```
# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/

# Node
node_modules/
dist/
build/

# Data
chroma_data/
*.db
uploads/

# Secrets
.env
*.pem

# IDE
.vscode/
.idea/
```

3. Create minimal `README.md`:
```markdown
# ACE — Assistant for Connector Engineering

RAG-powered Q&A system for technical connector engineering knowledge.

## Quick Start
docker-compose up --build

## Architecture
- Backend: FastAPI + SQLite + Chroma
- Frontend: React + Vite + TailwindCSS
- Embeddings: sentence-transformers (self-hosted)
- LLM: OpenRouter
- OCR: Tesseract
```

4. Initialize git:
```bash
cd ~/.hermes/ace
git init
git add .
git commit -m "chore: initialize project structure"
```

---

### Task 0.2: Backend Configuration & Dependencies

**Objective:** Set up Python project with FastAPI, all dependencies, and config loader.

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/core/config.py`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/app/core/__init__.py` (empty)

**Step 1: Create `backend/requirements.txt`**

```
# Web framework
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.19

# Database
sqlalchemy==2.0.36
aiosqlite==0.20.0

# Vector DB
chromadb==0.5.23

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.2.1

# PDF processing
pymupdf==1.25.1
pytesseract==0.3.13
Pillow==11.1.0

# Embeddings
sentence-transformers==3.3.1

# BM25 keyword search
rank-bm25==0.2.2
nltk==3.9.1

# LLM
httpx==0.28.1

# Config
pyyaml==6.0.2
pydantic-settings==2.7.1

# Testing
pytest==8.3.4
pytest-asyncio==0.25.0
httpx==0.28.1
```

**Step 2: Create `backend/app/core/config.py`**

```python
"""Application configuration loaded from config.yaml and environment variables."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic_settings import BaseSettings


def load_yaml_config() -> dict:
    """Load config.yaml from project root, return empty dict if not found."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = load_yaml_config()


class Settings(BaseSettings):
    # App
    app_host: str = _yaml.get("app", {}).get("host", "0.0.0.0")
    app_port: int = _yaml.get("app", {}).get("port", 8000)
    secret_key: str = _yaml.get("app", {}).get("secret_key", "CHANGE-ME-IN-PRODUCTION")

    # Database
    database_url: str = "sqlite+aiosqlite:///./ace.db"

    # Chroma
    chroma_persist_dir: str = _yaml.get("database", {}).get("chroma_persist_dir", "./chroma_data")

    # LLM
    llm_provider: str = _yaml.get("llm", {}).get("provider", "openrouter")
    llm_model: str = _yaml.get("llm", {}).get("model", "gpt-4o-mini")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", _yaml.get("llm", {}).get("api_key", ""))

    # Embeddings
    embedding_model: str = _yaml.get("llm", {}).get("embedding_model", "all-MiniLM-L6-v2")

    # Confidence
    confidence_threshold: float = _yaml.get("confidence", {}).get("threshold", 0.60)
    retrieval_weight: float = _yaml.get("confidence", {}).get("retrieval_weight", 0.5)
    llm_weight: float = _yaml.get("confidence", {}).get("llm_weight", 0.5)

    # Retrieval
    top_k: int = _yaml.get("retrieval", {}).get("top_k", 5)

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours

    # Upload
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 100

    class Config:
        env_prefix = "ACE_"


settings = Settings()
```

**Step 3: Create `backend/config.yaml`**

```yaml
llm:
  provider: openrouter
  model: gpt-4o-mini
  embedding_model: all-MiniLM-L6-v2
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

**Step 4: Create `__init__.py` files**

```bash
touch backend/app/__init__.py
touch backend/app/core/__init__.py
touch backend/app/api/__init__.py
touch backend/app/models/__init__.py
touch backend/app/services/__init__.py
touch backend/app/db/__init__.py
touch backend/tests/__init__.py
```

**Step 5: Commit**
```bash
git add .
git commit -m "chore: add backend dependencies and config loader"
```

---

### Task 0.3: Database Layer (SQLAlchemy + SQLite)

**Objective:** Set up async SQLAlchemy engine, session factory, and base model.

**Files:**
- Create: `backend/app/db/database.py`

**Step 1: Create `backend/app/db/database.py`**

```python
"""Async SQLAlchemy database engine and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables. Called on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add async SQLAlchemy database layer"
```

---

### Task 0.4: Chroma Vector DB Client

**Objective:** Initialize Chroma persistent client as a singleton.

**Files:**
- Create: `backend/app/db/chroma_client.py`

**Step 1: Create `backend/app/db/chroma_client.py`**

```python
"""Chroma vector database client (persistent, self-hosted)."""

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

_client = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Return singleton persistent Chroma client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str = "documents"):
    """Get or create the documents collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add Chroma vector DB client"
```

---

### Task 0.5: FastAPI Application Entrypoint

**Objective:** Create the main FastAPI app with CORS, lifespan events, and health check.

**Files:**
- Create: `backend/app/main.py`

**Step 1: Create `backend/app/main.py`**

```python
"""ACE — FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB tables. Shutdown: cleanup."""
    await init_db()
    yield


app = FastAPI(
    title="ACE — Assistant for Connector Engineering",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
```

**Step 2: Test it boots**
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"0.1.0"}
kill %1
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add FastAPI entrypoint with health check"
```

---

## Phase 1: Authentication & User Management

### Task 1.1: User Model

**Objective:** Define the User SQLAlchemy model with role enum.

**Files:**
- Create: `backend/app/models/user.py`

**Step 1: Create `backend/app/models/user.py`**

```python
"""User model with role-based access."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean
from app.db.database import Base


class UserRole(str, enum.Enum):
    sales = "sales"
    engineer = "engineer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.sales)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add User model with roles"
```

---

### Task 1.2: Security Utilities (Password Hashing + JWT)

**Objective:** Create password hashing and JWT token utilities.

**Files:**
- Create: `backend/app/core/security.py`

**Step 1: Create `backend/app/core/security.py`**

```python
"""Password hashing and JWT token utilities."""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add password hashing and JWT utilities"
```

---

### Task 1.3: Auth Dependencies (Current User Extraction)

**Objective:** Create FastAPI dependencies that extract current user from JWT cookie and enforce roles.

**Files:**
- Create: `backend/app/core/auth.py`

**Step 1: Create `backend/app/core/auth.py`**

```python
"""FastAPI auth dependencies — extract user from JWT cookie, enforce roles."""

from typing import List

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.user import User, UserRole


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Extract and validate JWT from httpOnly cookie, return User."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


def require_roles(allowed_roles: List[UserRole]):
    """Dependency factory: enforce role-based access."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return role_checker
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add auth dependencies with role enforcement"
```

---

### Task 1.4: Auth API Endpoints (Login, Logout, Me)

**Objective:** Create login (sets JWT cookie), logout (clears cookie), and /me endpoint.

**Files:**
- Create: `backend/app/api/auth.py`

**Step 1: Create `backend/app/api/auth.py`**

```python
"""Auth API — login, logout, current user."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.security import verify_password, create_access_token
from app.db.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    role: str

    class Config:
        from_attributes = True


@router.post("/login")
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=28800,  # 8 hours
    )

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    return {"message": "Login successful", "user": UserResponse.model_validate(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
```

**Step 2: Register router in `main.py`** — add import and include:
```python
from app.api.auth import router as auth_router
app.include_router(auth_router, prefix="/api")
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add auth API (login, logout, me)"
```

---

### Task 1.5: Admin User Management Endpoints

**Objective:** Admin can create, list, and deactivate user accounts.

**Files:**
- Create: `backend/app/api/users.py`

**Step 1: Create `backend/app/api/users.py`**

```python
"""User management API — admin only."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.security import hash_password
from app.db.database import get_db
from app.models.user import User, UserRole

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    username: str
    email: str
    display_name: str
    password: str
    role: UserRole


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    # Check uniqueness
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already exists")

    user = User(
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.patch("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    return {"message": f"User {user.username} deactivated"}
```

**Step 2: Register router in `main.py`**:
```python
from app.api.users import router as users_router
app.include_router(users_router, prefix="/api")
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add admin user management API"
```

---

### Task 1.6: Seed Admin User on First Startup

**Objective:** Auto-create a default admin account if no users exist (first boot).

**Files:**
- Modify: `backend/app/db/database.py` — add seed function
- Modify: `backend/app/main.py` — call seed in lifespan

**Step 1: Add to `database.py`:**

```python
async def seed_admin():
    """Create default admin if no users exist."""
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    async with async_session() as session:
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None:
            admin = User(
                username="admin",
                email="admin@ace.local",
                display_name="System Administrator",
                password_hash=hash_password("changeme"),
                role=UserRole.admin,
            )
            session.add(admin)
            await session.commit()
            print(">>> Seeded default admin user (admin / changeme)")
```

(Requires `from sqlalchemy import select` import at top of database.py)

**Step 2: Update `main.py` lifespan:**

```python
from app.db.database import init_db, seed_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_admin()
    yield
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: seed default admin user on first startup"
```

---

## Phase 2: Document Ingestion Pipeline

### Task 2.1: Document Model

**Objective:** SQLAlchemy model for tracking uploaded/processed documents.

**Files:**
- Create: `backend/app/models/document.py`

**Step 1: Create `backend/app/models/document.py`**

```python
"""Document model — tracks uploaded PDFs and processing status."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text
from app.db.database import Base


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, default=0)
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    error_message = Column(Text, nullable=True)
    uploaded_by = Column(Integer, nullable=False)  # FK to users.id
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add Document model"
```

---

### Task 2.2: Embedding Service

**Objective:** Self-hosted sentence-transformers embedding service (singleton model loader).

**Files:**
- Create: `backend/app/services/embedding.py`

**Step 1: Create `backend/app/services/embedding.py`**

```python
"""Self-hosted embedding service using sentence-transformers."""

from typing import List

from sentence_transformers import SentenceTransformer

from app.core.config import settings

_model = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load and cache the embedding model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts, return list of vectors."""
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add self-hosted embedding service"
```

---

### Task 2.3: PDF Extraction Service (PyMuPDF + Tesseract OCR)

**Objective:** Extract text from PDFs — native text via PyMuPDF, OCR fallback via Tesseract for scanned pages. Preserve structure (headings, tables).

**Files:**
- Create: `backend/app/services/extraction.py`

**Step 1: Create `backend/app/services/extraction.py`**

```python
"""PDF text extraction with OCR fallback.

Strategy:
1. Try native text extraction via PyMuPDF (fast, preserves structure)
2. If a page has little/no text, fall back to Tesseract OCR on rendered image
3. Extract tables as structured text where possible
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io


# Minimum characters on a page before triggering OCR fallback
OCR_TEXT_THRESHOLD = 50


@dataclass
class ExtractedPage:
    page_number: int  # 1-indexed
    text: str
    is_ocr: bool = False
    tables: List[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    filename: str
    page_count: int
    pages: List[ExtractedPage]
    errors: List[str] = field(default_factory=list)


def extract_pdf(file_path: str) -> ExtractionResult:
    """Extract all text from a PDF file with OCR fallback."""
    path = Path(file_path)
    doc = fitz.open(str(path))
    pages = []
    errors = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        try:
            # Try native text extraction first
            text = page.get_text("text")

            # Extract tables as text blocks
            tables = []
            table_finder = page.find_tables()
            if table_finder and table_finder.tables:
                for table in table_finder.tables:
                    try:
                        df = table.to_pandas()
                        tables.append(df.to_string(index=False))
                    except Exception:
                        pass

            # OCR fallback if native text is too sparse
            is_ocr = False
            if len(text.strip()) < OCR_TEXT_THRESHOLD:
                try:
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = pytesseract.image_to_string(img)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                        is_ocr = True
                except Exception as e:
                    errors.append(f"OCR failed on page {page_num + 1}: {str(e)}")

            pages.append(ExtractedPage(
                page_number=page_num + 1,
                text=text.strip(),
                is_ocr=is_ocr,
                tables=tables,
            ))

        except Exception as e:
            errors.append(f"Extraction failed on page {page_num + 1}: {str(e)}")
            pages.append(ExtractedPage(page_number=page_num + 1, text=""))

    doc.close()

    return ExtractionResult(
        filename=path.name,
        page_count=len(doc) if not doc.is_closed else len(pages),
        pages=pages,
        errors=errors,
    )
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add PDF extraction with Tesseract OCR fallback"
```

---

### Task 2.4: Hybrid Chunking Service

**Objective:** Split extracted text into chunks using hybrid strategy: structure-aware (headings, page breaks) with token-size fallback and overlap.

**Files:**
- Create: `backend/app/services/chunking.py`

**Step 1: Create `backend/app/services/chunking.py`**

```python
"""Hybrid chunking: structure-aware splitting with token-size fallback.

Strategy:
1. Split on structural boundaries (headings, page breaks, double newlines)
2. If a structural chunk exceeds max_tokens, split by token count with overlap
3. Each chunk carries metadata: document_id, page_number, chunk_index
"""

import re
from dataclasses import dataclass
from typing import List, Optional

# Defaults
DEFAULT_MAX_CHUNK_CHARS = 1500
DEFAULT_OVERLAP_CHARS = 200

# Structural split patterns (ordered by priority)
STRUCTURAL_PATTERNS = [
    r'\n#{1,6}\s',          # Markdown headings
    r'\n\d+\.\s',           # Numbered sections
    r'\n[A-Z][A-Z\s]{5,}',  # ALL-CAPS headings
    r'\n\n\n+',             # Triple+ newlines
    r'\n\n',                # Double newlines (paragraph breaks)
]


@dataclass
class Chunk:
    text: str
    document_id: int
    page_number: int
    chunk_index: int
    metadata: dict


def _split_structural(text: str) -> List[str]:
    """Split text on structural boundaries."""
    # Combine patterns into a single split regex
    combined = '|'.join(f'({p})' for p in STRUCTURAL_PATTERNS)
    parts = re.split(combined, text)
    # Filter out None and empty strings, rejoin delimiters with following text
    segments = []
    current = ""
    for part in parts:
        if part is None:
            continue
        current += part
        # If this part is substantial, save it
        if len(current.strip()) > 50 and any(re.match(p.lstrip(r'\n'), part.strip()) for p in STRUCTURAL_PATTERNS):
            if current.strip():
                segments.append(current.strip())
            current = part  # Start new segment with the heading
    if current.strip():
        segments.append(current.strip())

    return segments if segments else [text]


def _split_by_size(text: str, max_chars: int, overlap: int) -> List[str]:
    """Split text into fixed-size chunks with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            # Look for last period, newline, or space near the boundary
            for sep in ['. ', '.\n', '\n\n', '\n', ' ']:
                last_sep = text.rfind(sep, start + max_chars // 2, end)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else len(text)
    return chunks


def chunk_document(
    pages: list,
    document_id: int,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> List[Chunk]:
    """
    Chunk extracted pages using hybrid strategy.

    Args:
        pages: list of ExtractedPage objects
        document_id: ID of the parent document
        max_chunk_chars: max characters per chunk
        overlap_chars: overlap between consecutive token-split chunks

    Returns:
        List of Chunk objects ready for embedding
    """
    chunks = []
    chunk_idx = 0

    for page in pages:
        # Combine page text with any table text
        full_text = page.text
        if page.tables:
            full_text += "\n\n[TABLE]\n" + "\n[TABLE]\n".join(page.tables)

        if not full_text.strip():
            continue

        # Step 1: structural split
        segments = _split_structural(full_text)

        # Step 2: size-based split if any segment is too large
        for segment in segments:
            if len(segment) > max_chunk_chars:
                sub_chunks = _split_by_size(segment, max_chunk_chars, overlap_chars)
            else:
                sub_chunks = [segment]

            for text in sub_chunks:
                if len(text.strip()) < 20:  # skip trivially small chunks
                    continue
                chunks.append(Chunk(
                    text=text.strip(),
                    document_id=document_id,
                    page_number=page.page_number,
                    chunk_index=chunk_idx,
                    metadata={
                        "document_id": document_id,
                        "page_number": page.page_number,
                        "chunk_index": chunk_idx,
                        "is_ocr": page.is_ocr,
                    },
                ))
                chunk_idx += 1

    return chunks
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add hybrid chunking service"
```

---

### Task 2.5: Ingestion Pipeline (Orchestrator)

**Objective:** Orchestrate the full pipeline: save PDF → extract → chunk → embed → store in Chroma. Background task.

**Files:**
- Create: `backend/app/services/ingestion.py`

**Step 1: Create `backend/app/services/ingestion.py`**

```python
"""Document ingestion pipeline: extract → chunk → embed → store."""

import asyncio
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.db.chroma_client import get_collection
from app.models.document import Document, ProcessingStatus
from app.services.extraction import extract_pdf
from app.services.chunking import chunk_document
from app.services.embedding import embed_texts


async def ingest_document(document_id: int):
    """
    Full ingestion pipeline for a document. Runs as a background task.

    1. Update status to 'processing'
    2. Extract text from PDF (with OCR fallback)
    3. Chunk extracted text (hybrid strategy)
    4. Embed chunks via sentence-transformers
    5. Store embeddings in Chroma
    6. Update status to 'completed'
    """
    async with async_session() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None:
            return

        try:
            # Mark as processing
            doc.status = ProcessingStatus.processing
            await db.commit()

            # Step 1: Extract text
            extraction = await asyncio.to_thread(extract_pdf, doc.file_path)
            doc.page_count = extraction.page_count

            # Step 2: Chunk
            chunks = chunk_document(extraction.pages, document_id=doc.id)

            if not chunks:
                doc.status = ProcessingStatus.failed
                doc.error_message = "No text could be extracted from document"
                await db.commit()
                return

            # Step 3: Embed
            texts = [c.text for c in chunks]
            embeddings = await asyncio.to_thread(embed_texts, texts)

            # Step 4: Store in Chroma
            collection = get_collection()
            ids = [f"doc{doc.id}_chunk{c.chunk_index}" for c in chunks]
            metadatas = [
                {
                    "document_id": doc.id,
                    "document_title": doc.title,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                    "is_ocr": str(c.metadata.get("is_ocr", False)),
                }
                for c in chunks
            ]

            # Chroma has batch limits; add in batches of 100
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                batch_end = i + batch_size
                collection.add(
                    ids=ids[i:batch_end],
                    embeddings=embeddings[i:batch_end],
                    documents=texts[i:batch_end],
                    metadatas=metadatas[i:batch_end],
                )

            # Step 5: Update document record
            doc.chunk_count = len(chunks)
            doc.status = ProcessingStatus.completed
            doc.processed_at = datetime.utcnow()
            if extraction.errors:
                doc.error_message = "; ".join(extraction.errors)
            await db.commit()

        except Exception as e:
            doc.status = ProcessingStatus.failed
            doc.error_message = str(e)[:2000]
            await db.commit()
            raise
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add document ingestion pipeline"
```

---

### Task 2.6: Document API Endpoints (Upload, List, Delete)

**Objective:** REST endpoints for document management.

**Files:**
- Create: `backend/app/api/documents.py`

**Step 1: Create `backend/app/api/documents.py`**

```python
"""Document management API — upload, list, delete."""

import os
import shutil
from datetime import datetime
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.config import settings
from app.db.database import get_db
from app.db.chroma_client import get_collection
from app.models.document import Document, ProcessingStatus
from app.models.user import User, UserRole
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: int
    title: str
    filename: str
    file_size_bytes: int
    page_count: int | None
    chunk_count: int
    status: str
    error_message: str | None
    uploaded_at: datetime
    processed_at: datetime | None

    class Config:
        from_attributes = True


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.engineer, UserRole.admin])),
):
    """Upload a PDF document for ingestion."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Save file
    safe_filename = f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    file_path = os.path.join(settings.upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")
        f.write(content)

    # Create document record
    title = os.path.splitext(file.filename)[0]
    doc = Document(
        title=title,
        filename=file.filename,
        file_path=file_path,
        file_size_bytes=len(content),
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # Trigger background ingestion
    background_tasks.add_task(ingest_document, doc.id)

    return DocumentResponse.model_validate(doc)


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all documents (any authenticated user)."""
    result = await db.execute(select(Document).order_by(Document.uploaded_at.desc()))
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    """Delete a document and its chunks from Chroma."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from Chroma
    try:
        collection = get_collection()
        # Delete all chunks with this document_id
        collection.delete(where={"document_id": doc.id})
    except Exception:
        pass  # Chroma may not have entries if ingestion failed

    # Remove file from disk
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    # Remove from DB
    await db.delete(doc)
    return None
```

**Step 2: Register router in `main.py`**:
```python
from app.api.documents import router as documents_router
app.include_router(documents_router, prefix="/api")
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add document management API"
```

---

## Phase 3: Question Answering Pipeline

### Task 3.1: Question & Escalation Models

**Objective:** SQLAlchemy models for questions, answers, and escalations.

**Files:**
- Create: `backend/app/models/question.py`
- Create: `backend/app/models/escalation.py`

**Step 1: Create `backend/app/models/question.py`**

```python
"""Question and Answer models."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Enum, ForeignKey, Boolean
from app.db.database import Base


class QuestionStatus(str, enum.Enum):
    answered = "answered"
    escalated = "escalated"
    resolved = "resolved"  # escalation answered by engineer


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)  # null if escalated
    citations = Column(Text, nullable=True)  # JSON string of citation objects
    confidence_score = Column(Float, nullable=True)
    retrieval_score = Column(Float, nullable=True)
    llm_confidence = Column(Float, nullable=True)
    status = Column(Enum(QuestionStatus), nullable=False)
    asked_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    asked_at = Column(DateTime, default=datetime.utcnow)

    # Feedback
    feedback_positive = Column(Boolean, nullable=True)  # True=thumbs up, False=down, None=no feedback
    feedback_at = Column(DateTime, nullable=True)
```

**Step 2: Create `backend/app/models/escalation.py`**

```python
"""Escalation model — low-confidence questions sent to engineers."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, Text, DateTime, Enum, ForeignKey
from app.db.database import Base


class EscalationStatus(str, enum.Enum):
    pending = "pending"
    resolved = "resolved"


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, unique=True)
    retrieved_context = Column(Text, nullable=True)  # JSON: the chunks that were found
    engineer_response = Column(Text, nullable=True)
    responded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(EscalationStatus), default=EscalationStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add Question and Escalation models"
```

---

### Task 3.2: Retrieval Service

**Objective:** Query Chroma with embedded question, return top-K chunks with scores.

**Files:**
- Create: `backend/app/services/retrieval.py`

**Step 1: Create `backend/app/services/retrieval.py`**

```python
"""Retrieval service — query Chroma for relevant document chunks."""

from dataclasses import dataclass
from typing import List, Optional

from app.core.config import settings
from app.db.chroma_client import get_collection
from app.services.embedding import embed_query


@dataclass
class RetrievedChunk:
    text: str
    document_id: int
    document_title: str
    page_number: int
    chunk_index: int
    similarity_score: float  # cosine similarity (0-1, higher = better)


def retrieve_chunks(query: str, top_k: Optional[int] = None) -> List[RetrievedChunk]:
    """
    Embed query and retrieve top-K similar chunks from Chroma.

    Returns chunks sorted by similarity (highest first).
    """
    k = top_k or settings.top_k
    collection = get_collection()

    # Check if collection has any documents
    if collection.count() == 0:
        return []

    query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            # Chroma returns distances; for cosine, distance = 1 - similarity
            distance = results["distances"][0][i]
            similarity = 1.0 - distance  # Convert to similarity score

            metadata = results["metadatas"][0][i]
            chunks.append(RetrievedChunk(
                text=results["documents"][0][i],
                document_id=int(metadata.get("document_id", 0)),
                document_title=metadata.get("document_title", "Unknown"),
                page_number=int(metadata.get("page_number", 0)),
                chunk_index=int(metadata.get("chunk_index", 0)),
                similarity_score=max(0.0, min(1.0, similarity)),
            ))

    return sorted(chunks, key=lambda c: c.similarity_score, reverse=True)
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add retrieval service"
```

---

### Task 3.3: LLM Service (OpenRouter)

**Objective:** Call OpenRouter API with retrieved context and question, get answer with structured confidence score.

**Files:**
- Create: `backend/app/services/llm.py`

**Step 1: Create `backend/app/services/llm.py`**

```python
"""LLM service — call OpenRouter for answer generation with confidence scoring."""

import json
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.core.config import settings
from app.services.retrieval import RetrievedChunk

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are ACE (Assistant for Connector Engineering), a technical Q&A assistant for PEI-Genesis. You answer questions about electrical connectors and related engineering topics based ONLY on the provided context documents.

RULES:
1. Answer ONLY based on the provided context. Do not use external knowledge.
2. If the context does not contain enough information to answer confidently, say so.
3. Cite your sources using the document title and page number.
4. Be clear, conversational, and technically accurate.

You MUST respond in the following JSON format:
{
  "answer": "Your answer text here with inline citations like [Document Title, p.X]",
  "confidence": 0.85,
  "citations": [
    {
      "document_title": "Document Title",
      "page_number": 1,
      "excerpt": "Relevant excerpt from the source"
    }
  ]
}

The "confidence" field must be a float between 0.0 and 1.0 representing how confident you are that your answer is correct and complete based on the provided context. Use these guidelines:
- 0.9-1.0: Context directly and clearly answers the question
- 0.7-0.9: Context mostly answers the question with minor gaps
- 0.5-0.7: Context partially addresses the question
- 0.0-0.5: Context is insufficient or irrelevant
"""


@dataclass
class LLMResponse:
    answer: str
    confidence: float
    citations: List[dict]
    raw_response: Optional[str] = None


def _build_context(chunks: List[RetrievedChunk]) -> str:
    """Format retrieved chunks as context for the LLM."""
    if not chunks:
        return "No relevant documents found."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"--- Source {i}: {chunk.document_title} (Page {chunk.page_number}) ---\n"
            f"{chunk.text}\n"
        )
    return "\n".join(parts)


async def generate_answer(question: str, chunks: List[RetrievedChunk]) -> LLMResponse:
    """Send question + context to OpenRouter, parse structured response."""
    context = _build_context(chunks)

    user_message = f"""Context documents:
{context}

Question: {question}

Respond in the required JSON format with answer, confidence, and citations."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ace.pei-genesis.local",
                "X-Title": "ACE Q&A",
            },
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        )
        response.raise_for_status()

    data = response.json()
    raw_content = data["choices"][0]["message"]["content"]

    # Parse JSON response from LLM
    try:
        # Handle markdown code blocks if LLM wraps response
        content = raw_content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]  # remove first line
            content = content.rsplit("```", 1)[0]  # remove last ```
        parsed = json.loads(content)

        return LLMResponse(
            answer=parsed.get("answer", "I could not generate an answer."),
            confidence=float(parsed.get("confidence", 0.0)),
            citations=parsed.get("citations", []),
            raw_response=raw_content,
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Fallback: treat entire response as answer with low confidence
        return LLMResponse(
            answer=raw_content,
            confidence=0.3,
            citations=[],
            raw_response=raw_content,
        )
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add LLM service with OpenRouter integration"
```

---

### Task 3.4: Confidence Scoring Service

**Objective:** Combine retrieval similarity and LLM confidence into a single score.

**Files:**
- Create: `backend/app/services/confidence.py`

**Step 1: Create `backend/app/services/confidence.py`**

```python
"""Confidence scoring — combine retrieval and LLM confidence."""

from typing import List

from app.core.config import settings
from app.services.retrieval import RetrievedChunk


def compute_confidence(
    retrieval_chunks: List[RetrievedChunk],
    llm_confidence: float,
) -> tuple[float, float, float]:
    """
    Compute combined confidence score.

    Returns: (combined_score, retrieval_score, llm_score)
    """
    # Retrieval confidence: average similarity of top chunks
    if retrieval_chunks:
        retrieval_score = sum(c.similarity_score for c in retrieval_chunks) / len(retrieval_chunks)
    else:
        retrieval_score = 0.0

    # Weighted combination
    combined = (
        settings.retrieval_weight * retrieval_score
        + settings.llm_weight * llm_confidence
    )

    # Clamp to [0, 1]
    combined = max(0.0, min(1.0, combined))
    retrieval_score = max(0.0, min(1.0, retrieval_score))
    llm_confidence = max(0.0, min(1.0, llm_confidence))

    return combined, retrieval_score, llm_confidence


def is_above_threshold(combined_score: float) -> bool:
    """Check if confidence meets the threshold for direct answer."""
    return combined_score >= settings.confidence_threshold
```

**Step 2: Commit**
```bash
git add .
git commit -m "feat: add confidence scoring service"
```

---

### Task 3.5: Question API Endpoint

**Objective:** POST /questions — orchestrate the full Q&A pipeline. GET /questions — list question history.

**Files:**
- Create: `backend/app/api/questions.py`

**Step 1: Create `backend/app/api/questions.py`**

```python
"""Question API — submit questions, get answers, view history."""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.database import get_db
from app.models.question import Question, QuestionStatus
from app.models.escalation import Escalation, EscalationStatus
from app.models.user import User
from app.services.retrieval import retrieve_chunks
from app.services.llm import generate_answer
from app.services.confidence import compute_confidence, is_above_threshold

router = APIRouter(prefix="/questions", tags=["questions"])


class AskRequest(BaseModel):
    question: str


class CitationOut(BaseModel):
    document_title: str
    page_number: int
    excerpt: str


class QuestionResponse(BaseModel):
    id: int
    question_text: str
    answer_text: Optional[str]
    citations: Optional[List[CitationOut]]
    confidence_score: Optional[float]
    status: str
    asked_at: str
    feedback_positive: Optional[bool]
    engineer_response: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/", response_model=QuestionResponse)
async def ask_question(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a question. Returns answer or escalation status."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Step 1: Retrieve relevant chunks
    chunks = retrieve_chunks(body.question)

    # Step 2: Generate answer via LLM
    llm_response = await generate_answer(body.question, chunks)

    # Step 3: Compute confidence
    combined_score, retrieval_score, llm_conf = compute_confidence(
        chunks, llm_response.confidence
    )

    # Step 4: Determine status
    if is_above_threshold(combined_score):
        status = QuestionStatus.answered
        answer_text = llm_response.answer
        citations_json = json.dumps(llm_response.citations)
    else:
        status = QuestionStatus.escalated
        answer_text = None
        citations_json = None

    # Step 5: Save question
    question = Question(
        question_text=body.question,
        answer_text=answer_text,
        citations=citations_json,
        confidence_score=combined_score,
        retrieval_score=retrieval_score,
        llm_confidence=llm_conf,
        status=status,
        asked_by=current_user.id,
    )
    db.add(question)
    await db.flush()
    await db.refresh(question)

    # Step 6: Create escalation if needed
    if status == QuestionStatus.escalated:
        context_data = [
            {
                "text": c.text,
                "document_title": c.document_title,
                "page_number": c.page_number,
                "similarity": c.similarity_score,
            }
            for c in chunks
        ]
        escalation = Escalation(
            question_id=question.id,
            retrieved_context=json.dumps(context_data),
        )
        db.add(escalation)

    await db.commit()

    # Build response
    citations_out = None
    if citations_json:
        try:
            citations_out = [CitationOut(**c) for c in json.loads(citations_json)]
        except Exception:
            citations_out = []

    return QuestionResponse(
        id=question.id,
        question_text=question.question_text,
        answer_text=question.answer_text,
        citations=citations_out,
        confidence_score=question.confidence_score,
        status=question.status.value,
        asked_at=question.asked_at.isoformat(),
        feedback_positive=question.feedback_positive,
    )


@router.get("/", response_model=List[QuestionResponse])
async def list_questions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List question history. Sales users see only their own; engineers/admins see all."""
    from app.models.user import UserRole

    query = select(Question).order_by(Question.asked_at.desc())
    if current_user.role == UserRole.sales:
        query = query.where(Question.asked_by == current_user.id)

    result = await db.execute(query)
    questions = result.scalars().all()

    responses = []
    for q in questions:
        # Check for engineer response if escalated
        engineer_response = None
        if q.status == QuestionStatus.resolved:
            esc_result = await db.execute(
                select(Escalation).where(Escalation.question_id == q.id)
            )
            esc = esc_result.scalar_one_or_none()
            if esc:
                engineer_response = esc.engineer_response

        citations_out = None
        if q.citations:
            try:
                citations_out = [CitationOut(**c) for c in json.loads(q.citations)]
            except Exception:
                citations_out = []

        responses.append(QuestionResponse(
            id=q.id,
            question_text=q.question_text,
            answer_text=q.answer_text,
            citations=citations_out,
            confidence_score=q.confidence_score,
            status=q.status.value,
            asked_at=q.asked_at.isoformat(),
            feedback_positive=q.feedback_positive,
            engineer_response=engineer_response,
        ))

    return responses
```

**Step 2: Register router in `main.py`**:
```python
from app.api.questions import router as questions_router
app.include_router(questions_router, prefix="/api")
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add Q&A pipeline API"
```

---

## Phase 4: Escalation & Feedback

### Task 4.1: Escalation API Endpoints

**Objective:** Engineers can view pending escalations and submit responses. Responses are fed back into the knowledgebase.

**Files:**
- Create: `backend/app/api/escalations.py`

**Step 1: Create `backend/app/api/escalations.py`**

```python
"""Escalation API — view and respond to escalated questions."""

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.db.database import get_db
from app.db.chroma_client import get_collection
from app.models.escalation import Escalation, EscalationStatus
from app.models.question import Question, QuestionStatus
from app.models.user import User, UserRole
from app.services.embedding import embed_texts

router = APIRouter(prefix="/escalations", tags=["escalations"])


class EscalationResponse(BaseModel):
    id: int
    question_id: int
    question_text: str
    retrieved_context: Optional[List[dict]]
    asked_by_name: str
    status: str
    engineer_response: Optional[str]
    created_at: str
    resolved_at: Optional[str]


class RespondRequest(BaseModel):
    response: str


@router.get("/", response_model=List[EscalationResponse])
async def list_escalations(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles([UserRole.engineer, UserRole.admin])),
):
    """List escalations. Optionally filter by status (pending/resolved)."""
    query = select(Escalation).order_by(Escalation.created_at.desc())
    if status_filter:
        query = query.where(Escalation.status == status_filter)

    result = await db.execute(query)
    escalations = result.scalars().all()

    responses = []
    for esc in escalations:
        # Get the question
        q_result = await db.execute(select(Question).where(Question.id == esc.question_id))
        question = q_result.scalar_one_or_none()
        if not question:
            continue

        # Get the asking user's name
        from app.models.user import User as UserModel
        u_result = await db.execute(select(UserModel).where(UserModel.id == question.asked_by))
        asking_user = u_result.scalar_one_or_none()

        context = None
        if esc.retrieved_context:
            try:
                context = json.loads(esc.retrieved_context)
            except json.JSONDecodeError:
                context = []

        responses.append(EscalationResponse(
            id=esc.id,
            question_id=esc.question_id,
            question_text=question.question_text,
            retrieved_context=context,
            asked_by_name=asking_user.display_name if asking_user else "Unknown",
            status=esc.status.value,
            engineer_response=esc.engineer_response,
            created_at=esc.created_at.isoformat(),
            resolved_at=esc.resolved_at.isoformat() if esc.resolved_at else None,
        ))

    return responses


@router.post("/{escalation_id}/respond")
async def respond_to_escalation(
    escalation_id: int,
    body: RespondRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.engineer, UserRole.admin])),
):
    """Engineer responds to an escalation. Response is fed back into knowledgebase."""
    result = await db.execute(select(Escalation).where(Escalation.id == escalation_id))
    esc = result.scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if esc.status == EscalationStatus.resolved:
        raise HTTPException(status_code=400, detail="Escalation already resolved")

    # Get the original question
    q_result = await db.execute(select(Question).where(Question.id == esc.question_id))
    question = q_result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Associated question not found")

    # Update escalation
    esc.engineer_response = body.response
    esc.responded_by = current_user.id
    esc.status = EscalationStatus.resolved
    esc.resolved_at = datetime.utcnow()

    # Update question status
    question.status = QuestionStatus.resolved
    question.answer_text = body.response

    # Feed back into knowledgebase: store as a validated Q&A pair in Chroma
    qa_text = f"Q: {question.question_text}\nA: {body.response}"
    embedding = embed_texts([qa_text])

    collection = get_collection()
    collection.add(
        ids=[f"qa_escalation_{esc.id}"],
        embeddings=embedding,
        documents=[qa_text],
        metadatas=[{
            "document_id": -1,  # special: engineer-provided
            "document_title": "Engineer Q&A",
            "page_number": 0,
            "chunk_index": 0,
            "is_ocr": "False",
            "source": "escalation_response",
            "escalation_id": esc.id,
        }],
    )

    await db.commit()

    return {"message": "Response submitted and added to knowledgebase", "escalation_id": esc.id}
```

**Step 2: Register router in `main.py`**:
```python
from app.api.escalations import router as escalations_router
app.include_router(escalations_router, prefix="/api")
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add escalation API with knowledgebase feedback"
```

---

### Task 4.2: Feedback API Endpoint

**Objective:** Thumbs up/down on answers.

**Files:**
- Create: `backend/app/api/feedback.py`

**Step 1: Create `backend/app/api/feedback.py`**

```python
"""Feedback API — thumbs up/down on answers."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.database import get_db
from app.models.question import Question
from app.models.user import User

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    question_id: int
    positive: bool  # True = thumbs up, False = thumbs down


@router.post("/")
async def submit_feedback(
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit thumbs up/down feedback on an answer."""
    result = await db.execute(select(Question).where(Question.id == body.question_id))
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if question.asked_by != current_user.id:
        raise HTTPException(status_code=403, detail="Can only provide feedback on your own questions")

    question.feedback_positive = body.positive
    question.feedback_at = datetime.utcnow()
    await db.commit()

    return {"message": "Feedback recorded", "question_id": question.id, "positive": body.positive}
```

**Step 2: Register router in `main.py`**:
```python
from app.api.feedback import router as feedback_router
app.include_router(feedback_router, prefix="/api")
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add feedback API"
```

---

### Task 4.3: Analytics API Endpoint (Admin)

**Objective:** Basic analytics — question counts, escalation rates, feedback stats.

**Files:**
- Create: `backend/app/api/analytics.py`

**Step 1: Create `backend/app/api/analytics.py`**

```python
"""Analytics API — admin-only metrics."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.db.database import get_db
from app.models.document import Document
from app.models.question import Question, QuestionStatus
from app.models.escalation import Escalation, EscalationStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/")
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    """Return summary analytics."""
    # Total questions
    total_q = await db.execute(select(func.count(Question.id)))
    total_questions = total_q.scalar() or 0

    # Answered directly
    answered = await db.execute(
        select(func.count(Question.id)).where(Question.status == QuestionStatus.answered)
    )
    answered_count = answered.scalar() or 0

    # Escalated
    escalated = await db.execute(
        select(func.count(Question.id)).where(
            Question.status.in_([QuestionStatus.escalated, QuestionStatus.resolved])
        )
    )
    escalated_count = escalated.scalar() or 0

    # Pending escalations
    pending_esc = await db.execute(
        select(func.count(Escalation.id)).where(Escalation.status == EscalationStatus.pending)
    )
    pending_escalations = pending_esc.scalar() or 0

    # Feedback
    positive_fb = await db.execute(
        select(func.count(Question.id)).where(Question.feedback_positive == True)
    )
    positive_feedback = positive_fb.scalar() or 0

    negative_fb = await db.execute(
        select(func.count(Question.id)).where(Question.feedback_positive == False)
    )
    negative_feedback = negative_fb.scalar() or 0

    # Documents
    total_docs = await db.execute(select(func.count(Document.id)))
    document_count = total_docs.scalar() or 0

    # Users
    total_users = await db.execute(select(func.count(User.id)))
    user_count = total_users.scalar() or 0

    # Average confidence
    avg_conf = await db.execute(select(func.avg(Question.confidence_score)))
    avg_confidence = round(avg_conf.scalar() or 0, 3)

    return {
        "total_questions": total_questions,
        "answered_directly": answered_count,
        "escalated": escalated_count,
        "pending_escalations": pending_escalations,
        "escalation_rate": round(escalated_count / max(total_questions, 1), 3),
        "positive_feedback": positive_feedback,
        "negative_feedback": negative_feedback,
        "feedback_satisfaction_rate": round(
            positive_feedback / max(positive_feedback + negative_feedback, 1), 3
        ),
        "average_confidence": avg_confidence,
        "document_count": document_count,
        "user_count": user_count,
    }
```

**Step 2: Register router in `main.py`**:
```python
from app.api.analytics import router as analytics_router
app.include_router(analytics_router, prefix="/api")
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add analytics API"
```

---

### Task 4.4: Admin Config API (Model Swap)

**Objective:** Admin can view and update LLM model and confidence threshold at runtime without redeploying.

**Files:**
- Create: `backend/app/api/config.py`

**Step 1: Create `backend/app/api/config.py`**

```python
"""Config API — admin can view/update runtime settings."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_roles
from app.core.config import settings
from app.models.user import User, UserRole

router = APIRouter(prefix="/config", tags=["config"])


class ConfigResponse(BaseModel):
    llm_model: str
    confidence_threshold: float
    retrieval_top_k: int
    embedding_model: str


class ConfigUpdateRequest(BaseModel):
    llm_model: Optional[str] = None
    confidence_threshold: Optional[float] = None
    retrieval_top_k: Optional[int] = None


@router.get("/", response_model=ConfigResponse)
async def get_config(
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    return ConfigResponse(
        llm_model=settings.llm_model,
        confidence_threshold=settings.confidence_threshold,
        retrieval_top_k=settings.top_k,
        embedding_model=settings.embedding_model,
    )


@router.patch("/")
async def update_config(
    body: ConfigUpdateRequest,
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    """Update runtime config. Changes take effect immediately (in-memory only)."""
    updated = {}
    if body.llm_model is not None:
        settings.llm_model = body.llm_model
        updated["llm_model"] = body.llm_model
    if body.confidence_threshold is not None:
        settings.confidence_threshold = body.confidence_threshold
        updated["confidence_threshold"] = body.confidence_threshold
    if body.retrieval_top_k is not None:
        settings.top_k = body.retrieval_top_k
        updated["retrieval_top_k"] = body.retrieval_top_k

    return {"message": "Config updated", "changes": updated}
```

**Step 2: Register router in `main.py`**:
```python
from app.api.config import router as config_router
app.include_router(config_router, prefix="/api")
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add admin config API (model swap)"
```

---

## Phase 5: React Frontend

### Task 5.1: Initialize React Project

**Objective:** Create Vite + React + TailwindCSS project.

**Steps:**

```bash
cd ~/.hermes/ace/frontend
npm create vite@latest . -- --template react
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install axios react-router-dom lucide-react
```

Configure Tailwind in `vite.config.js`:
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

Update `src/index.css`:
```css
@import "tailwindcss";
```

**Commit:**
```bash
git add .
git commit -m "chore: initialize React frontend with Vite + Tailwind"
```

---

### Task 5.2: API Client & Auth Context

**Objective:** Create axios client and React auth context for managing login state.

**Files:**
- Create: `frontend/src/api/client.js`
- Create: `frontend/src/context/AuthContext.jsx`

**Step 1: Create `frontend/src/api/client.js`**

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,  // send httpOnly cookies
});

// Redirect to login on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
```

**Step 2: Create `frontend/src/context/AuthContext.jsx`**

```jsx
import { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if already authenticated
    api.get('/auth/me')
      .then(res => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    setUser(res.data.user);
    return res.data;
  };

  const logout = async () => {
    await api.post('/auth/logout');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
```

**Step 3: Commit**
```bash
git add .
git commit -m "feat: add API client and auth context"
```

---

### Task 5.3: App Router & Layout

**Objective:** Set up react-router with protected routes and role-based navigation.

**Files:**
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/components/Layout.jsx`
- Create: `frontend/src/components/ProtectedRoute.jsx`

**Step 1: Create `frontend/src/components/ProtectedRoute.jsx`**

```jsx
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children, allowedRoles }) {
  const { user, loading } = useAuth();

  if (loading) return <div className="flex justify-center p-8">Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" />;
  }
  return children;
}
```

**Step 2: Create `frontend/src/components/Layout.jsx`**

```jsx
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-xl font-bold text-blue-600">ACE</Link>
            <Link to="/" className="text-gray-600 hover:text-gray-900">Ask</Link>
            <Link to="/history" className="text-gray-600 hover:text-gray-900">History</Link>
            {(user?.role === 'engineer' || user?.role === 'admin') && (
              <>
                <Link to="/escalations" className="text-gray-600 hover:text-gray-900">Escalations</Link>
                <Link to="/documents" className="text-gray-600 hover:text-gray-900">Documents</Link>
              </>
            )}
            {user?.role === 'admin' && (
              <>
                <Link to="/users" className="text-gray-600 hover:text-gray-900">Users</Link>
                <Link to="/analytics" className="text-gray-600 hover:text-gray-900">Analytics</Link>
                <Link to="/settings" className="text-gray-600 hover:text-gray-900">Settings</Link>
              </>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{user?.display_name} ({user?.role})</span>
            <button onClick={handleLogout} className="text-sm text-red-600 hover:text-red-800">
              Logout
            </button>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
```

**Step 3: Update `frontend/src/App.jsx`**

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import AskPage from './pages/AskPage';
import HistoryPage from './pages/HistoryPage';
import EscalationsPage from './pages/EscalationsPage';
import DocumentsPage from './pages/DocumentsPage';
import UsersPage from './pages/UsersPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<AskPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="escalations" element={
              <ProtectedRoute allowedRoles={['engineer', 'admin']}><EscalationsPage /></ProtectedRoute>
            } />
            <Route path="documents" element={
              <ProtectedRoute allowedRoles={['engineer', 'admin']}><DocumentsPage /></ProtectedRoute>
            } />
            <Route path="users" element={
              <ProtectedRoute allowedRoles={['admin']}><UsersPage /></ProtectedRoute>
            } />
            <Route path="analytics" element={
              <ProtectedRoute allowedRoles={['admin']}><AnalyticsPage /></ProtectedRoute>
            } />
            <Route path="settings" element={
              <ProtectedRoute allowedRoles={['admin']}><SettingsPage /></ProtectedRoute>
            } />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

**Step 4: Commit**
```bash
git add .
git commit -m "feat: add router, layout, and protected routes"
```

---

### Task 5.4: Login Page

**Files:**
- Create: `frontend/src/pages/LoginPage.jsx`

```jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold text-center mb-2">ACE</h1>
        <p className="text-gray-500 text-center mb-6">Assistant for Connector Engineering</p>
        {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              type="text" value={username} onChange={(e) => setUsername(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              required autoFocus
            />
          </div>
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          <button
            type="submit" disabled={loading}
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
```

**Commit:**
```bash
git add .
git commit -m "feat: add login page"
```

---

### Task 5.5: Ask Question Page (Chat UI)

**Files:**
- Create: `frontend/src/pages/AskPage.jsx`

```jsx
import { useState } from 'react';
import { ThumbsUp, ThumbsDown, AlertTriangle, Send } from 'lucide-react';
import api from '../api/client';

export default function AskPage() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [feedbackGiven, setFeedbackGiven] = useState(false);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setResult(null);
    setFeedbackGiven(false);
    try {
      const res = await api.post('/questions/', { question: question.trim() });
      setResult(res.data);
    } catch (err) {
      setResult({ error: err.response?.data?.detail || 'Failed to get answer' });
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (positive) => {
    if (!result?.id || feedbackGiven) return;
    try {
      await api.post('/feedback/', { question_id: result.id, positive });
      setFeedbackGiven(true);
    } catch {
      // silent fail
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Ask a Question</h1>

      <form onSubmit={handleAsk} className="mb-8">
        <div className="flex gap-2">
          <input
            type="text" value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about connectors, specifications, compatibility..."
            className="flex-1 border rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button
            type="submit" disabled={loading || !question.trim()}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Send size={18} />
            {loading ? 'Thinking...' : 'Ask'}
          </button>
        </div>
      </form>

      {result && !result.error && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          {result.status === 'escalated' ? (
            <div className="flex items-center gap-3 text-amber-600">
              <AlertTriangle size={24} />
              <div>
                <p className="font-medium">Question Escalated</p>
                <p className="text-sm text-gray-500">
                  Your question has been sent to an engineer for review.
                  Check back later for a response.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="prose max-w-none mb-4">
                <p>{result.answer_text}</p>
              </div>

              {result.citations && result.citations.length > 0 && (
                <div className="border-t pt-4 mt-4">
                  <h3 className="text-sm font-medium text-gray-500 mb-2">Sources</h3>
                  {result.citations.map((cite, i) => (
                    <div key={i} className="text-sm bg-gray-50 rounded p-3 mb-2">
                      <span className="font-medium">{cite.document_title}</span>
                      <span className="text-gray-400"> — p.{cite.page_number}</span>
                      <p className="text-gray-600 mt-1 italic">"{cite.excerpt}"</p>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-4 mt-4 border-t pt-4">
                <span className="text-sm text-gray-500">Was this helpful?</span>
                <button
                  onClick={() => handleFeedback(true)}
                  disabled={feedbackGiven}
                  className={`p-2 rounded hover:bg-green-50 ${feedbackGiven ? 'opacity-50' : ''}`}
                >
                  <ThumbsUp size={18} className="text-green-600" />
                </button>
                <button
                  onClick={() => handleFeedback(false)}
                  disabled={feedbackGiven}
                  className={`p-2 rounded hover:bg-red-50 ${feedbackGiven ? 'opacity-50' : ''}`}
                >
                  <ThumbsDown size={18} className="text-red-600" />
                </button>
                {feedbackGiven && <span className="text-sm text-green-600">Thanks for the feedback!</span>}
              </div>
            </>
          )}
        </div>
      )}

      {result?.error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">{result.error}</div>
      )}
    </div>
  );
}
```

**Commit:**
```bash
git add .
git commit -m "feat: add Ask page with chat UI"
```

---

### Task 5.6: Question History Page

**Files:**
- Create: `frontend/src/pages/HistoryPage.jsx`

The history page shows all past questions with their status (answered/escalated/resolved), answers, and engineer responses. Standard list view with status badges, expandable answer sections, and feedback indicators.

**Commit:**
```bash
git add .
git commit -m "feat: add question history page"
```

---

### Task 5.7: Escalations Page (Engineer Dashboard)

**Files:**
- Create: `frontend/src/pages/EscalationsPage.jsx`

Shows pending and resolved escalations. Each escalation card displays the original question, retrieved context excerpts, the asking user's name, and a text area for the engineer to type a response. Submitting posts to `/api/escalations/{id}/respond`.

**Commit:**
```bash
git add .
git commit -m "feat: add escalations dashboard"
```

---

### Task 5.8: Documents Page

**Files:**
- Create: `frontend/src/pages/DocumentsPage.jsx`

Upload form (drag-and-drop or file picker for PDFs), document list with status (pending/processing/completed/failed), page count, chunk count, and delete button (admin only). Upload posts to `/api/documents/` as multipart form data.

**Commit:**
```bash
git add .
git commit -m "feat: add document management page"
```

---

### Task 5.9: Users Management Page (Admin)

**Files:**
- Create: `frontend/src/pages/UsersPage.jsx`

List of all users with role badges. Create user form (username, email, display name, password, role dropdown). Deactivate button per user. All calls via `/api/users/`.

**Commit:**
```bash
git add .
git commit -m "feat: add user management page"
```

---

### Task 5.10: Analytics Page (Admin)

**Files:**
- Create: `frontend/src/pages/AnalyticsPage.jsx`

Dashboard cards showing: total questions, direct answer rate, escalation rate, pending escalations, feedback satisfaction, average confidence, document count, user count. Simple stat cards — no charts in MVP.

**Commit:**
```bash
git add .
git commit -m "feat: add analytics dashboard"
```

---

### Task 5.11: Settings Page (Admin)

**Files:**
- Create: `frontend/src/pages/SettingsPage.jsx`

Form to view and update runtime config: LLM model (text input), confidence threshold (slider/number), retrieval top_k (number). Calls GET/PATCH `/api/config/`.

**Commit:**
```bash
git add .
git commit -m "feat: add settings page"
```

---

## Phase 6: Docker & Deployment

### Task 6.1: Backend Dockerfile

**Files:**
- Create: `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

# Install Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Commit:**
```bash
git add .
git commit -m "chore: add backend Dockerfile with Tesseract"
```

---

### Task 6.2: Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- Create: `frontend/nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API to backend
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 100M;
    }
}
```

**Commit:**
```bash
git add .
git commit -m "chore: add frontend Dockerfile with nginx"
```

---

### Task 6.3: Docker Compose

**Files:**
- Create: `docker-compose.yml`

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data/uploads:/app/uploads
      - ./data/chroma:/app/chroma_data
      - ./data/db:/app/db
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - ACE_SECRET_KEY=${APP_SECRET_KEY:-change-me-in-production}
      - ACE_DATABASE_URL=sqlite+aiosqlite:///./db/ace.db
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

- Create: `.env.example`

```
OPENROUTER_API_KEY=your-openrouter-api-key-here
APP_SECRET_KEY=generate-a-strong-random-secret-key
```

**Commit:**
```bash
git add .
git commit -m "chore: add Docker Compose config"
```

---

### Task 6.4: End-to-End Smoke Test

**Objective:** Verify the entire stack works: build containers, boot, login, upload a PDF, ask a question.

**Steps:**

```bash
cd ~/.hermes/ace

# Build and start
docker-compose up --build -d

# Wait for services
sleep 30

# Health check
curl http://localhost:8000/health

# Login as admin
curl -c cookies.txt -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'

# Upload a test PDF
curl -b cookies.txt -X POST http://localhost:8000/api/documents/ \
  -F "file=@test.pdf"

# Wait for ingestion
sleep 30

# Ask a question
curl -b cookies.txt -X POST http://localhost:8000/api/questions/ \
  -H "Content-Type: application/json" \
  -d '{"question":"What connectors are available?"}'

# Check analytics
curl -b cookies.txt http://localhost:8000/api/analytics/
```

**Commit:**
```bash
git add .
git commit -m "chore: end-to-end smoke test passed"
```

---

## Phase 7: Testing

### Task 7.1: Backend Unit Tests

**Files:**
- Create: `backend/tests/test_auth.py` — login/logout/me, role enforcement
- Create: `backend/tests/test_documents.py` — upload, list, delete
- Create: `backend/tests/test_questions.py` — ask, history, escalation trigger
- Create: `backend/tests/test_feedback.py` — thumbs up/down
- Create: `backend/tests/test_confidence.py` — scoring logic
- Create: `backend/tests/test_chunking.py` — hybrid chunking edge cases
- Create: `backend/tests/conftest.py` — test fixtures, in-memory DB, mock LLM

Each test file covers happy paths, edge cases, and permission enforcement. Use pytest-asyncio for async tests. Mock OpenRouter calls to avoid real API hits in tests.

**Run:**
```bash
cd backend
pytest tests/ -v --tb=short
```

**Commit:**
```bash
git add .
git commit -m "test: add backend unit tests"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 0 | 0.1–0.5 | Project scaffolding, config, DB, Chroma, FastAPI app |
| 1 | 1.1–1.6 | Auth, users, roles, JWT, seed admin |
| 2 | 2.1–2.6 | PDF extraction, OCR, chunking, embedding, ingestion pipeline, document API |
| 3 | 3.1–3.5 | Question/escalation models, retrieval, LLM, confidence, Q&A API |
| 4 | 4.1–4.4 | Escalation API, feedback, analytics, config API |
| 5 | 5.1–5.11 | React frontend — all pages and components |
| 6 | 6.1–6.4 | Dockerfiles, Docker Compose, smoke test |
| 7 | 7.1 | Unit tests |

**Total: ~30 tasks across 8 phases.**

**Estimated implementation time: 3-5 days with subagent-driven development.**

---

*Plan version: 1.0*
*Based on: ace-design-document.md v1.1*
*Created: 2026-04-08*
