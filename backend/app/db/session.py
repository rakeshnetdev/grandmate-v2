"""Async engine and session management.

The engine is built once per application and stored on ``app.state``, not as a module
global. A module-level engine would be shared across test applications and would hold
connections open between tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Build the async engine."""
    return create_async_engine(
        settings.url,
        echo=settings.db_echo_sql,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Recycle before typical idle-connection timeouts so a pooled connection that a
        # proxy has silently dropped is not handed to a request.
        pool_recycle=1800,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the session factory.

    ``expire_on_commit=False`` so objects stay usable after commit. Without it, reading
    any attribute post-commit triggers a lazy refresh, which raises in async code where
    implicit I/O is not allowed.
    """
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A transactional session scope.

    Commits on success, rolls back on any exception, always closes. Used by workers and
    scripts; request handlers get a session through the FastAPI dependency instead.
    """
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


__all__ = ["create_engine", "create_session_factory", "session_scope"]
