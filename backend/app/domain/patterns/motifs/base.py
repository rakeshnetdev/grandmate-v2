"""Shared shape for every motif detector.

Every detector is a pure function over one ply's before/after positions plus the
detection-policy thresholds in `PatternSettings` — no database access, no engine call, no
side effects. That is what makes each one independently testable on a curated FEN without
any fixture heavier than a `chess.Board`.

Confidence corroboration against `MoveEvaluation` (this ply's engine classification, once
a `GameAnalysis` exists) is deliberately **not** a detector's job — it happens once, in
`app/domain/patterns/confidence.py`, applied uniformly by the orchestrating service. A
detector answers "is this motif structurally present"; only the service decides how much
an engine's independent judgement should move that confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import chess

from app.core.config import PatternSettings


@dataclass(frozen=True)
class MotifDetection:
    """What a detector found. `side` is not carried here — the orchestrating service
    already knows it (the mover is always `board_before.turn`), so every detector would
    otherwise be repeating the same line for no benefit."""

    confidence: float
    evidence: dict[str, object]


class MotifDetector(Protocol):
    """Signature every motif detector module's `detect` function must match."""

    def __call__(
        self,
        board_before: chess.Board,
        move: chess.Move,
        board_after: chess.Board,
        settings: PatternSettings,
    ) -> MotifDetection | None: ...


__all__ = ["MotifDetection", "MotifDetector"]
