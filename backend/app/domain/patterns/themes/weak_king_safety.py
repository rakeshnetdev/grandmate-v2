"""Weak king safety: at the position the game ended in, how much of `side`'s pawn shield
survives in front of its own king. Missing shield pawns are the single most common
concrete signal of king exposure, and unlike "open files toward the king" they don't
require reasoning about enemy piece placement to be meaningful on their own.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection
from app.domain.patterns.themes.board_helpers import king_shield_squares, pawn_squares


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    if not plies:
        return None

    final_board = plies[-1].board_after
    shield_squares = king_shield_squares(final_board, side)
    if not shield_squares:
        return None

    side_pawns = set(pawn_squares(final_board, side))
    present = sum(1 for square in shield_squares if square in side_pawns)
    missing = len(shield_squares) - present
    if missing < 2:
        return None

    confidence = 0.7 if missing == len(shield_squares) else 0.5
    return ThemeDetection(
        ply=plies[-1].ply,
        confidence=confidence,
        evidence={
            "shield_squares_expected": len(shield_squares),
            "shield_pawns_present": present,
        },
    )


__all__ = ["detect"]
