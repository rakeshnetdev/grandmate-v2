"""Database fixtures for integration tests.

Tests that need Postgres skip cleanly when it is not running, rather than failing. A
developer working on the analysis core should not need a database up to run the suite;
CI always has one, so coverage is not silently lost.

**Why schema setup uses a synchronous engine.** An async engine cached across tests holds
connections bound to the event loop that created them, while pytest-asyncio gives each
test a fresh loop — producing ``got Future attached to a different loop``. Doing the
once-per-session DDL synchronously sidesteps the problem entirely, and each test then
gets its own short-lived async engine with no pooling to outlive it.

**Why the test database is never the dev database.** This fixture drops every table it
manages at the start and end of the session. Pointed at the same database a developer
runs the app against, that would wipe their data on every ``pytest`` invocation — and it
did, silently, before this module picked its own database name: ``alembic_version``
(alembic's own bookkeeping table) is not part of ``Base.metadata``, so ``drop_all`` never
touches it, leaving it claiming the schema was current while every table under it was
gone. The default here is a same-server, differently-named database instead, created on
first use so a fresh checkout needs no manual setup step.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import DEFAULT_DATABASE_URL, DatabaseSettings
from app.db.base import Base

# Same server and credentials as dev, different database — see the module docstring for
# why this must never be ``DEFAULT_DATABASE_URL`` itself.
DEFAULT_TEST_DATABASE_URL = DEFAULT_DATABASE_URL.rsplit("/", 1)[0] + "/grandmate_test"


def database_url() -> str:
    """The URL under test.

    Read from the environment directly rather than through ``Settings``, because the
    hermetic settings fixture deliberately strips every declared variable — including
    this one.
    """
    return os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL


def _ensure_database_exists(sync_url: str) -> None:
    """Create the target database if it does not exist yet.

    Connects to the server's default ``postgres`` maintenance database to issue
    ``CREATE DATABASE`` — a database cannot be created from within a connection to
    itself. ``AUTOCOMMIT`` because ``CREATE DATABASE`` cannot run inside a transaction.
    """
    url = make_url(sync_url)
    db_name = url.database
    admin_engine = create_sync_engine(
        url.set(database="postgres"), poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def db_schema() -> Iterator[str]:
    """Create the schema once per session, synchronously. Yields the async URL."""
    url = database_url()
    sync_url = DatabaseSettings(database_url=url).sync_url  # type: ignore[arg-type]

    try:
        _ensure_database_exists(sync_url)
    except Exception:
        pytest.skip("Postgres not reachable — start it with `docker compose up -d postgres`")

    engine = create_sync_engine(sync_url, poolclass=NullPool)

    # `create_all` builds tables straight from `Base.metadata`, bypassing Alembic
    # entirely — so, unlike a real deployment, nothing here has already run the
    # `CREATE EXTENSION IF NOT EXISTS vector` statement the knowledge-corpus migration
    # carries (Phase 7). Without it, every `Vector(...)` column fails with
    # `type "vector" does not exist` the moment `create_all` reaches it.
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    yield url

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest_asyncio.fixture
async def db_engine(db_schema: str) -> AsyncIterator[AsyncEngine]:
    """A per-test async engine.

    ``NullPool`` because the engine lives for one test: pooling would keep connections
    open past the event loop that created them.
    """
    engine = create_async_engine(db_schema, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is always rolled back.

    Each test sees a clean database without paying to recreate the schema, and no test
    can leak rows into another.

    ``join_transaction_mode="create_savepoint"`` matters as of Phase 7: routes that call
    ``session.commit()`` directly (the fix for the Phase 5 background-job race) would
    otherwise commit *this* connection's outer transaction the moment a route under test
    does that — ending the "always rolled back" guarantee mid-test. In savepoint mode, an
    inner ``session.commit()`` only releases a SAVEPOINT and a new one opens immediately;
    the outer transaction started by ``connection.begin()`` below is never touched, so
    rollback at teardown still discards everything regardless of what routes commit.
    """
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            # Tests that assert on IntegrityError leave the transaction already aborted
            # and deassociated, so rolling back unconditionally raises during teardown
            # and masks the real result. Only roll back what is still live.
            if transaction.is_active:
                await transaction.rollback()
