"""HTTP-level tests for `ScopedProfileIdDep` (Phase 8b, D-021, ADR-0016) — exercised
through the `/games` route, since every route using the dependency shares this exact
behaviour by construction. `test_import_routes_profile_routing.py` and the per-feature
route test files each carry one smoke test confirming their own route actually passes
`profile_id` through, rather than repeating this full matrix per route.
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
def scope_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def scope_client(
    scope_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(scope_settings)
    app.state.db_session_factory = None

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestScopedProfileId:
    async def test_defaults_to_the_callers_self_profile(
        self, scope_client: httpx.AsyncClient
    ) -> None:
        await scope_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )

        # An empty list either way, but a 200 (not a 404/422) confirms the dependency
        # resolved successfully with no `profile_id` query param supplied.
        response = await scope_client.get("/api/v1/games")
        assert response.status_code == 200

    async def test_accepts_the_callers_own_study_profile_id(
        self, scope_client: httpx.AsyncClient
    ) -> None:
        await scope_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        profiles = (await scope_client.get("/api/v1/profiles")).json()
        study_id = next(p["id"] for p in profiles if p["kind"] == "opponent")

        response = await scope_client.get("/api/v1/games", params={"profile_id": study_id})

        assert response.status_code == 200

    async def test_rejects_a_profile_id_the_caller_does_not_own(
        self, scope_client: httpx.AsyncClient
    ) -> None:
        await scope_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        other_login = await scope_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "hikaru"}
        )
        other_profile_id = other_login.json()["profile"]["id"]
        # Back to being logged in as magnus for the actual request.
        await scope_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )

        response = await scope_client.get("/api/v1/games", params={"profile_id": other_profile_id})

        assert response.status_code == 404

    async def test_rejects_a_profile_id_that_does_not_exist(
        self, scope_client: httpx.AsyncClient
    ) -> None:
        await scope_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )

        response = await scope_client.get("/api/v1/games", params={"profile_id": str(uuid.uuid4())})

        assert response.status_code == 404
