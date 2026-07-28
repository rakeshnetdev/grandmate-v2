"""Read-side lookups for chat threads (Phase 10).

Same split as `domain/analysis/queries.py`: a different responsibility and lifecycle
than `ChatService`, which also runs the agent — this module only ever reads
`chat_threads`, the identity/listing row (see `db/models/chat.py`'s docstring for why
message history itself is not here).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatThread


async def get_owned_thread(
    session: AsyncSession, thread_id: uuid.UUID, profile_id: uuid.UUID
) -> ChatThread | None:
    """A thread the profile owns, or `None` — a thread id that exists but belongs to a
    different profile 404s the same as one that doesn't exist at all, same pattern
    `domain.profiles.get_owned_profile` already established."""
    result = await session.execute(
        select(ChatThread).where(ChatThread.id == thread_id, ChatThread.profile_id == profile_id)
    )
    return result.scalar_one_or_none()


async def list_threads_for_profile(
    session: AsyncSession, profile_id: uuid.UUID
) -> list[ChatThread]:
    """Most recently active first — `updated_at` is bumped on every message, not just
    thread creation (see `ChatService.send_message`)."""
    result = await session.execute(
        select(ChatThread)
        .where(ChatThread.profile_id == profile_id)
        .order_by(ChatThread.updated_at.desc())
    )
    return list(result.scalars().all())


__all__ = ["get_owned_thread", "list_threads_for_profile"]
