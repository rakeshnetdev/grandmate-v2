"""HTTP-level confirmation that `POST /imports` actually routes games between the
caller's own SELF profile and their study profile (Phase 8b, D-021, ADR-0016) — the
unit-level routing logic itself is `test_import_service_profile_routing.py`'s job; this
is about the real request path wiring it correctly end to end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.api.dependencies.storage import get_storage
from app.core.config import Settings
from app.domain.patterns import load_opening_index
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app

OWN_GAME = """[Event "Test"]
[White "magnus"]
[Black "SomeOpponent"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0
"""

UNOWNED_GAME = """[Event "Test"]
[White "Carlsen,Magnus"]
[Black "Nilssen,J"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture(autouse=True)
def _stub_analysis_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.api.routes.imports.run_pending_analysis_jobs", _noop)


@pytest.fixture
def routing_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def routing_client(
    routing_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(routing_settings)
    app.state.db_session_factory = None
    app.state.opening_index = load_opening_index(routing_settings.patterns)

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"})
        yield client


class TestImportProfileRouting:
    async def test_a_batch_splits_across_self_and_study_via_the_real_request(
        self, routing_client: httpx.AsyncClient
    ) -> None:
        response = await routing_client.post(
            "/api/v1/imports", data={"pgn_text": OWN_GAME + "\n" + UNOWNED_GAME}
        )
        assert response.status_code == 201
        assert response.json()["progress"]["imported"] == 2

        profiles = (await routing_client.get("/api/v1/profiles")).json()
        study_id = next(p["id"] for p in profiles if p["kind"] == "opponent")

        self_games = (await routing_client.get("/api/v1/games")).json()
        study_games = (
            await routing_client.get("/api/v1/games", params={"profile_id": study_id})
        ).json()

        assert len(self_games) == 1
        assert self_games[0]["headers"]["White"] == "magnus"
        assert len(study_games) == 1
        assert study_games[0]["headers"]["White"] == "Carlsen,Magnus"
