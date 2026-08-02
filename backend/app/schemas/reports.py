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


class RepeatedWeaknessSummary(BaseModel):
    kind: str
    name: str
    baseline_games_with_finding: int
    baseline_games: int
    occurrence_rate: float
    move_numbers: list[int]


class ImprovedWeaknessSummary(BaseModel):
    kind: str
    name: str
    baseline_games_with_finding: int
    baseline_games: int
    occurrence_rate: float
    clear_streak: int
    # False means "absent from this one game", not "fixed" — the frontend words the two
    # differently, so this flag has to survive the trip rather than being flattened away.
    sustained: bool


class MetricComparisonSummary(BaseModel):
    name: str
    value: float
    baseline_mean: float
    z_score: float | None
    band: str


class PatternFeedbackSummary(BaseModel):
    """Phase 19, D-037: one game against its recent history.

    Carries the deterministic comparison alongside the narrative, rather than only the
    prose: the tab renders the numbers itself and uses the report for explanation, so a
    reader can see the sample the claims rest on. `report` is null when the baseline is
    too thin to support any claim at all — `sufficient_baseline` says why.
    """

    game_id: uuid.UUID
    baseline_games: int
    sufficient_baseline: bool
    attributable: bool
    outcome: str
    overall_band: str
    repeated: list[RepeatedWeaknessSummary]
    improved: list[ImprovedWeaknessSummary]
    metrics: list[MetricComparisonSummary]
    report: GameReportSummary | None


__all__ = [
    "GameReportSummary",
    "ImprovedWeaknessSummary",
    "MetricComparisonSummary",
    "PatternFeedbackSummary",
    "RepeatedWeaknessSummary",
    "ReportFinding",
    "TrainingRecommendationSummary",
]
