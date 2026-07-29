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
from app.domain.patterns.queries import get_opening_match, get_pattern_findings
from app.domain.reports import ReportService, TrainingService
from app.schemas.reports import GameReportSummary, ReportFinding, TrainingRecommendationSummary

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
) -> GameReportSummary:
    """The latest report for a game in the requested profile, generating one on demand
    if none exists yet or the stored one predates the game's current analysis run."""
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
    )
    return _to_summary(report)


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
) -> TrainingRecommendationSummary:
    """A fresh training plan for the requested profile, persona, and analytics window —
    always generated on demand (D-032: no caching, no scheduler), which is why this is
    the one report-family endpoint with no "existing and fresh" branch. `window`
    defaults and validates the same way `/analytics/profile` does, since the plan is
    built directly from that same windowed snapshot."""
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
    recommendation = await service.generate(
        profile_id=profile_id, persona=persona, window_size=window_size
    )
    return _to_training_summary(recommendation)


__all__ = ["router"]
