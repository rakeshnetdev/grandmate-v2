"""Integration tests for `TrainingService` against a real transactional database, using
`FakeLLMProvider`/`FakeEmbeddingProvider` (no real network calls) to script the
generation/grounding/retry/fallback flow end to end: analytics snapshot -> retrieval ->
facts -> selection -> LLM -> critic -> persistence.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AnalyticsSettings, LLMSettings, ReportSettings, RetrievalSettings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    KnowledgeBucket,
    KnowledgeChunk,
    KnowledgeDocument,
    MotifFinding,
    MotifType,
    Persona,
    Profile,
    ProfileKind,
    ReportSource,
    User,
)
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.reports import TrainingService
from tests.fake_embeddings import FakeEmbeddingProvider
from tests.fake_llm import FakeLLMProvider

_GOOD_RESPONSE = json.dumps(
    {
        "summary": "A recurring tactical pattern to work on.",
        "findings": [
            {"fact_ids": ["weakness-motif-fork"], "text": "Your opponents keep forking you."}
        ],
        "recommendations": ["Study fork patterns this week."],
    }
)

_UNGROUNDED_RESPONSE = json.dumps(
    {"summary": "...", "findings": [{"fact_ids": ["not-a-real-fact"], "text": "made up"}]}
)


def _report_settings(**overrides: object) -> ReportSettings:
    return ReportSettings(**overrides)  # type: ignore[arg-type]


def _llm_settings(**overrides: object) -> LLMSettings:
    return LLMSettings(**overrides)  # type: ignore[arg-type]


def _retrieval_settings() -> RetrievalSettings:
    return RetrievalSettings()  # type: ignore[call-arg]


def _analytics_settings() -> AnalyticsSettings:
    return AnalyticsSettings()  # type: ignore[call-arg]


async def _seed_profile(session: AsyncSession) -> uuid.UUID:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Test")
    session.add(profile)
    await session.flush()
    return profile.id


async def _seed_games_with_a_recurring_fork_weakness(
    session: AsyncSession, profile_id: uuid.UUID, *, games: int = 3
) -> None:
    """`games` games where the player was forked by the opponent every time — enough
    for `recurring_weaknesses` to clear `analytics_weakness_min_occurrence_rate`
    (default 0.3) at occurrence_rate=1.0."""
    for i in range(games):
        created_at = datetime(2026, 7, 20 + i, tzinfo=UTC)
        game = Game(
            profile_id=profile_id,
            source=GameSource.UPLOAD,
            content_hash=str(uuid.uuid4()),
            headers={"White": "Player", "Black": "Opponent", "Result": "0-1"},
            raw_pgn_path="pgn/test.pgn",
            canonicalized_at=created_at,
            focus_color=GameColor.WHITE,
            created_at=created_at,
        )
        session.add(game)
        await session.flush()

        analysis = GameAnalysis(
            game_id=game.id,
            analysis_version="test",
            engine_depth=12,
            summary={"total_moves": 10, "counts": {"best": 10}, "accuracy": 70.0},
            created_at=created_at,
        )
        session.add(analysis)
        await session.flush()

        session.add(
            MotifFinding(
                game_analysis_id=analysis.id,
                ply=10,
                side=GameColor.BLACK,  # the opponent executed the fork against the player
                motif=MotifType.FORK,
                confidence=0.9,
                evidence={},
            )
        )
        await session.flush()


async def _seed_tactics_chunk_about_forks(session: AsyncSession) -> None:
    embedder = FakeEmbeddingProvider()
    document = KnowledgeDocument(
        bucket=KnowledgeBucket.TACTICS,
        title="Forks",
        source="test",
        source_url=None,
        licence="original",
        retrieved_at=date(2026, 7, 1),
        content_hash=str(uuid.uuid4()),
    )
    session.add(document)
    await session.flush()
    content = "A fork attacks two enemy pieces at once with a single piece."
    (embedding,) = await embedder.embed([content])
    session.add(
        KnowledgeChunk(
            document_id=document.id,
            bucket=KnowledgeBucket.TACTICS,
            chunk_index=0,
            content=content,
            token_count=len(content.split()),
            chunk_metadata={},
            embedding=embedding,
        )
    )
    await session.flush()


def _service(
    session: AsyncSession, llm: FakeLLMProvider, **llm_overrides: object
) -> TrainingService:
    return TrainingService(
        session,
        llm,
        FakeEmbeddingProvider(),
        _report_settings(),
        _llm_settings(**llm_overrides),
        _retrieval_settings(),
        _analytics_settings(),
    )


class TestGenerate:
    async def test_a_well_grounded_response_is_persisted_with_its_theme_recorded(
        self, db_session: AsyncSession
    ) -> None:
        profile_id = await _seed_profile(db_session)
        await _seed_games_with_a_recurring_fork_weakness(db_session, profile_id)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE])

        recommendation = await _service(db_session, llm).generate(
            profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10
        )

        assert recommendation.source == ReportSource.LLM
        assert recommendation.grounded is True
        assert recommendation.themes_covered == ["fork"]
        assert len(llm.calls) == 1

    async def test_retrieves_and_grounds_against_the_knowledge_corpus(
        self, db_session: AsyncSession
    ) -> None:
        profile_id = await _seed_profile(db_session)
        await _seed_games_with_a_recurring_fork_weakness(db_session, profile_id)
        await _seed_tactics_chunk_about_forks(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE])

        await _service(db_session, llm).generate(
            profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10
        )

        prompt_user_content = llm.calls[0].messages[1].content
        assert "fork attacks two enemy pieces" in prompt_user_content

    async def test_two_ungrounded_responses_fall_back_without_a_third_attempt(
        self, db_session: AsyncSession
    ) -> None:
        profile_id = await _seed_profile(db_session)
        await _seed_games_with_a_recurring_fork_weakness(db_session, profile_id)
        llm = FakeLLMProvider(responses=[_UNGROUNDED_RESPONSE, _UNGROUNDED_RESPONSE])

        recommendation = await _service(db_session, llm).generate(
            profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10
        )

        assert recommendation.source == ReportSource.FALLBACK
        assert recommendation.model is None
        assert len(llm.calls) == 2

    async def test_exhausted_budget_skips_the_llm_entirely(self, db_session: AsyncSession) -> None:
        profile_id = await _seed_profile(db_session)
        await _seed_games_with_a_recurring_fork_weakness(db_session, profile_id)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE])
        await LLMBudgetTracker(db_session, _llm_settings(llm_daily_token_ceiling=100)).record_usage(
            prompt_tokens=100, completion_tokens=0
        )

        recommendation = await _service(db_session, llm, llm_daily_token_ceiling=100).generate(
            profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10
        )

        assert recommendation.source == ReportSource.FALLBACK
        assert llm.calls == []

    async def test_each_call_inserts_a_new_row_rather_than_reusing_one(
        self, db_session: AsyncSession
    ) -> None:
        # D-032: on-demand, no caching — every request is a fresh generation, since
        # history (not staleness detection) is what keeps a plan from repeating itself.
        profile_id = await _seed_profile(db_session)
        await _seed_games_with_a_recurring_fork_weakness(db_session, profile_id)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE, _GOOD_RESPONSE])
        service = _service(db_session, llm)

        first = await service.generate(
            profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10
        )
        second = await service.generate(
            profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10
        )

        assert first.id != second.id

    async def test_a_theme_from_the_prior_plan_is_flagged_recently_recommended(
        self, db_session: AsyncSession
    ) -> None:
        profile_id = await _seed_profile(db_session)
        await _seed_games_with_a_recurring_fork_weakness(db_session, profile_id)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE, _GOOD_RESPONSE])
        service = _service(db_session, llm)

        await service.generate(profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10)
        await service.generate(profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10)

        user_content = llm.calls[1].messages[1].content
        second_call_facts = json.loads(user_content[user_content.index("[") :])
        fork_fact = next(f for f in second_call_facts if f["data"].get("name") == "fork")
        assert fork_fact["data"]["recently_recommended"] is True

    async def test_no_recurring_weakness_yields_an_empty_plan(
        self, db_session: AsyncSession
    ) -> None:
        profile_id = await _seed_profile(db_session)
        llm = FakeLLMProvider(responses=[])

        recommendation = await _service(db_session, llm).generate(
            profile_id=profile_id, persona=Persona.SELF_LEARNER, window_size=10
        )

        assert recommendation.source == ReportSource.FALLBACK
        assert recommendation.themes_covered == []
