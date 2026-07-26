"""Database session injection for routes.

The session factory lives on ``app.state``, built once in the application lifespan
(``app/main.py``), for the same reason settings do: a route must use the instance the
application was actually constructed with, not a module-level global that a test's
explicit ``create_app(settings)`` could silently bypass.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory
    return factory


async def get_db_session(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(_session_factory)],
) -> AsyncIterator[AsyncSession]:
    """A request-scoped session. Commits on success, rolls back on any exception.

    A route handler that raises ``HTTPException`` after writing to the session (an
    application error mid-flow) must not have the partial write committed anyway, so the
    rollback branch runs on every exception type, not just unhandled ones.
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


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]

__all__ = ["DbSessionDep", "get_db_session"]
