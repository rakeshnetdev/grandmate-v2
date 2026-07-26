"""HTTP-level auth route tests: login, me, logout.

The app is built with a real database session (the transactional ``db_session`` fixture,
rolled back after the test) rather than the app's own pooled engine — ``get_db_session``
is overridden to hand the route the same session the test uses to assert on. The platform
lookup is monkeypatched so no test reaches Lichess or Chess.com over the network.

**Why ``httpx.AsyncClient`` over ``fastapi.testclient.TestClient``.** ``TestClient`` drives
the ASGI app from a background thread with its own event loop. ``db_session`` is a
connection bound to *this* test's event loop (pytest-asyncio), so a request executed on a
different loop hits asyncpg's "Future attached to a different loop" error the moment a
route tries to use it. Running requests as coroutines on the same loop as the fixture
avoids the mismatch entirely — the same reason ``db_fixtures.py`` gives each test its own
async engine rather than sharing one across loops.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.core.config import Settings
from app.domain.auth import COOKIE_NAME
from app.integrations.platforms import PlatformClient, PlatformUser, UserNotFoundError
from app.main import create_app


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    if username.lower() == "missing":
        raise UserNotFoundError(f"No such user: {username!r}")
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def auth_settings() -> Settings:
    settings = Settings()
    # A real secret is required to issue a session token; the hermetic default is blank.
    # 32+ bytes so HS256 does not raise InsecureKeyLengthWarning (fatal under this suite's
    # filterwarnings=error).
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def auth_client(
    auth_settings: Settings, db_session: AsyncSession
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(auth_settings)

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestLogin:
    async def test_login_creates_an_account_and_sets_the_session_cookie(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "lichess"
        assert body["username"] == "magnus"
        assert body["verified"] is False
        assert body["profile"]["kind"] == "self"
        assert COOKIE_NAME in response.cookies

    async def test_login_rejects_a_username_the_platform_does_not_know(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login", json={"provider": "chesscom", "username": "missing"}
        )

        assert response.status_code == 404

    async def test_login_rejects_a_blank_username(self, auth_client: httpx.AsyncClient) -> None:
        response = await auth_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "   "}
        )

        assert response.status_code == 422


class TestMe:
    async def test_me_without_a_session_is_unauthorized(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        response = await auth_client.get("/api/v1/auth/me")

        assert response.status_code == 401

    async def test_me_after_login_returns_the_same_identity(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        login_response = await auth_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        login_body = login_response.json()

        me_response = await auth_client.get("/api/v1/auth/me")

        assert me_response.status_code == 200
        assert me_response.json()["id"] == login_body["id"]
        assert me_response.json()["username"] == "magnus"

    async def test_me_with_a_tampered_cookie_is_unauthorized(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        auth_client.cookies.set(COOKIE_NAME, "not-a-real-token")

        response = await auth_client.get("/api/v1/auth/me")

        assert response.status_code == 401


class TestLogout:
    async def test_logout_clears_the_session_so_me_becomes_unauthorized(
        self, auth_client: httpx.AsyncClient
    ) -> None:
        await auth_client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )

        logout_response = await auth_client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 204

        me_response = await auth_client.get("/api/v1/auth/me")
        assert me_response.status_code == 401
