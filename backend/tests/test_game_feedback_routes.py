"""HTTP-level tests for `/reports/games/{id}/pattern-feedback` (Phase 19).

Comparison correctness is `test_game_feedback_comparison.py`'s job; these cover the HTTP
contract — profile scoping, the pending-vs-error 404, and the thin-baseline response that
must NOT read as an error, since a new player hits it on their first few games.
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
from app.db.base import utc_now
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MotifFinding,
    MotifType,
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

# Shaped for the pattern-feedback format so the critic accepts it — a "repeated" finding
# citing a real repeat fact id.
_GOOD_RESPONSE = json.dumps(
    {
        "summary": "Better than your recent games, but the same habit showed up.",
        "findings": [
            {
                "fact_ids": ["repeat-motif-hanging_piece"],
                "kind": "repeated",
                "text": "You hung a piece again on move 1.",
            }
        ],
        "recommendations": ["Check what is defended before moving."],
    }
)


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def feedback_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    settings.game_feedback.game_feedback_min_baseline_games = 3
    return settings


@pytest_asyncio.fixture
async def feedback_client(
    feedback_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(feedback_settings)
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


async def _seed_analyzed_game(
    session: AsyncSession,
    profile_id: uuid.UUID,
    *,
    hanging_piece: bool,
) -> Game:
    """One canonicalized, analyzed game where White (the player) blunders on ply 0,
    optionally with a hanging-piece motif detected at that same ply."""
    game = Game(
        profile_id=profile_id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "A", "Black": "B", "Result": "1-0"},
        raw_pgn_path="pgn/test.pgn",
        focus_color=GameColor.WHITE,
        # Aggregation only sees canonicalized games — without this the game is invisible
        # to its own baseline.
        canonicalized_at=utc_now(),
    )
    session.add(game)
    await session.flush()

    analysis = GameAnalysis(
        game_id=game.id,
        analysis_version="test-v1",
        engine_depth=12,
        summary={"total_moves": 2, "counts": {"blunder": 1, "best": 1}, "accuracy": 50.0},
    )
    session.add(analysis)
    await session.flush()

    session.add_all(
        [
            MoveEvaluation(
                game_analysis_id=analysis.id,
                ply=ply,
                eval_cp=0,
                mate_in=None,
                best_move_uci="e2e4",
                pv=[],
                classification=classification,
                eval_swing_cp=300,
                is_critical_moment=False,
                deep_analyzed=False,
            )
            for ply, classification in (
                (0, MoveClassification.BLUNDER),
                (1, MoveClassification.BEST),
            )
        ]
    )
    if hanging_piece:
        session.add(
            MotifFinding(
                game_analysis_id=analysis.id,
                ply=0,
                side=GameColor.WHITE,
                motif=MotifType.HANGING_PIECE,
                confidence=0.9,
                evidence={},
            )
        )
    await session.flush()
    return game


class TestPatternFeedbackRoute:
    async def test_thin_baseline_is_a_normal_response_not_an_error(
        self, feedback_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(feedback_client.headers["X-Test-Profile-Id"])
        game = await _seed_analyzed_game(db_session, profile_id, hanging_piece=True)

        response = await feedback_client.get(f"/api/v1/reports/games/{game.id}/pattern-feedback")

        assert response.status_code == 200
        body = response.json()
        assert body["sufficient_baseline"] is False
        assert body["baseline_games"] == 0
        # No report at all, rather than prose hedged over a baseline of nothing.
        assert body["report"] is None

    async def test_reports_a_repeat_once_the_baseline_supports_it(
        self, feedback_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(feedback_client.headers["X-Test-Profile-Id"])
        for _ in range(3):
            await _seed_analyzed_game(db_session, profile_id, hanging_piece=True)
        latest = await _seed_analyzed_game(db_session, profile_id, hanging_piece=True)

        response = await feedback_client.get(f"/api/v1/reports/games/{latest.id}/pattern-feedback")

        assert response.status_code == 200
        body = response.json()
        assert body["sufficient_baseline"] is True
        assert body["baseline_games"] == 3
        assert [item["name"] for item in body["repeated"]] == ["hanging_piece"]
        assert body["repeated"][0]["move_numbers"] == [1]
        assert body["report"]["persona"] == "self_learner"

    async def test_regenerate_replaces_the_stored_write_up(
        self, feedback_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Without the flag the stored report is reused; with it, a new one is generated
        and returned in its place."""
        profile_id = uuid.UUID(feedback_client.headers["X-Test-Profile-Id"])
        for _ in range(3):
            await _seed_analyzed_game(db_session, profile_id, hanging_piece=True)
        latest = await _seed_analyzed_game(db_session, profile_id, hanging_piece=True)
        url = f"/api/v1/reports/games/{latest.id}/pattern-feedback"

        first = (await feedback_client.get(url)).json()["report"]
        cached = (await feedback_client.get(url)).json()["report"]
        regenerated = (await feedback_client.get(url, params={"regenerate": "true"})).json()[
            "report"
        ]

        assert cached["id"] == first["id"]
        assert regenerated["id"] != first["id"]

    async def test_regenerate_cannot_force_a_verdict_on_a_thin_baseline(
        self, feedback_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """The button must not be a way around the minimum-history gate — there is
        nothing to regenerate from."""
        profile_id = uuid.UUID(feedback_client.headers["X-Test-Profile-Id"])
        game = await _seed_analyzed_game(db_session, profile_id, hanging_piece=True)

        response = await feedback_client.get(
            f"/api/v1/reports/games/{game.id}/pattern-feedback",
            params={"regenerate": "true"},
        )

        assert response.status_code == 200
        assert response.json()["report"] is None

    async def test_a_game_with_no_analysis_yet_is_pending_not_broken(
        self, feedback_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """The frontend tells "still analyzing" from "failed" by this detail string."""
        profile_id = uuid.UUID(feedback_client.headers["X-Test-Profile-Id"])
        game = Game(
            profile_id=profile_id,
            source=GameSource.UPLOAD,
            content_hash=str(uuid.uuid4()),
            headers={"White": "A", "Black": "B"},
            raw_pgn_path="pgn/test.pgn",
        )
        db_session.add(game)
        await db_session.flush()

        response = await feedback_client.get(f"/api/v1/reports/games/{game.id}/pattern-feedback")

        assert response.status_code == 404
        assert "no analysis found" in response.json()["detail"].lower()

    async def test_another_profiles_game_is_not_visible(
        self, feedback_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User()
        db_session.add(other_user)
        await db_session.flush()
        other_profile = Profile(
            owner_user_id=other_user.id, kind=ProfileKind.SELF, display_name="Other"
        )
        db_session.add(other_profile)
        await db_session.flush()
        game = await _seed_analyzed_game(db_session, other_profile.id, hanging_piece=True)

        response = await feedback_client.get(f"/api/v1/reports/games/{game.id}/pattern-feedback")

        assert response.status_code == 404
