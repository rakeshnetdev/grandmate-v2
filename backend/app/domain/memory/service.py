"""Long-term memory orchestration (Phase 11, ADR-0005, D-013, D-026).

Writes go to both stores every time — the LangGraph `AsyncPostgresStore` (what
`recall_memory` reads during a conversation) and the audited `long_term_memory` Postgres
table (what the audit UI reads and deletes from). ADR-0005 calls this dual write "the
deliberate extra cost" of the three-layer memory model; this service is where that cost
is paid, once, so nothing else in the codebase has to reason about keeping the two in
sync.

**Supersession policy, an intentional MVP simplification.** `preference` and `goal` are
treated as a single current value per profile — a new one supersedes whatever was
active, matching how a coach actually thinks about "what does this player want right
now" (not an accumulating list). `recurring_finding` accumulates instead — a player can
genuinely have several distinct recurring weaknesses at once — deduplicated only against
an exact (case-insensitive) repeat, so the same finding surfacing across many chat turns
doesn't clutter the audit list. A real semantic "does this update an existing entry"
judgment (e.g. two goals worded differently that mean the same thing) is deferred — D-013
named this exact class of decision as needing real chat behaviour to reason about first.
"""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.store.base import BaseStore
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MemorySettings
from app.db.base import utc_now
from app.db.models import LongTermMemory, MemoryKind
from app.domain.memory.queries import get_active_memories, get_all_memories, get_owned_memory


class MemoryService:
    def __init__(self, session: AsyncSession, store: BaseStore, settings: MemorySettings) -> None:
        self._session = session
        self._store = store
        self._settings = settings

    async def write_candidate_memories(
        self,
        profile_id: uuid.UUID,
        candidates: list[dict[str, Any]],
        *,
        source_thread_id: uuid.UUID | None,
    ) -> list[LongTermMemory]:
        """Persists every candidate that clears the confidence floor. Silent by design
        (D-026, confirmed with the owner): the floor, not a confirmation prompt, is what
        stands between a real preference and chat noise."""
        written: list[LongTermMemory] = []
        for candidate in candidates:
            confidence = float(candidate["confidence"])
            if confidence < self._settings.memory_write_confidence_floor:
                continue

            kind = MemoryKind(candidate["kind"])
            content = str(candidate["content"])
            existing = await get_active_memories(self._session, profile_id, kind=kind)

            if kind is MemoryKind.RECURRING_FINDING:
                if any(e.content.strip().lower() == content.strip().lower() for e in existing):
                    continue
            else:
                for entry in existing:
                    entry.superseded_at = utc_now()

            memory = LongTermMemory(
                profile_id=profile_id,
                kind=kind,
                content=content,
                confidence=confidence,
                source_thread_id=source_thread_id,
            )
            self._session.add(memory)
            await self._session.flush()
            await self._store.aput(
                (str(profile_id), kind.value),
                str(memory.id),
                {"content": content, "confidence": confidence},
            )
            written.append(memory)
        return written

    async def delete_memory(self, profile_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
        """A real delete, not a supersession — see the module docstring on why a
        user-initiated delete is a different guarantee than the system's own
        superseding. `False` if the memory does not exist or is not owned by
        `profile_id`."""
        memory = await get_owned_memory(self._session, memory_id, profile_id)
        if memory is None:
            return False
        await self._store.adelete((str(profile_id), memory.kind.value), str(memory.id))
        await self._session.delete(memory)
        await self._session.flush()
        return True

    async def list_memories(self, profile_id: uuid.UUID) -> list[LongTermMemory]:
        """Active and superseded — the full audit view."""
        return await get_all_memories(self._session, profile_id)


__all__ = ["MemoryService"]
