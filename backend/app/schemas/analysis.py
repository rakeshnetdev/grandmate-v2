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
    # SAN/FEN come from `GameMove`, not `MoveEvaluation` — merged in by ply at the route
    # layer, the same pairing `orchestration/tools/analysis_tools.py`'s chat tool
    # already does. `None` only if canonicalization produced an evaluation for a ply
    # `GameMove` itself doesn't have, which should not happen in practice.
    san: str | None
    fen_after: str | None
    eval_cp: int | None
    mate_in: int | None
    best_move_uci: str | None
    # Readable notation for best_move_uci, stored at analysis time (Phase 16b) — what a
    # UI should show next to a mistake; null on analyses predating the column.
    best_move_san: str | None
    pv: list[str]
    classification: str
    eval_swing_cp: int
    # True when eval_swing_cp above is a forced-mate classification sentinel (see
    # domain/analysis/classification.py), not a real centipawn count — a consumer must
    # not display eval_swing_cp verbatim as centipawns when this is True.
    mate_swing: bool
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
