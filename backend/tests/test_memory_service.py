"""`MemoryService`: confidence-gated writes, supersession vs accumulation, delete, and
cross-profile isolation (Phase 11, ADR-0005, D-013, D-026).
"""

from __future__ import annotations

import uuid

from langgraph.store.memory import InMemoryStore
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MemorySettings
from app.db.models import MemoryKind, Profile, ProfileKind, User
from app.domain.memory import MemoryService, get_active_memories, get_all_memories


async def _make_profile(session: AsyncSession) -> Profile:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


def _service(session: AsyncSession, *, floor: float = 0.7) -> tuple[MemoryService, InMemoryStore]:
    store = InMemoryStore()
    return MemoryService(session, store, MemorySettings(memory_write_confidence_floor=floor)), store


class TestConfidenceFloor:
    async def test_a_candidate_below_the_floor_is_not_written(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        service, _store = _service(db_session, floor=0.7)

        written = await service.write_candidate_memories(
            profile.id,
            [{"kind": "goal", "content": "maybe endgames?", "confidence": 0.5}],
            source_thread_id=None,
        )

        assert written == []
        assert await get_active_memories(db_session, profile.id) == []

    async def test_a_candidate_at_or_above_the_floor_is_written(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        service, _store = _service(db_session, floor=0.7)

        written = await service.write_candidate_memories(
            profile.id,
            [{"kind": "goal", "content": "Wants to improve endgames", "confidence": 0.7}],
            source_thread_id=None,
        )

        assert len(written) == 1
        assert written[0].content == "Wants to improve endgames"


class TestSupersessionAndAccumulation:
    async def test_a_new_preference_supersedes_the_old_one(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        service, _store = _service(db_session)

        await service.write_candidate_memories(
            profile.id,
            [{"kind": "preference", "content": "Likes long explanations", "confidence": 0.9}],
            source_thread_id=None,
        )
        await service.write_candidate_memories(
            profile.id,
            [{"kind": "preference", "content": "Prefers short answers", "confidence": 0.9}],
            source_thread_id=None,
        )

        active = await get_active_memories(db_session, profile.id, kind=MemoryKind.PREFERENCE)
        all_entries = await get_all_memories(db_session, profile.id)

        assert [m.content for m in active] == ["Prefers short answers"]
        assert len(all_entries) == 2
        superseded = next(m for m in all_entries if m.content == "Likes long explanations")
        assert superseded.superseded_at is not None

    async def test_two_distinct_recurring_findings_both_stay_active(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        service, _store = _service(db_session)

        await service.write_candidate_memories(
            profile.id,
            [
                {
                    "kind": "recurring_finding",
                    "content": "Hangs pieces in time trouble",
                    "confidence": 0.9,
                }
            ],
            source_thread_id=None,
        )
        await service.write_candidate_memories(
            profile.id,
            [{"kind": "recurring_finding", "content": "Weak endgame technique", "confidence": 0.9}],
            source_thread_id=None,
        )

        active = await get_active_memories(
            db_session, profile.id, kind=MemoryKind.RECURRING_FINDING
        )

        assert {m.content for m in active} == {
            "Hangs pieces in time trouble",
            "Weak endgame technique",
        }

    async def test_an_exact_duplicate_recurring_finding_is_not_rewritten(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        service, _store = _service(db_session)
        candidate = [
            {
                "kind": "recurring_finding",
                "content": "Hangs pieces in time trouble",
                "confidence": 0.9,
            }
        ]

        await service.write_candidate_memories(profile.id, candidate, source_thread_id=None)
        second = await service.write_candidate_memories(
            profile.id, candidate, source_thread_id=None
        )

        assert second == []
        active = await get_active_memories(
            db_session, profile.id, kind=MemoryKind.RECURRING_FINDING
        )
        assert len(active) == 1


class TestDelete:
    async def test_delete_removes_from_postgres_and_the_store(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        service, store = _service(db_session)
        [memory] = await service.write_candidate_memories(
            profile.id,
            [{"kind": "goal", "content": "Improve endgames", "confidence": 0.9}],
            source_thread_id=None,
        )

        deleted = await service.delete_memory(profile.id, memory.id)

        assert deleted is True
        assert await get_all_memories(db_session, profile.id) == []
        assert await store.aget((str(profile.id), "goal"), str(memory.id)) is None

    async def test_delete_returns_false_for_an_unowned_memory(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_profile(db_session)
        other = await _make_profile(db_session)
        service, _store = _service(db_session)
        [memory] = await service.write_candidate_memories(
            owner.id,
            [{"kind": "goal", "content": "Improve endgames", "confidence": 0.9}],
            source_thread_id=None,
        )

        deleted = await service.delete_memory(other.id, memory.id)

        assert deleted is False
        assert await get_all_memories(db_session, owner.id) != []

    async def test_delete_returns_false_for_an_unknown_memory(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        service, _store = _service(db_session)

        assert await service.delete_memory(profile.id, uuid.uuid4()) is False


class TestCrossProfileIsolation:
    async def test_a_profiles_memories_are_invisible_to_another_profile(
        self, db_session: AsyncSession
    ) -> None:
        profile_a = await _make_profile(db_session)
        profile_b = await _make_profile(db_session)
        service, _store = _service(db_session)

        await service.write_candidate_memories(
            profile_a.id,
            [{"kind": "goal", "content": "Improve endgames", "confidence": 0.9}],
            source_thread_id=None,
        )

        assert await get_active_memories(db_session, profile_b.id) == []
        assert len(await get_active_memories(db_session, profile_a.id)) == 1
