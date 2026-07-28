"""Persona report generation and retrieval (Phase 9, D-023).

Thin per the "routes delegate" rule: orchestration lives in `domain/reports/service.py`.
`profile_id` scoping follows `analysis.py`/`patterns.py`'s exact pattern
(`ScopedProfileIdDep`, Phase 8b) — a report belongs to whichever profile the game itself
belongs to.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.llm import LLMProviderDep
from app.api.dependencies.profile_scope import ScopedProfileIdDep
from app.api.dependencies.settings import SettingsDep
from app.db.models import Game, GameReport, Persona
from app.domain.analysis import get_latest_analysis
from app.domain.patterns.queries import get_opening_match, get_pattern_findings
from app.domain.reports import ReportService
from app.schemas.reports import GameReportSummary, ReportFinding

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


__all__ = ["router"]
