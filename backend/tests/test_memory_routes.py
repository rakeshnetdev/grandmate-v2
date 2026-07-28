"""HTTP-level memory audit route tests: list and delete, profile scoping.
Write-path correctness (confidence floor, supersession) is `test_memory_service.py`'s
job; these are about the HTTP contract.
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
from app.core.config import Settings
from app.domain.memory import MemoryService
from app.integrations.platforms import PlatformClient, PlatformUser
from app.main import create_app
from app.orchestration.store import open_store


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def memory_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def memory_client(
    memory_settings: Settings, db_session: AsyncSession
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(memory_settings)
    app.state.db_session_factory = None

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        client.headers["X-Test-Profile-Id"] = login.json()["profile"]["id"]
        yield client


async def _seed_memory(
    session: AsyncSession, settings: Settings, profile_id: uuid.UUID, content: str
) -> uuid.UUID:
    async with open_store(settings.database) as store:
        service = MemoryService(session, store, settings.memory)
        [memory] = await service.write_candidate_memories(
            profile_id,
            [{"kind": "goal", "content": content, "confidence": 0.9}],
            source_thread_id=None,
        )
    return memory.id


class TestListMemories:
    async def test_lists_the_callers_memories(
        self, memory_client: httpx.AsyncClient, memory_settings: Settings, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(memory_client.headers["X-Test-Profile-Id"])
        await _seed_memory(db_session, memory_settings, profile_id, "Improve endgames")

        response = await memory_client.get("/api/v1/memory")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["content"] == "Improve endgames"
        assert body[0]["kind"] == "goal"
        assert body[0]["superseded_at"] is None

    async def test_empty_when_nothing_remembered_yet(
        self, memory_client: httpx.AsyncClient
    ) -> None:
        response = await memory_client.get("/api/v1/memory")

        assert response.status_code == 200
        assert response.json() == []


class TestDeleteMemory:
    async def test_deletes_an_owned_memory(
        self, memory_client: httpx.AsyncClient, memory_settings: Settings, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(memory_client.headers["X-Test-Profile-Id"])
        memory_id = await _seed_memory(db_session, memory_settings, profile_id, "Improve endgames")

        response = await memory_client.delete(f"/api/v1/memory/{memory_id}")

        assert response.status_code == 204
        listing = await memory_client.get("/api/v1/memory")
        assert listing.json() == []

    async def test_an_unknown_memory_is_not_found(self, memory_client: httpx.AsyncClient) -> None:
        response = await memory_client.delete(f"/api/v1/memory/{uuid.uuid4()}")

        assert response.status_code == 404
