"""
Database — Async SQLAlchemy engine + session management
========================================================
WHY async: FastAPI is async. Sync DB driver blocks entire event loop.
WHY connection pooling: opening DB connection costs ~50ms. Pool reuses open ones.
WHY pre_ping: detects dead connections before using them (after DB restart).

CHANGE FROM v1: Removed run_migrations() from here.
Migration now runs in entrypoint.sh BEFORE Uvicorn starts.
This eliminates the race condition where 2 workers run migrations simultaneously.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger("ngonngon.db")

# =============================================================================
# Engine
# =============================================================================
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=settings.ENV == "development",
)

# =============================================================================
# Session Factory
# =============================================================================
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================================
# Base Model
# =============================================================================
class Base(DeclarativeBase):
    pass


# =============================================================================
# Dependency — inject session per request
# =============================================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    WHY dependency injection:
    - Each request gets its own session → transaction isolation
    - Session auto-closes after request → no connection leaks
    - Easy to mock in tests

    WHY pool_pre_ping (configured in engine above):
    - Detects stale connections before using them (e.g. after DB restart)
    - Eliminates most transient OperationalErrors at connection level
    - If DB is fully down, request will fail fast with clear error
    """
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
