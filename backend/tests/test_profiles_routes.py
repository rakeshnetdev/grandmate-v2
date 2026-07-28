"""HTTP-level profile listing tests (Phase 8b, D-021, ADR-0016)."""

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
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def profiles_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def profiles_client(
    profiles_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(profiles_settings)
    app.state.db_session_factory = None

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestListMyProfiles:
    async def test_a_fresh_login_already_has_a_self_and_a_study_profile(
        self, profiles_client: httpx.AsyncClient
    ) -> None:
        login = await profiles_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        profiles_client.headers["X-Test-Profile-Id"] = login.json()["profile"]["id"]

        response = await profiles_client.get("/api/v1/profiles")

        assert response.status_code == 200
        body = response.json()
        kinds = {p["kind"] for p in body}
        assert kinds == {"self", "opponent"}
        # Self first, per list_profiles's contract.
        assert body[0]["kind"] == "self"
        assert body[0]["id"] == login.json()["profile"]["id"]

    async def test_the_study_profile_is_named_study_games(
        self, profiles_client: httpx.AsyncClient
    ) -> None:
        login = await profiles_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        profiles_client.headers["X-Test-Profile-Id"] = login.json()["profile"]["id"]

        response = await profiles_client.get("/api/v1/profiles")

        study = next(p for p in response.json() if p["kind"] == "opponent")
        assert study["display_name"] == "Study games"

    async def test_two_different_accounts_see_only_their_own_profiles(
        self, profiles_client: httpx.AsyncClient
    ) -> None:
        first_login = await profiles_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        profiles_client.headers["X-Test-Profile-Id"] = first_login.json()["profile"]["id"]
        first_response = await profiles_client.get("/api/v1/profiles")
        first_ids = {p["id"] for p in first_response.json()}

        second_login = await profiles_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "hikaru"}
        )
        profiles_client.headers["X-Test-Profile-Id"] = second_login.json()["profile"]["id"]
        second_response = await profiles_client.get("/api/v1/profiles")
        second_ids = {p["id"] for p in second_response.json()}

        assert first_ids.isdisjoint(second_ids)
