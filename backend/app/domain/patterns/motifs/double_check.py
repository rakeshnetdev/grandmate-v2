"""Double check: the move delivers check from two pieces at once. Mechanically
detectable straight from the checker count python-chess already computes — no heuristic
judgement involved, hence the lowest possible detection difficulty in the taxonomy.
"""

from __future__ import annotations

import chess

from app.core.config import PatternSettings
from app.domain.patterns.motifs.base import MotifDetection


def detect(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    settings: PatternSettings,
) -> MotifDetection | None:
    checkers = board_after.checkers()
    if len(checkers) < 2:
        return None
    return MotifDetection(
        confidence=0.99,
        evidence={"checker_squares": [chess.square_name(sq) for sq in checkers]},
    )


__all__ = ["detect"]
