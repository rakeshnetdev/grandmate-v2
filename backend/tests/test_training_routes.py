"""HTTP-level training-plan route tests (Phase 15, D-032): default/explicit persona and
window, window validation, and profile scoping. Generation correctness itself is
`test_training_service.py`'s job — these are about the HTTP contract.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.api.dependencies.llm import get_embedding_provider, get_llm_provider
from app.api.dependencies.storage import get_storage
from app.core.config import Settings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MotifFinding,
    MotifType,
)
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app
from tests.fake_embeddings import FakeEmbeddingProvider
from tests.fake_llm import FakeLLMProvider

_GOOD_RESPONSE = json.dumps(
    {
        "summary": "A recurring pattern.",
        "findings": [{"fact_ids": ["weakness-motif-fork"], "text": "You keep getting forked."}],
        "recommendations": ["Study forks."],
    }
)


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture
def training_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def training_client(
    training_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(training_settings)
    app.state.db_session_factory = None

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(
        responses=[_GOOD_RESPONSE, _GOOD_RESPONSE, _GOOD_RESPONSE]
    )
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"}
        )
        client.headers["X-Test-Profile-Id"] = login.json()["profile"]["id"]
        yield client


async def _seed_recurring_fork_weakness(session: AsyncSession, profile_id: uuid.UUID) -> None:
    for _ in range(3):
        game = Game(
            profile_id=profile_id,
            source=GameSource.UPLOAD,
            content_hash=str(uuid.uuid4()),
            headers={"White": "A", "Black": "B", "Result": "0-1"},
            raw_pgn_path="pgn/test.pgn",
            canonicalized_at=datetime.now(UTC),
            focus_color=GameColor.WHITE,
        )
        session.add(game)
        await session.flush()

        analysis = GameAnalysis(
            game_id=game.id,
            analysis_version="test",
            engine_depth=12,
            summary={"total_moves": 10, "counts": {"best": 10}, "accuracy": 70.0},
        )
        session.add(analysis)
        await session.flush()

        session.add(
            MotifFinding(
                game_analysis_id=analysis.id,
                ply=10,
                side=GameColor.BLACK,
                motif=MotifType.FORK,
                confidence=0.9,
                evidence={},
            )
        )
        await session.flush()


class TestGetTrainingPlan:
    async def test_defaults_to_self_learner_persona_and_the_default_window(
        self, training_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(training_client.headers["X-Test-Profile-Id"])
        await _seed_recurring_fork_weakness(db_session, profile_id)

        response = await training_client.get("/api/v1/reports/profile/training")

        assert response.status_code == 200
        body = response.json()
        assert body["persona"] == "self_learner"
        assert body["window_size"] == 10

    async def test_accepts_an_explicit_persona_and_window(
        self, training_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(training_client.headers["X-Test-Profile-Id"])
        await _seed_recurring_fork_weakness(db_session, profile_id)

        response = await training_client.get(
            "/api/v1/reports/profile/training", params={"persona": "kid", "window": 30}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["persona"] == "kid"
        assert body["window_size"] == 30

    async def test_rejects_an_out_of_range_window(self, training_client: httpx.AsyncClient) -> None:
        response = await training_client.get(
            "/api/v1/reports/profile/training", params={"window": 7}
        )
        assert response.status_code == 422

    async def test_returns_the_generated_content(
        self, training_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        profile_id = uuid.UUID(training_client.headers["X-Test-Profile-Id"])
        await _seed_recurring_fork_weakness(db_session, profile_id)

        response = await training_client.get("/api/v1/reports/profile/training")

        body = response.json()
        assert body["summary"] == "A recurring pattern."
        assert body["themes_covered"] == ["fork"]
        assert body["source"] == "llm"
        assert body["grounded"] is True

    async def test_a_profile_with_no_games_gets_an_empty_fallback_plan(
        self, training_client: httpx.AsyncClient
    ) -> None:
        response = await training_client.get("/api/v1/reports/profile/training")

        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "fallback"
        assert body["themes_covered"] == []
