"""Postgres-backed checkpointer lifecycle (Phase 10, ADR-0005 short-term store).

Opened per chat turn, not held for the app's lifetime — the same per-request-resource
convention `DbSessionDep` already uses, and the only way to avoid a real database
connection attempt at every app startup regardless of whether a given request ever
touches chat at all (the same lesson `UnconfiguredLLMProvider` encodes for the LLM
provider: a feature's dependency must not become every route's problem). `.setup()` is
idempotent — its own `checkpoint_migrations` table tracks what has already been applied —
and cheap enough to call on every turn rather than caching a "did we already do this"
flag, the same "cheap enough to recompute" reasoning `ProfileAnalyticsService` already
uses for its own on-demand computation.

These tables are deliberately **not** an Alembic migration: they are library-internal
state, owned and versioned by `langgraph-checkpoint-postgres` itself. Pinning that DDL
into our own migration history would fight the library's own upgrade mechanism the next
time the installed package version changes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import DatabaseSettings


@asynccontextmanager
async def open_checkpointer(
    database_settings: DatabaseSettings,
) -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(
        database_settings.psycopg_conninfo
    ) as checkpointer:
        await checkpointer.setup()
        yield checkpointer


__all__ = ["open_checkpointer"]
