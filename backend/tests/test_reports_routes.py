"""HTTP-level report route tests: default/explicit persona, 404s, and profile scoping.
`get_llm_provider` is overridden with `FakeLLMProvider` so no real network call happens —
generation correctness itself is `test_reports_service.py`'s job; these are about the
HTTP contract.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.api.dependencies.llm import get_llm_provider
from app.api.dependencies.storage import get_storage
from app.core.config import Settings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MoveClassification,
    MoveEvaluation,
    Profile,
    ProfileKind,
    User,
)
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app
from tests.fake_llm import FakeLLMProvider

_GOOD_RESPONSE = json.dumps(
    {
        "summary": "A close game.",
        # "kind" and third-person phrasing satisfy the self-learner game format's rules
        # (Phase 16a, D-035 addendum) — this fixture is used for self_learner requests.
        "findings": [
            {"fact_ids": ["move-4"], "text": "White's move 4 was a blunder.", "kind": "mistake"}
        ],
        "recommendations": ["Review move 4."],
    }
)


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def reports_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def reports_client(
    reports_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(reports_settings)
    app.state.db_session_factory = None

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(
        responses=[_GOOD_RESPONSE, _GOOD_RESPONSE, _GOOD_RESPONSE]
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        client.headers["X-Test-Profile-Id"] = login.json()["profile"]["id"]
        yield client


async def _seed_game_with_analysis(session: AsyncSession, profile_id: uuid.UUID) -> Game:
    game = Game(
        profile_id=profile_id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "A", "Black": "B", "Result": "1-0"},
        raw_pgn_path="pgn/test.pgn",
        focus_color=GameColor.WHITE,
    )
    session.add(game)
    await session.flush()

    analysis = GameAnalysis(
        game_id=game.id,
        analysis_version="test-v1",
        engine_depth=12,
        summary={"total_moves": 1, "counts": {"blunder": 1}, "accuracy": 50.0},
    )
    session.add(analysis)
    await session.flush()
    session.add(
        MoveEvaluation(
            game_analysis_id=analysis.id,
            ply=4,
            eval_cp=0,
            mate_in=None,
            best_move_uci="e2e4",
            pv=[],
            classification=MoveClassification.BLUNDER,
            eval_swing_cp=300,
            is_critical_moment=True,
            deep_analyzed=True,
        )
    )
    await session.flush()
    return game


class TestGetGameStory:
    """HTTP-level tests for `/reports/games/{id}/story` (Phase 16b) — the fixture's
    scripted `_GOOD_RESPONSE` is shaped for the findings format (`kind: "mistake"`), so
    it fails the story critic's kind check and falls back deterministically; that's fine
    here since generation correctness is `test_reports_story_service.py`'s job — these
    tests are about the HTTP contract only.
    """

    async def test_returns_a_story_report_for_an_analyzed_game(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(reports_client.headers["X-Test-Profile-Id"])
        game = await _seed_game_with_analysis(db_session, profile_id)

        response = await reports_client.get(f"/api/v1/reports/games/{game.id}/story")

        assert response.status_code == 200
        body = response.json()
        assert body["game_id"] == str(game.id)
        assert body["persona"] == "self_learner"

    async def test_unknown_game_is_not_found(self, reports_client: httpx.AsyncClient) -> None:
        response = await reports_client.get(f"/api/v1/reports/games/{uuid.uuid4()}/story")
        assert response.status_code == 404

    async def test_a_game_with_no_analysis_yet_is_not_found(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(reports_client.headers["X-Test-Profile-Id"])
        game = Game(
            profile_id=profile_id,
            source=GameSource.UPLOAD,
            content_hash=str(uuid.uuid4()),
            headers={"White": "A", "Black": "B"},
            raw_pgn_path="pgn/test.pgn",
        )
        db_session.add(game)
        await db_session.flush()

        response = await reports_client.get(f"/api/v1/reports/games/{game.id}/story")

        assert response.status_code == 404

    async def test_another_profiles_game_is_not_visible(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User()
        db_session.add(other_user)
        await db_session.flush()
        other_profile = Profile(
            owner_user_id=other_user.id, kind=ProfileKind.SELF, display_name="Other"
        )
        db_session.add(other_profile)
        await db_session.flush()
        game = await _seed_game_with_analysis(db_session, other_profile.id)

        response = await reports_client.get(f"/api/v1/reports/games/{game.id}/story")

        assert response.status_code == 404


class TestGetGameReport:
    async def test_defaults_to_self_learner_persona(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(reports_client.headers["X-Test-Profile-Id"])
        game = await _seed_game_with_analysis(db_session, profile_id)

        response = await reports_client.get(f"/api/v1/reports/games/{game.id}")

        assert response.status_code == 200
        assert response.json()["persona"] == "self_learner"

    async def test_accepts_an_explicit_persona(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(reports_client.headers["X-Test-Profile-Id"])
        game = await _seed_game_with_analysis(db_session, profile_id)

        response = await reports_client.get(
            f"/api/v1/reports/games/{game.id}", params={"persona": "kid"}
        )

        assert response.status_code == 200
        assert response.json()["persona"] == "kid"

    async def test_rejects_an_unknown_persona(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(reports_client.headers["X-Test-Profile-Id"])
        game = await _seed_game_with_analysis(db_session, profile_id)

        response = await reports_client.get(
            f"/api/v1/reports/games/{game.id}", params={"persona": "parent"}
        )

        assert response.status_code == 422

    async def test_unknown_game_is_not_found(self, reports_client: httpx.AsyncClient) -> None:
        response = await reports_client.get(f"/api/v1/reports/games/{uuid.uuid4()}")
        assert response.status_code == 404

    async def test_a_game_with_no_analysis_yet_is_not_found(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(reports_client.headers["X-Test-Profile-Id"])
        game = Game(
            profile_id=profile_id,
            source=GameSource.UPLOAD,
            content_hash=str(uuid.uuid4()),
            headers={"White": "A", "Black": "B"},
            raw_pgn_path="pgn/test.pgn",
        )
        db_session.add(game)
        await db_session.flush()

        response = await reports_client.get(f"/api/v1/reports/games/{game.id}")

        assert response.status_code == 404

    async def test_another_profiles_game_is_not_visible(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User()
        db_session.add(other_user)
        await db_session.flush()
        other_profile = Profile(
            owner_user_id=other_user.id, kind=ProfileKind.SELF, display_name="Other"
        )
        db_session.add(other_profile)
        await db_session.flush()
        game = await _seed_game_with_analysis(db_session, other_profile.id)

        response = await reports_client.get(f"/api/v1/reports/games/{game.id}")

        assert response.status_code == 404

    async def test_returns_the_generated_content(
        self, reports_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(reports_client.headers["X-Test-Profile-Id"])
        game = await _seed_game_with_analysis(db_session, profile_id)

        response = await reports_client.get(f"/api/v1/reports/games/{game.id}")

        body = response.json()
        assert body["summary"] == "A close game."
        assert body["findings"][0]["fact_ids"] == ["move-4"]
        assert body["source"] == "llm"
        assert body["grounded"] is True
