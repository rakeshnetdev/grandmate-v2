"""HTTP-level chat route tests: thread creation, listing, sending a message, and
history. `get_llm_provider` is overridden with `FakeLLMProvider` so no real network call
happens — generation/grounding correctness is `test_chat_graph.py`'s and
`test_chat_guardrail.py`'s job; these are about the HTTP contract and profile scoping.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.api.dependencies.llm import get_embedding_provider, get_llm_provider
from app.api.dependencies.patterns import get_opening_index
from app.api.dependencies.storage import get_storage
from app.core.config import Settings
from app.db.models import Game, GameSource, Profile, ProfileKind, User
from app.domain.patterns import OpeningIndex
from app.integrations.llm import UnconfiguredEmbeddingProvider
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app
from tests.fake_llm import FakeLLMProvider

_DIRECT_ANSWER = '{"answer": "A grounded answer.", "citations": []}'


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def chat_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def chat_client(
    chat_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(chat_settings)
    app.state.db_session_factory = None

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
    # A generous, reusable script: intent + answer pairs for several turns across a test.
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(
        responses=['{"intent": "explain"}', _DIRECT_ANSWER] * 5
    )
    # No tool call is scripted in any test here, so the embedding provider is never
    # actually invoked — the stand-in just needs to exist for dependency resolution.
    app.dependency_overrides[get_embedding_provider] = lambda: UnconfiguredEmbeddingProvider()
    app.dependency_overrides[get_opening_index] = lambda: OpeningIndex({})

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        client.headers["X-Test-Profile-Id"] = login.json()["profile"]["id"]
        yield client


class TestCreateThread:
    async def test_creates_a_thread_with_no_game(self, chat_client: httpx.AsyncClient) -> None:
        response = await chat_client.post("/api/v1/chat/threads", json={})

        assert response.status_code == 201
        body = response.json()
        assert body["active_game_id"] is None
        assert body["title"] is None

    async def test_a_game_owned_by_another_profile_is_not_found(
        self, chat_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User()
        db_session.add(other_user)
        await db_session.flush()
        other_profile = Profile(
            owner_user_id=other_user.id, kind=ProfileKind.SELF, display_name="Someone Else"
        )
        db_session.add(other_profile)
        await db_session.flush()
        other_game = Game(
            profile_id=other_profile.id,
            source=GameSource.UPLOAD,
            content_hash=str(uuid.uuid4()),
            headers={},
            raw_pgn_path="pgn/test.pgn",
        )
        db_session.add(other_game)
        await db_session.flush()

        response = await chat_client.post(
            "/api/v1/chat/threads", json={"active_game_id": str(other_game.id)}
        )

        assert response.status_code == 404


class TestListThreads:
    async def test_lists_only_the_callers_own_threads(self, chat_client: httpx.AsyncClient) -> None:
        await chat_client.post("/api/v1/chat/threads", json={})
        await chat_client.post("/api/v1/chat/threads", json={})

        response = await chat_client.get("/api/v1/chat/threads")

        assert response.status_code == 200
        assert len(response.json()) == 2


class TestSendMessage:
    async def test_returns_a_grounded_answer(self, chat_client: httpx.AsyncClient) -> None:
        created = await chat_client.post("/api/v1/chat/threads", json={})
        thread_id = created.json()["id"]

        response = await chat_client.post(
            f"/api/v1/chat/threads/{thread_id}/messages", json={"message": "what is a fork?"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "A grounded answer."
        assert body["grounded"] is True
        assert body["thread"]["title"] == "what is a fork?"

    async def test_an_unknown_thread_is_not_found(self, chat_client: httpx.AsyncClient) -> None:
        response = await chat_client.post(
            f"/api/v1/chat/threads/{uuid.uuid4()}/messages", json={"message": "hi"}
        )

        assert response.status_code == 404

    async def test_an_empty_message_is_rejected(self, chat_client: httpx.AsyncClient) -> None:
        created = await chat_client.post("/api/v1/chat/threads", json={})
        thread_id = created.json()["id"]

        response = await chat_client.post(
            f"/api/v1/chat/threads/{thread_id}/messages", json={"message": ""}
        )

        assert response.status_code == 422


class TestGetThreadHistory:
    async def test_returns_the_transcript_after_a_message(
        self, chat_client: httpx.AsyncClient
    ) -> None:
        created = await chat_client.post("/api/v1/chat/threads", json={})
        thread_id = created.json()["id"]
        await chat_client.post(
            f"/api/v1/chat/threads/{thread_id}/messages", json={"message": "hello"}
        )

        response = await chat_client.get(f"/api/v1/chat/threads/{thread_id}")

        assert response.status_code == 200
        messages = response.json()["messages"]
        assert messages == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "A grounded answer."},
        ]

    async def test_an_unknown_thread_is_not_found(self, chat_client: httpx.AsyncClient) -> None:
        response = await chat_client.get(f"/api/v1/chat/threads/{uuid.uuid4()}")

        assert response.status_code == 404
