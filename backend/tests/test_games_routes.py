"""HTTP-level game route tests: list, get, profile scoping. Same pattern as
`test_pattern_routes.py`: real transactional `db_session`, `get_db_session` overridden,
games seeded directly rather than run through a real import — these are about the HTTP
contract over already-seeded rows, not about ingestion itself (covered by
`test_import_routes.py`/`test_import_service.py`).
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
from app.db.models import Game, GameSource, Profile, ProfileKind, User
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def games_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def games_client(
    games_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(games_settings)
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


async def _seed_game(
    session: AsyncSession, profile_id: uuid.UUID, *, canonicalized: bool = True
) -> Game:
    game = Game(
        profile_id=profile_id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "Alice", "Black": "Bob", "Result": "1-0"},
        raw_pgn_path="pgn/test.pgn",
        canonicalized_at=datetime.now(UTC) if canonicalized else None,
    )
    session.add(game)
    await session.flush()
    return game


class TestListMyGames:
    async def test_no_games_yet_returns_empty_list(self, games_client: httpx.AsyncClient) -> None:
        response = await games_client.get("/api/v1/games")

        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_the_callers_games_most_recent_first(
        self, games_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(games_client.headers["X-Test-Profile-Id"])
        first = await _seed_game(db_session, profile_id)
        second = await _seed_game(db_session, profile_id)

        response = await games_client.get("/api/v1/games")

        assert response.status_code == 200
        ids = [game["id"] for game in response.json()]
        assert ids == [str(second.id), str(first.id)]

    async def test_does_not_include_another_profiles_games(
        self, games_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User()
        db_session.add(other_user)
        await db_session.flush()
        other_profile = Profile(
            owner_user_id=other_user.id, kind=ProfileKind.SELF, display_name="Other"
        )
        db_session.add(other_profile)
        await db_session.flush()
        await _seed_game(db_session, other_profile.id)

        response = await games_client.get("/api/v1/games")

        assert response.status_code == 200
        assert response.json() == []


class TestGetMyGame:
    async def test_returns_the_game(
        self, games_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(games_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)

        response = await games_client.get(f"/api/v1/games/{game.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(game.id)
        assert body["headers"] == {"White": "Alice", "Black": "Bob", "Result": "1-0"}
        assert body["canonicalized_at"] is not None

    async def test_a_game_that_failed_canonicalization_still_has_a_null_flag(
        self, games_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(games_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id, canonicalized=False)

        response = await games_client.get(f"/api/v1/games/{game.id}")

        assert response.status_code == 200
        assert response.json()["canonicalized_at"] is None

    async def test_unknown_game_is_not_found(self, games_client: httpx.AsyncClient) -> None:
        response = await games_client.get(f"/api/v1/games/{uuid.uuid4()}")

        assert response.status_code == 404

    async def test_another_profiles_game_is_not_visible(
        self, games_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User()
        db_session.add(other_user)
        await db_session.flush()
        other_profile = Profile(
            owner_user_id=other_user.id, kind=ProfileKind.SELF, display_name="Other"
        )
        db_session.add(other_profile)
        await db_session.flush()
        game = await _seed_game(db_session, other_profile.id)

        response = await games_client.get(f"/api/v1/games/{game.id}")

        assert response.status_code == 404


class TestGetMyGamePgn:
    async def test_returns_the_stored_pgn_as_plain_text(
        self, games_client: httpx.AsyncClient, db_session: AsyncSession, tmp_path
    ) -> None:
        profile_id = uuid.UUID(games_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)
        pgn = '[White "Alice"]\n[Black "Bob"]\n\n1. e4 e5 1-0\n'
        await LocalStorage(tmp_path).put(game.raw_pgn_path, pgn.encode())

        response = await games_client.get(f"/api/v1/games/{game.id}/pgn")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert response.text == pgn

    async def test_a_game_whose_blob_is_missing_is_not_found(
        self, games_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(games_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)  # row exists, no blob written

        response = await games_client.get(f"/api/v1/games/{game.id}/pgn")

        assert response.status_code == 404

    async def test_another_profiles_pgn_is_not_visible(
        self, games_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User()
        db_session.add(other_user)
        await db_session.flush()
        other_profile = Profile(
            owner_user_id=other_user.id, kind=ProfileKind.SELF, display_name="Other"
        )
        db_session.add(other_profile)
        await db_session.flush()
        game = await _seed_game(db_session, other_profile.id)

        response = await games_client.get(f"/api/v1/games/{game.id}/pgn")

        assert response.status_code == 404
