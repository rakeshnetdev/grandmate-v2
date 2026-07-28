"""Long-term memory audit: list and delete (Phase 11, ADR-0005).

Thin per the "routes delegate" rule. `profile_id` scoping follows every other
profile-scoped route's exact pattern (`ScopedProfileIdDep`, Phase 8b). The store is
opened directly in each handler, the same per-request-not-per-app lifecycle
`ChatService` uses (`orchestration/store.py`) — there is no FastAPI dependency for it
because nothing outside a request that actually touches memory should pay for a
connection attempt.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.profile_scope import ScopedProfileIdDep
from app.api.dependencies.settings import SettingsDep
from app.db.models import LongTermMemory
from app.domain.memory import MemoryService, get_all_memories
from app.orchestration.store import open_store
from app.schemas.memory import MemoryOut

router = APIRouter(prefix="/memory", tags=["memory"])


def _to_out(memory: LongTermMemory) -> MemoryOut:
    return MemoryOut(
        id=memory.id,
        kind=memory.kind.value,
        content=memory.content,
        confidence=memory.confidence,
        source_thread_id=memory.source_thread_id,
        created_at=memory.created_at,
        superseded_at=memory.superseded_at,
    )


@router.get("", response_model=list[MemoryOut])
async def list_memories(profile_id: ScopedProfileIdDep, session: DbSessionDep) -> list[MemoryOut]:
    """Active and superseded — the full audit view (ADR-0005: a wrong memory stays
    traceable, not hidden)."""
    memories = await get_all_memories(session, profile_id)
    return [_to_out(m) for m in memories]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> None:
    async with open_store(settings.database) as store:
        service = MemoryService(session, store, settings.memory)
        deleted = await service.delete_memory(profile_id, memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")


__all__ = ["router"]
