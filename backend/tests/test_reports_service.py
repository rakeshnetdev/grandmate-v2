"""Integration tests for `ReportService` against a real transactional database, using
`FakeLLMProvider` (no real network call) to script the LLM side of the grounding/retry/
fallback flow.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LLMSettings, ReportSettings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameReport,
    GameSource,
    MoveClassification,
    MoveEvaluation,
    Persona,
    Profile,
    ProfileKind,
    ReportSource,
    User,
)
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.reports import ReportService
from tests.fake_llm import FakeLLMProvider

_GOOD_RESPONSE = json.dumps(
    {
        "summary": "A close game with one costly mistake.",
        # "kind" and third-person phrasing satisfy the self-learner game format's rules
        # (Phase 16a, D-035 addendum); harmless extra data for the other personas this
        # fixture is also reused for below (KID), whose critic ignores unknown keys.
        "findings": [
            {"fact_ids": ["move-4"], "text": "White's move 4 was a blunder.", "kind": "mistake"}
        ],
        "recommendations": ["Review move 4."],
    }
)

_UNGROUNDED_RESPONSE = json.dumps(
    {
        "summary": "...",
        "findings": [{"fact_ids": ["move-999"], "text": "A move that never happened."}],
        "recommendations": [],
    }
)


def _report_settings() -> ReportSettings:
    return ReportSettings()  # type: ignore[call-arg]


def _llm_settings(**overrides: object) -> LLMSettings:
    return LLMSettings(**overrides)  # type: ignore[arg-type]


async def _seed_profile_id(session: AsyncSession) -> uuid.UUID:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Test")
    session.add(profile)
    await session.flush()
    return profile.id


async def _seed_game_with_analysis(session: AsyncSession) -> tuple[Game, GameAnalysis]:
    game = Game(
        profile_id=await _seed_profile_id(session),
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "Player", "Black": "Opponent", "Result": "1-0"},
        raw_pgn_path="pgn/test.pgn",
        focus_color=GameColor.WHITE,
    )
    session.add(game)
    await session.flush()

    analysis = GameAnalysis(
        game_id=game.id,
        analysis_version="test-v1",
        engine_depth=12,
        summary={
            "total_moves": 5,
            "counts": {"blunder": 1},
            "accuracy": 80.0,
            "critical_moments": 1,
        },
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
    # Not `analysis.evaluations = [...]`: assigning to the relationship collection
    # lazy-loads the existing (empty) one first to reconcile it, a synchronous load this
    # async session can't satisfy implicitly — see `GameParsingService.canonicalize`'s
    # own comment for the same issue. `refresh` re-loads the relationship async-safely.
    await session.refresh(analysis, attribute_names=["evaluations"])
    return game, analysis


class TestGetOrGenerate:
    async def test_a_well_grounded_first_response_is_used_as_is(
        self, db_session: AsyncSession
    ) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        report = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )

        assert report.source == ReportSource.LLM
        assert report.grounded is True
        assert report.model == "fake-model"
        assert len(llm.calls) == 1

    async def test_an_ungrounded_first_response_is_retried_once(
        self, db_session: AsyncSession
    ) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_UNGROUNDED_RESPONSE, _GOOD_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        report = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )

        assert report.source == ReportSource.LLM
        assert len(llm.calls) == 2

    async def test_two_ungrounded_responses_fall_back_without_a_third_attempt(
        self, db_session: AsyncSession
    ) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_UNGROUNDED_RESPONSE, _UNGROUNDED_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        report = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )

        assert report.source == ReportSource.FALLBACK
        assert report.model is None
        assert report.grounded is True
        assert len(llm.calls) == 2

    async def test_exhausted_budget_skips_the_llm_entirely(self, db_session: AsyncSession) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE])
        settings = _llm_settings(llm_daily_token_ceiling=100)
        # Pre-record today's usage at the ceiling, simulating an already-exhausted budget.
        await LLMBudgetTracker(db_session, settings).record_usage(
            prompt_tokens=100, completion_tokens=0
        )
        service = ReportService(db_session, llm, _report_settings(), settings)

        report = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )

        assert report.source == ReportSource.FALLBACK
        assert llm.calls == []

    async def test_a_fresh_existing_report_is_returned_without_calling_the_llm_again(
        self, db_session: AsyncSession
    ) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        first = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )
        second = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )

        assert first.id == second.id
        assert len(llm.calls) == 1

    async def test_a_stale_report_triggers_regeneration(self, db_session: AsyncSession) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE, _GOOD_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        first = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )
        analysis.analysis_version = "test-v2"
        await db_session.flush()

        second = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )

        assert second.id != first.id
        assert len(llm.calls) == 2

    async def test_different_personas_get_different_reports(self, db_session: AsyncSession) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_RESPONSE, _GOOD_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        self_report = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )
        kid_report = await service.get_or_generate(
            game=game, analysis=analysis, opening=None, motifs=[], themes=[], persona=Persona.KID
        )

        assert self_report.id != kid_report.id
        rows = (
            (await db_session.execute(select(GameReport).where(GameReport.game_id == game.id)))
            .scalars()
            .all()
        )
        assert len(rows) == 2
