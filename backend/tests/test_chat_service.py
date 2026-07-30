"""`ChatService`: thread bookkeeping around the graph (Phase 10). Agent/grounding
correctness is `test_chat_graph.py`'s job — these tests cover ownership, title/timestamp
bookkeeping, and the 404-shaped `None` returns the routes turn into HTTP 404s.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Persona, Profile, ProfileKind, User
from app.domain.chat import ChatService
from app.domain.patterns import OpeningIndex
from app.integrations.llm import build_embedding_provider
from tests.fake_llm import FakeLLMProvider

_DIRECT_ANSWER = '{"answer": "A grounded answer.", "citations": []}'
# Every completed turn runs a `write_memory` extraction call after its answer.
_NO_MEMORIES = '{"memories": []}'


async def _make_profile(session: AsyncSession) -> Profile:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


def _service(session: AsyncSession, llm: FakeLLMProvider) -> ChatService:
    settings = Settings()
    return ChatService(
        session,
        settings,
        llm,
        build_embedding_provider(settings.llm, settings.retrieval),
        OpeningIndex({}),
    )


class TestCreateAndListThreads:
    async def test_a_new_thread_has_no_title(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        service = _service(db_session, FakeLLMProvider())

        thread = await service.create_thread(profile.id, active_game_id=None)

        assert thread.title is None
        assert thread.profile_id == profile.id

    async def test_listing_is_scoped_to_the_profile(self, db_session: AsyncSession) -> None:
        profile_a = await _make_profile(db_session)
        profile_b = await _make_profile(db_session)
        service = _service(db_session, FakeLLMProvider())
        await service.create_thread(profile_a.id, active_game_id=None)
        await service.create_thread(profile_b.id, active_game_id=None)

        threads_a = await service.list_threads(profile_a.id)

        assert len(threads_a) == 1
        assert threads_a[0].profile_id == profile_a.id


class TestSendMessage:
    async def test_returns_none_for_a_thread_from_another_profile(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_profile(db_session)
        other = await _make_profile(db_session)
        service = _service(db_session, FakeLLMProvider())
        thread = await service.create_thread(owner.id, active_game_id=None)

        result = await service.send_message(other.id, thread.id, Persona.SELF_LEARNER, "hi")

        assert result is None

    async def test_returns_none_for_an_unknown_thread(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        service = _service(db_session, FakeLLMProvider())

        result = await service.send_message(profile.id, uuid.uuid4(), Persona.SELF_LEARNER, "hi")

        assert result is None

    async def test_a_successful_turn_titles_the_thread_from_the_first_message(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        llm = FakeLLMProvider(responses=['{"intent": "explain"}', _DIRECT_ANSWER, _NO_MEMORIES])
        service = _service(db_session, llm)
        thread = await service.create_thread(profile.id, active_game_id=None)

        result = await service.send_message(
            profile.id, thread.id, Persona.SELF_LEARNER, "what is a fork?"
        )

        assert result is not None
        assert result.answer == "A grounded answer."
        assert result.grounded is True
        assert result.thread.title == "what is a fork?"

    async def test_a_second_message_does_not_overwrite_the_title(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        llm = FakeLLMProvider(
            responses=[
                '{"intent": "explain"}',
                _DIRECT_ANSWER,
                _NO_MEMORIES,
                '{"intent": "explain"}',
                _DIRECT_ANSWER,
                _NO_MEMORIES,
            ]
        )
        service = _service(db_session, llm)
        thread = await service.create_thread(profile.id, active_game_id=None)
        await service.send_message(profile.id, thread.id, Persona.SELF_LEARNER, "first question")

        result = await service.send_message(
            profile.id, thread.id, Persona.SELF_LEARNER, "second question"
        )

        assert result is not None
        assert result.thread.title == "first question"


class TestGetHistory:
    async def test_none_for_a_thread_from_another_profile(self, db_session: AsyncSession) -> None:
        owner = await _make_profile(db_session)
        other = await _make_profile(db_session)
        service = _service(db_session, FakeLLMProvider())
        thread = await service.create_thread(owner.id, active_game_id=None)

        history = await service.get_history(other.id, thread.id)

        assert history is None

    async def test_empty_for_a_thread_with_no_messages_yet(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        service = _service(db_session, FakeLLMProvider())
        thread = await service.create_thread(profile.id, active_game_id=None)

        history = await service.get_history(profile.id, thread.id)

        assert history == []

    async def test_contains_the_exchange_after_a_message(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        llm = FakeLLMProvider(responses=['{"intent": "explain"}', _DIRECT_ANSWER, _NO_MEMORIES])
        service = _service(db_session, llm)
        thread = await service.create_thread(profile.id, active_game_id=None)
        await service.send_message(profile.id, thread.id, Persona.SELF_LEARNER, "hello")

        history = await service.get_history(profile.id, thread.id)

        assert history == [
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "A grounded answer.",
                "citations": [],
                "grounded": True,
            },
        ]
