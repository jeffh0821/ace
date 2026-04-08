"""Shared test fixtures for ACE backend tests."""

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.models.question import Question, QuestionStatus
from app.core.security import hash_password

# In-memory test database
TEST_DATABASE_URL = "sqlite+aiosqlite://"

# Known passwords for test users
TEST_PASSWORD = "testpass123"


@pytest_asyncio.fixture
async def db_engine():
    """Create a fresh in-memory database engine for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Provide a database session bound to the test engine."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def seed_users(db_session):
    """Create admin, engineer, and sales test users. Return dict of users."""
    hashed = hash_password(TEST_PASSWORD)
    admin = User(
        username="testadmin",
        email="admin@test.local",
        display_name="Test Admin",
        password_hash=hashed,
        role=UserRole.admin,
    )
    engineer = User(
        username="testengineer",
        email="engineer@test.local",
        display_name="Test Engineer",
        password_hash=hashed,
        role=UserRole.engineer,
    )
    sales = User(
        username="testsales",
        email="sales@test.local",
        display_name="Test Sales",
        password_hash=hashed,
        role=UserRole.sales,
    )
    db_session.add_all([admin, engineer, sales])
    await db_session.commit()
    await db_session.refresh(admin)
    await db_session.refresh(engineer)
    await db_session.refresh(sales)
    return {"admin": admin, "engineer": engineer, "sales": sales}


@pytest_asyncio.fixture
async def client(db_session):
    """
    AsyncClient wired to the FastAPI app with:
    - In-memory SQLite database override
    - Mocked embedding service (avoids loading real model)
    - Mocked Chroma client
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Mock the embedding module to avoid loading the real sentence-transformers model
    with patch("app.services.embedding.get_embedding_model") as mock_get_model, \
         patch("app.services.embedding.embed_texts") as mock_embed_texts, \
         patch("app.services.embedding.embed_query") as mock_embed_query, \
         patch("app.db.chroma_client.get_chroma_client") as mock_chroma_client, \
         patch("app.db.chroma_client.get_collection") as mock_get_collection:

        # Fake embedding model
        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1] * 384]
        mock_get_model.return_value = mock_model

        # Fake embed functions
        mock_embed_texts.return_value = [[0.1] * 384]
        mock_embed_query.return_value = [0.1] * 384

        # Fake Chroma collection
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_collection.add.return_value = None
        mock_collection.delete.return_value = None
        mock_get_collection.return_value = mock_collection

        # Fake Chroma client
        mock_chroma = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection
        mock_chroma_client.return_value = mock_chroma

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


async def login_as(client: AsyncClient, username: str, password: str = TEST_PASSWORD) -> dict:
    """Helper: login and return cookies dict."""
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return dict(resp.cookies)


async def get_auth_cookies(client: AsyncClient, username: str, password: str = TEST_PASSWORD) -> dict:
    """Alias for login_as."""
    return await login_as(client, username, password)
