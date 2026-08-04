"""Integration tests for `ReportService.get_or_generate_story` (Phase 16b), same
`FakeLLMProvider`-scripted convention as `test_reports_service.py`.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LLMSettings, ReportSettings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MoveClassification,
    MoveEvaluation,
    Persona,
    Profile,
    ProfileKind,
    ReportSource,
    User,
)
from app.domain.reports import ReportService
from tests.fake_llm import FakeLLMProvider

_GOOD_STORY_RESPONSE = json.dumps(
    {
        "summary": "A close game decided by one blunder.",
        "findings": [
            {"fact_ids": ["move-4"], "text": "White's move was a blunder.", "kind": "lesson"}
        ],
        "recommendations": [],
    }
)

_GOOD_FINDINGS_RESPONSE = json.dumps(
    {
        "summary": "A close game.",
        "findings": [
            {"fact_ids": ["move-4"], "text": "White's move was a blunder.", "kind": "mistake"}
        ],
        "recommendations": [],
    }
)

_UNGROUNDED_RESPONSE = json.dumps(
    {
        "summary": "...",
        "findings": [{"fact_ids": ["move-999"], "text": "invented", "kind": "lesson"}],
        "recommendations": [],
    }
)


def _report_settings() -> ReportSettings:
    return ReportSettings()  # type: ignore[call-arg]


def _llm_settings(**overrides: object) -> LLMSettings:
    return LLMSettings(**overrides)  # type: ignore[arg-type]


async def _seed_game_with_analysis(session: AsyncSession) -> tuple[Game, GameAnalysis]:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Test")
    session.add(profile)
    await session.flush()

    game = Game(
        profile_id=profile.id,
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
        summary={"total_moves": 5, "counts": {"blunder": 1}, "accuracy": 80.0},
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
    await session.refresh(analysis, attribute_names=["evaluations"])
    return game, analysis


class TestGetOrGenerateStory:
    async def test_a_grounded_response_is_persisted_as_a_story_report(
        self, db_session: AsyncSession
    ) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_STORY_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        report = await service.get_or_generate_story(
            game=game, analysis=analysis, opening=None, motifs=[], themes=[]
        )

        assert report.source == ReportSource.LLM
        assert report.report_type == "story"
        assert report.persona == Persona.SELF_LEARNER
        assert report.content["findings"][0]["kind"] == "lesson"

    async def test_an_ungrounded_response_falls_back(self, db_session: AsyncSession) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_UNGROUNDED_RESPONSE, _UNGROUNDED_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        report = await service.get_or_generate_story(
            game=game, analysis=analysis, opening=None, motifs=[], themes=[]
        )

        assert report.source == ReportSource.FALLBACK
        assert report.grounded is True

    async def test_a_fresh_existing_story_is_returned_without_calling_the_llm_again(
        self, db_session: AsyncSession
    ) -> None:
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_STORY_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())
        first = await service.get_or_generate_story(
            game=game, analysis=analysis, opening=None, motifs=[], themes=[]
        )

        second = await service.get_or_generate_story(
            game=game, analysis=analysis, opening=None, motifs=[], themes=[]
        )

        assert second.id == first.id
        assert len(llm.calls) == 1

    async def test_regenerate_bypasses_a_fresh_story_and_spends_another_call(
        self, db_session: AsyncSession
    ) -> None:
        """The explicit "Regenerate" button — the one caller allowed to pay twice for the
        same analysis version, per the test above."""
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_STORY_RESPONSE, _GOOD_STORY_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())
        first = await service.get_or_generate_story(
            game=game, analysis=analysis, opening=None, motifs=[], themes=[]
        )

        second = await service.get_or_generate_story(
            game=game, analysis=analysis, opening=None, motifs=[], themes=[], regenerate=True
        )

        assert second.id != first.id
        assert len(llm.calls) == 2
        assert second.analysis_version == first.analysis_version

    async def test_findings_report_and_story_report_coexist_independently(
        self, db_session: AsyncSession
    ) -> None:
        """The same (game_id, persona) now has two report *shapes* — this is exactly
        what `report_type` exists to keep from colliding (see queries.get_latest_report).
        """
        game, analysis = await _seed_game_with_analysis(db_session)
        llm = FakeLLMProvider(responses=[_GOOD_STORY_RESPONSE, _GOOD_FINDINGS_RESPONSE])
        service = ReportService(db_session, llm, _report_settings(), _llm_settings())

        story = await service.get_or_generate_story(
            game=game, analysis=analysis, opening=None, motifs=[], themes=[]
        )
        findings_report = await service.get_or_generate(
            game=game,
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            persona=Persona.SELF_LEARNER,
        )

        assert story.id != findings_report.id
        assert story.report_type == "story"
        assert findings_report.report_type == "findings"
