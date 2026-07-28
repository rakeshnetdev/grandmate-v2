"""Read-side lookups for long-term memory (Phase 11).

Same split as `domain/chat/queries.py`: a different responsibility and lifecycle than
`MemoryService`, which also writes and deletes.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LongTermMemory, MemoryKind


async def get_active_memories(
    session: AsyncSession, profile_id: uuid.UUID, *, kind: MemoryKind | None = None
) -> list[LongTermMemory]:
    """Every currently-active (non-superseded) memory for a profile — what the chat
    agent's `recall_memory` tool and the audit UI both ultimately read, though the audit
    UI also wants superseded entries (see `get_all_memories`) and the tool never does."""
    query = select(LongTermMemory).where(
        LongTermMemory.profile_id == profile_id, LongTermMemory.superseded_at.is_(None)
    )
    if kind is not None:
        query = query.where(LongTermMemory.kind == kind)
    result = await session.execute(query.order_by(LongTermMemory.created_at.desc()))
    return list(result.scalars().all())


async def get_all_memories(session: AsyncSession, profile_id: uuid.UUID) -> list[LongTermMemory]:
    """Active and superseded — the audit view. A superseded entry is not hidden: the
    entire point of superseding rather than deleting is that a wrong memory stays
    traceable (ADR-0005), which requires the audit surface to actually show it."""
    result = await session.execute(
        select(LongTermMemory)
        .where(LongTermMemory.profile_id == profile_id)
        .order_by(LongTermMemory.created_at.desc())
    )
    return list(result.scalars().all())


async def get_owned_memory(
    session: AsyncSession, memory_id: uuid.UUID, profile_id: uuid.UUID
) -> LongTermMemory | None:
    """A memory the profile owns, or `None` — a memory id that exists but belongs to a
    different profile 404s the same as one that doesn't exist, same pattern every other
    profile-scoped resource in this codebase follows."""
    result = await session.execute(
        select(LongTermMemory).where(
            LongTermMemory.id == memory_id, LongTermMemory.profile_id == profile_id
        )
    )
    return result.scalar_one_or_none()


__all__ = ["get_active_memories", "get_all_memories", "get_owned_memory"]
