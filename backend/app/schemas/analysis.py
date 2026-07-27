"""Engine analysis request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AnalysisJobSummary(BaseModel):
    """An engine-analysis job's visible status. Same shape as imports' `JobSummary` —
    kept as a separate schema anyway, since the two resources evolve independently and a
    shared schema would couple them for no real benefit."""

    id: uuid.UUID
    kind: str
    status: str
    game_id: uuid.UUID | None
    error: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None


class MoveEvaluationSummary(BaseModel):
    ply: int
    eval_cp: int | None
    mate_in: int | None
    best_move_uci: str | None
    pv: list[str]
    classification: str
    eval_swing_cp: int
    is_critical_moment: bool
    deep_analyzed: bool


class GameAnalysisSummary(BaseModel):
    """A completed analysis run, with every ply's evaluation."""

    id: uuid.UUID
    game_id: uuid.UUID
    analysis_version: str
    engine_depth: int
    summary: dict[str, Any]
    completed_at: datetime | None
    moves: list[MoveEvaluationSummary]


__all__ = ["AnalysisJobSummary", "GameAnalysisSummary", "MoveEvaluationSummary"]
