"""
Async SQLAlchemy engine and session factory.

Pool parameters follow the architectural mandate:
  pool_size=20  — baseline persistent connections
  max_overflow=10 — burst headroom (30 total)
  pool_recycle=3600 — reclaim stale connections every hour
  pool_pre_ping=True — discard dead connections before handing out
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── Engine ─────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=False,
    # Connection pool mandates
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    # asyncpg-specific: raise immediately instead of blocking forever
    connect_args={"command_timeout": 10},
)

# ── Session factory ─────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autobegin=True,
)


# ── ORM base ────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ── FastAPI dependency ──────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a transactional AsyncSession for each request.

    The session is automatically closed (and rolled back on unhandled
    exceptions) when the request context exits.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()