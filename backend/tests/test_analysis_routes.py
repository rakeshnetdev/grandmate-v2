"""HTTP-level analysis route tests: job status, game results, retry.

Same pattern as `test_import_routes.py`: real transactional `db_session`, `get_db_session`
overridden, `run_pending_analysis_jobs` stubbed (only the retry endpoint dispatches it —
see that file's docstring for why real dispatch has no place in an HTTP-contract test).
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
    GameSource,
    Job,
    JobKind,
    JobStatus,
    MoveClassification,
    MoveEvaluation,
    Profile,
    ProfileKind,
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


@pytest.fixture(autouse=True)
def _stub_analysis_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.api.routes.analysis._run_pending_analysis_jobs", _noop)


@pytest.fixture
def analysis_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def analysis_client(
    analysis_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(analysis_settings)
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


async def _seed_completed_analysis(session: AsyncSession, game: Game) -> GameAnalysis:
    analysis = GameAnalysis(
        game_id=game.id,
        analysis_version="sf-d12-dd18-t50.100.300",
        engine_depth=12,
        summary={"total_moves": 1, "counts": {"best": 1}, "accuracy": 100.0},
    )
    session.add(analysis)
    await session.flush()
    session.add(
        MoveEvaluation(
            game_analysis_id=analysis.id,
            ply=0,
            eval_cp=20,
            mate_in=None,
            best_move_uci="e2e4",
            pv=["e2e4"],
            classification=MoveClassification.BEST,
            eval_swing_cp=0,
            is_critical_moment=False,
            deep_analyzed=False,
        )
    )
    await session.flush()
    return analysis


async def _seed_job(
    session: AsyncSession, profile_id: uuid.UUID, game_id: uuid.UUID, status: JobStatus
) -> Job:
    job = Job(kind=JobKind.ENGINE_ANALYSIS, profile_id=profile_id, game_id=game_id, status=status)
    session.add(job)
    await session.flush()
    return job


class TestGetAnalysisJob:
    async def test_returns_the_jobs_status(
        self, analysis_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(analysis_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)
        job = await _seed_job(db_session, profile_id, game.id, JobStatus.DONE)
        await db_session.flush()

        response = await analysis_client.get(f"/api/v1/analysis/jobs/{job.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(job.id)
        assert body["status"] == "done"
        assert body["game_id"] == str(game.id)

    async def test_unknown_job_is_not_found(self, analysis_client: httpx.AsyncClient) -> None:
        response = await analysis_client.get(f"/api/v1/analysis/jobs/{uuid.uuid4()}")

        assert response.status_code == 404

    async def test_another_profiles_job_is_not_visible(
        self, analysis_client: httpx.AsyncClient, db_session: AsyncSession
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
        job = await _seed_job(db_session, other_profile.id, game.id, JobStatus.DONE)
        await db_session.flush()

        response = await analysis_client.get(f"/api/v1/analysis/jobs/{job.id}")

        assert response.status_code == 404


class TestGetGameAnalysis:
    async def test_returns_the_completed_analysis_with_moves(
        self, analysis_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(analysis_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)
        await _seed_completed_analysis(db_session, game)

        response = await analysis_client.get(f"/api/v1/analysis/games/{game.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["game_id"] == str(game.id)
        assert body["summary"]["accuracy"] == 100.0
        assert len(body["moves"]) == 1
        assert body["moves"][0]["classification"] == "best"

    async def test_a_game_with_no_analysis_yet_is_not_found(
        self, analysis_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(analysis_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)
        await db_session.flush()

        response = await analysis_client.get(f"/api/v1/analysis/games/{game.id}")

        assert response.status_code == 404


class TestRetryGameAnalysis:
    async def test_queues_a_new_job_for_a_game_the_caller_owns(
        self, analysis_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(analysis_client.headers["X-Test-Profile-Id"])
        game = await _seed_game(db_session, profile_id)
        await db_session.flush()

        response = await analysis_client.post(f"/api/v1/analysis/games/{game.id}/retry")

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending"
        assert body["game_id"] == str(game.id)

    async def test_retrying_an_unknown_game_is_not_found(
        self, analysis_client: httpx.AsyncClient
    ) -> None:
        response = await analysis_client.post(f"/api/v1/analysis/games/{uuid.uuid4()}/retry")

        assert response.status_code == 404
