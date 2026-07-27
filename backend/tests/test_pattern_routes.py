"""HTTP-level pattern route tests: opening + tactical/strategic findings, profile
scoping. Same pattern as `test_analysis_routes.py`: real transactional `db_session`,
`get_db_session` overridden, no real detection run — these are about the HTTP contract
over already-seeded rows, not about detection itself (covered by
`test_pattern_service.py` and the per-detector unit tests).
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
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MotifFinding,
    MotifType,
    OpeningMatch,
    Profile,
    ProfileKind,
    StrategicThemeFinding,
    StrategicThemeType,
    User,
)
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def pattern_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def pattern_client(
    pattern_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(pattern_settings)
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


async def _seed_game(session: AsyncSession, profile_id: uuid.UUID) -> Game:
    game = Game(
        profile_id=profile_id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "A", "Black": "B"},
        raw_pgn_path="pgn/test.pgn",
    )
    session.add(game)
    await session.flush()
    return game


class TestGetGamePatterns:
    async def test_a_game_with_nothing_detected_yet_returns_empty_shape(
        self, pattern_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(pattern_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)

        response = await pattern_client.get(f"/api/v1/patterns/games/{game.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["game_id"] == str(game.id)
        assert body["opening"] is None
        assert body["motifs"] == []
        assert body["themes"] == []

    async def test_returns_the_opening_match(
        self, pattern_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(pattern_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)
        db_session.add(
            OpeningMatch(
                game_id=game.id,
                eco="C60",
                opening_name="Ruy Lopez",
                epd="r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq -",
                matched_ply=4,
            )
        )
        await db_session.flush()

        response = await pattern_client.get(f"/api/v1/patterns/games/{game.id}")

        assert response.status_code == 200
        opening = response.json()["opening"]
        assert opening == {
            "eco": "C60",
            "opening_name": "Ruy Lopez",
            "epd": "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq -",
            "matched_ply": 4,
        }

    async def test_returns_motif_and_theme_findings_from_the_latest_analysis(
        self, pattern_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(pattern_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)
        analysis = GameAnalysis(
            game_id=game.id, analysis_version="test", engine_depth=12, summary={}
        )
        db_session.add(analysis)
        await db_session.flush()
        db_session.add(
            MotifFinding(
                game_analysis_id=analysis.id,
                ply=10,
                side=GameColor.WHITE,
                motif=MotifType.FORK,
                confidence=0.9,
                evidence={"target_squares": ["e8", "c8"]},
            )
        )
        db_session.add(
            StrategicThemeFinding(
                game_analysis_id=analysis.id,
                ply=20,
                side=GameColor.BLACK,
                theme=StrategicThemeType.BAD_BISHOP,
                confidence=0.6,
                evidence={"bishop_square": "c8"},
            )
        )
        await db_session.flush()

        response = await pattern_client.get(f"/api/v1/patterns/games/{game.id}")

        assert response.status_code == 200
        body = response.json()
        assert len(body["motifs"]) == 1
        assert body["motifs"][0]["motif"] == "fork"
        assert body["motifs"][0]["side"] == "white"
        assert body["motifs"][0]["confidence"] == 0.9
        assert len(body["themes"]) == 1
        assert body["themes"][0]["theme"] == "bad_bishop"
        assert body["themes"][0]["side"] == "black"

    async def test_unknown_game_is_not_found(self, pattern_client: httpx.AsyncClient) -> None:
        response = await pattern_client.get(f"/api/v1/patterns/games/{uuid.uuid4()}")

        assert response.status_code == 404

    async def test_another_profiles_game_is_not_visible(
        self, pattern_client: httpx.AsyncClient, db_session: AsyncSession
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

        response = await pattern_client.get(f"/api/v1/patterns/games/{game.id}")

        assert response.status_code == 404
