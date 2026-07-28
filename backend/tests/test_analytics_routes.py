"""HTTP-level analytics route tests: default/explicit window, window validation, and
that the response is scoped to the caller's own profile. Games are seeded directly
rather than run through a real import — computation correctness itself is
`test_analytics_service.py`'s job; these are about the HTTP contract.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.api.dependencies.storage import get_storage
from app.core.config import Settings
from app.db.models import Game, GameAnalysis, GameColor, GameSource, Profile, ProfileKind, User
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def analytics_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def analytics_client(
    analytics_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(analytics_settings)
    app.state.db_session_factory = None  # see test_import_routes.py's fixture docstring

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        client.headers["X-Test-Profile-Id"] = login.json()["profile"]["id"]
        yield client


async def _seed_analyzed_game(
    session: AsyncSession, profile_id: uuid.UUID, *, accuracy: float
) -> Game:
    game = Game(
        profile_id=profile_id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "A", "Black": "B", "Result": "1-0"},
        raw_pgn_path="pgn/test.pgn",
        canonicalized_at=datetime.now(UTC),
        focus_color=GameColor.WHITE,
    )
    session.add(game)
    await session.flush()
    session.add(
        GameAnalysis(
            game_id=game.id,
            analysis_version="test",
            engine_depth=12,
            summary={"total_moves": 1, "counts": {"best": 1}, "accuracy": accuracy},
        )
    )
    await session.flush()
    return game


class TestGetProfileAnalytics:
    async def test_defaults_to_the_configured_default_window(
        self, analytics_client: httpx.AsyncClient
    ) -> None:
        response = await analytics_client.get("/api/v1/analytics/profile")

        assert response.status_code == 200
        assert response.json()["window_size"] == 10

    async def test_accepts_an_explicit_allowed_window(
        self, analytics_client: httpx.AsyncClient
    ) -> None:
        response = await analytics_client.get("/api/v1/analytics/profile", params={"window": 30})

        assert response.status_code == 200
        assert response.json()["window_size"] == 30

    async def test_rejects_a_window_outside_the_configured_set(
        self, analytics_client: httpx.AsyncClient
    ) -> None:
        response = await analytics_client.get("/api/v1/analytics/profile", params={"window": 7})

        assert response.status_code == 422

    async def test_reflects_the_callers_own_games(
        self, analytics_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(analytics_client.headers["X-Test-Profile-Id"])
        await _seed_analyzed_game(db_session, profile_id, accuracy=95.0)

        response = await analytics_client.get("/api/v1/analytics/profile")

        assert response.status_code == 200
        body = response.json()
        assert body["games_included"] == 1
        assert body["accuracy"]["current"] == 95.0

    async def test_does_not_include_another_profiles_games(
        self, analytics_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User()
        db_session.add(other_user)
        await db_session.flush()
        other_profile = Profile(
            owner_user_id=other_user.id, kind=ProfileKind.SELF, display_name="Other"
        )
        db_session.add(other_profile)
        await db_session.flush()
        await _seed_analyzed_game(db_session, other_profile.id, accuracy=50.0)

        response = await analytics_client.get("/api/v1/analytics/profile")

        assert response.status_code == 200
        assert response.json()["games_included"] == 0
