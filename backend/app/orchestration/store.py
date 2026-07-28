"""Postgres-backed long-term memory store lifecycle (Phase 11, ADR-0005 long-term store).

The cross-thread counterpart to `orchestration/checkpointer.py`'s thread-scoped
checkpointer — same package (`langgraph-checkpoint-postgres`), same per-call-not-per-app
lifecycle, same reasoning for why its tables (`store`, `store_migrations`, ...) are
deliberately not an Alembic migration. See that module's docstring; it applies here
unchanged.

`recall_memory` (the chat tool) is this store's only reader; `MemoryService` is its only
writer. The audited Postgres mirror — `long_term_memory`, a normal Alembic-owned table —
is what the audit UI reads and deletes from; the two are written together
(`MemoryService.write_candidate_memories`) but never read from each other's storage.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.store.postgres.aio import AsyncPostgresStore

from app.core.config import DatabaseSettings


@asynccontextmanager
async def open_store(database_settings: DatabaseSettings) -> AsyncIterator[AsyncPostgresStore]:
    async with AsyncPostgresStore.from_conn_string(database_settings.psycopg_conninfo) as store:
        await store.setup()
        yield store


__all__ = ["open_store"]
