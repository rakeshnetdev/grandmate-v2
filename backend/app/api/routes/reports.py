"""Persona report generation and retrieval (Phase 9, D-023) and training-plan
generation (Phase 15, D-032).

Thin per the "routes delegate" rule: orchestration lives in `domain/reports/service.py`
and `domain/reports/training_service.py`. `profile_id` scoping follows
`analysis.py`/`patterns.py`'s exact pattern (`ScopedProfileIdDep`, Phase 8b) — a report
belongs to whichever profile the game itself belongs to, and a training plan belongs
directly to the requested profile.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.llm import EmbeddingProviderDep, LLMProviderDep
from app.api.dependencies.profile_scope import ScopedProfileIdDep
from app.api.dependencies.settings import SettingsDep
from app.db.models import Game, GameReport, Persona, TrainingRecommendation
from app.domain.analysis import get_latest_analysis
from app.domain.game_feedback import PatternFeedback, PatternFeedbackService, load_baseline
from app.domain.game_feedback.facts import move_number
from app.domain.patterns.queries import get_opening_match, get_pattern_findings
from app.domain.reports import ReportService, TrainingService
from app.schemas.reports import (
    GameReportSummary,
    ImprovedWeaknessSummary,
    MetricComparisonSummary,
    PatternFeedbackSummary,
    RepeatedWeaknessSummary,
    ReportFinding,
    TrainingRecommendationSummary,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _to_summary(report: GameReport) -> GameReportSummary:
    content = report.content
    return GameReportSummary(
        id=report.id,
        game_id=report.game_id,
        persona=report.persona.value,
        source=report.source.value,
        model=report.model,
        analysis_version=report.analysis_version,
        summary=content.get("summary", ""),
        findings=[ReportFinding(**finding) for finding in content.get("findings", [])],
        recommendations=content.get("recommendations", []),
        grounded=report.grounded,
        created_at=report.created_at,
    )


@router.get("/games/{game_id}", response_model=GameReportSummary)
async def get_game_report(
    game_id: uuid.UUID,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    persona: Persona = Persona.SELF_LEARNER,
    regenerate: bool = False,
) -> GameReportSummary:
    """The latest report for a game in the requested profile, generating one on demand
    if none exists yet or the stored one predates the game's current analysis run.

    `regenerate=true` forces a fresh generation for the explicit "Regenerate" action,
    matching the pattern-feedback and training routes.
    """
    game = await session.get(Game, game_id)
    if game is None or game.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    analysis = await get_latest_analysis(session, game_id, profile_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this game yet",
        )

    opening = await get_opening_match(session, game_id, profile_id)
    findings = await get_pattern_findings(session, game_id, profile_id)

    service = ReportService(session, llm_provider, settings.reports, settings.llm)
    report = await service.get_or_generate(
        game=game,
        analysis=analysis,
        opening=opening,
        motifs=findings.motifs,
        themes=findings.themes,
        persona=persona,
        regenerate=regenerate,
    )
    return _to_summary(report)


@router.get("/games/{game_id}/story", response_model=GameReportSummary)
async def get_game_story(
    game_id: uuid.UUID,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    regenerate: bool = False,
) -> GameReportSummary:
    """The full opening/middlegame/endgame game-story report (Phase 16b) —
    self-learner only, no `persona` query param (unlike `get_game_report`).

    `regenerate=true` forces a fresh one for the explicit "Regenerate" action.
    """
    game = await session.get(Game, game_id)
    if game is None or game.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    analysis = await get_latest_analysis(session, game_id, profile_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this game yet",
        )

    opening = await get_opening_match(session, game_id, profile_id)
    findings = await get_pattern_findings(session, game_id, profile_id)

    service = ReportService(session, llm_provider, settings.reports, settings.llm)
    report = await service.get_or_generate_story(
        game=game,
        analysis=analysis,
        opening=opening,
        motifs=findings.motifs,
        themes=findings.themes,
        regenerate=regenerate,
    )
    return _to_summary(report)


@router.get("/games/{game_id}/pattern-feedback", response_model=PatternFeedbackSummary)
async def get_pattern_feedback(
    game_id: uuid.UUID,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    regenerate: bool = False,
) -> PatternFeedbackSummary:
    """This game compared against the profile's previous analyzed games (Phase 19,
    D-037) — self-learner only, like the story report.

    Returns 404 with the same "no analysis" detail the sibling routes use when the game
    itself is not analyzed yet, so the frontend's existing pending-vs-error distinction
    applies here unchanged. A thin baseline is *not* an error: it comes back as a normal
    response with `sufficient_baseline: false` and a null report.

    `regenerate=true` forces a fresh generation for the explicit "Regenerate" action,
    matching `/reports/profile/training`'s existing contract."""
    game = await session.get(Game, game_id)
    if game is None or game.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    analysis = await get_latest_analysis(session, game_id, profile_id)
    baseline = await load_baseline(
        session, profile_id, game_id, settings.game_feedback.game_feedback_baseline_window
    )
    if analysis is None or baseline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this game yet",
        )

    service = PatternFeedbackService(
        session, llm_provider, settings.game_feedback, settings.reports, settings.llm
    )
    feedback = await service.get_or_generate(
        game=game, analysis=analysis, baseline=baseline, regenerate=regenerate
    )
    return _to_feedback_summary(game_id, feedback)


def _to_feedback_summary(game_id: uuid.UUID, feedback: PatternFeedback) -> PatternFeedbackSummary:
    comparison = feedback.comparison
    return PatternFeedbackSummary(
        game_id=game_id,
        baseline_games=comparison.baseline_games,
        sufficient_baseline=comparison.sufficient_baseline,
        attributable=comparison.attributable,
        outcome=comparison.outcome,
        overall_band=comparison.overall_band,
        repeated=[
            RepeatedWeaknessSummary(
                kind=item.kind,
                name=item.name,
                baseline_games_with_finding=item.baseline_games_with_finding,
                baseline_games=item.baseline_games,
                occurrence_rate=item.occurrence_rate,
                move_numbers=[move_number(ply) for ply in item.plies],
            )
            for item in comparison.repeated
        ],
        improved=[
            ImprovedWeaknessSummary(
                kind=item.kind,
                name=item.name,
                baseline_games_with_finding=item.baseline_games_with_finding,
                baseline_games=item.baseline_games,
                occurrence_rate=item.occurrence_rate,
                clear_streak=item.clear_streak,
                sustained=item.sustained,
            )
            for item in comparison.improved
        ],
        metrics=[
            MetricComparisonSummary(
                name=item.name,
                value=item.value,
                baseline_mean=item.baseline_mean,
                z_score=item.z_score,
                band=item.band,
            )
            for item in comparison.metrics
        ],
        report=_to_summary(feedback.report) if feedback.report is not None else None,
    )


def _to_training_summary(recommendation: TrainingRecommendation) -> TrainingRecommendationSummary:
    content = recommendation.content
    return TrainingRecommendationSummary(
        id=recommendation.id,
        profile_id=recommendation.profile_id,
        persona=recommendation.persona.value,
        window_size=recommendation.window_size,
        source=recommendation.source.value,
        model=recommendation.model,
        snapshot_version=recommendation.snapshot_version,
        summary=content.get("summary", ""),
        findings=[ReportFinding(**finding) for finding in content.get("findings", [])],
        recommendations=content.get("recommendations", []),
        themes_covered=recommendation.themes_covered,
        grounded=recommendation.grounded,
        created_at=recommendation.created_at,
    )


@router.get("/profile/training", response_model=TrainingRecommendationSummary)
async def get_training_plan(
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    embedding_provider: EmbeddingProviderDep,
    persona: Persona = Persona.SELF_LEARNER,
    window: int | None = None,
    regenerate: bool = False,
) -> TrainingRecommendationSummary:
    """The training plan for the requested profile, persona, and analytics window.

    Get-or-generate, like `/reports/games/{id}`: the stored plan is returned while the
    analytics snapshot it was built from is still current, and a new one is generated
    otherwise. D-032's "on-demand, no scheduler" governs *cadence* — it never called for
    re-deriving an identical plan (and spending an LLM call) on every dashboard render.
    `regenerate=true` forces a fresh one for the explicit "Regenerate" action.

    `window` defaults and validates the same way `/analytics/profile` does, since the
    plan is built directly from that same windowed snapshot."""
    window_size = window if window is not None else settings.analytics.analytics_default_window
    allowed_windows = settings.analytics.window_sizes_list
    if window_size not in allowed_windows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"window must be one of {allowed_windows}",
        )

    service = TrainingService(
        session,
        llm_provider,
        embedding_provider,
        settings.reports,
        settings.llm,
        settings.retrieval,
        settings.analytics,
    )
    recommendation = await service.get_or_generate(
        profile_id=profile_id,
        persona=persona,
        window_size=window_size,
        regenerate=regenerate,
    )
    return _to_training_summary(recommendation)


__all__ = ["router"]
