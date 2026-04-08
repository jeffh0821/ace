"""Async SQLAlchemy database engine and session management."""

from sqlalchemy import select
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
