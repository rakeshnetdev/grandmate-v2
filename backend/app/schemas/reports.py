"""Persona report response schemas (Phase 9)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportFinding(BaseModel):
    fact_ids: list[str]
    text: str
    # Self-learner-game-format-only (Phase 16a, D-035 addendum): "strength" or
    # "mistake", so the frontend can group findings under "What Went Well" vs.
    # "Mistakes & Blunders". `None` for coach/kid, which don't use this format.
    kind: str | None = None


class GameReportSummary(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    persona: str
    source: str
    model: str | None
    analysis_version: str
    summary: str
    findings: list[ReportFinding]
    recommendations: list[str]
    grounded: bool
    created_at: datetime


class TrainingRecommendationSummary(BaseModel):
    """Phase 15, D-032. Same shape as `GameReportSummary` plus the two fields specific
    to a profile-level plan: `window_size` (which analytics window it was built from)
    and `themes_covered` (what history the next generation deprioritises)."""

    id: uuid.UUID
    profile_id: uuid.UUID
    persona: str
    window_size: int
    source: str
    model: str | None
    snapshot_version: str
    summary: str
    findings: list[ReportFinding]
    recommendations: list[str]
    themes_covered: list[str]
    grounded: bool
    created_at: datetime


__all__ = ["GameReportSummary", "ReportFinding", "TrainingRecommendationSummary"]
