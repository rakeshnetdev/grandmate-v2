"""Space advantage: `side`'s pawns are, on average, meaningfully more advanced than the
opponent's, at the position the game ended in.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection
from app.domain.patterns.themes.board_helpers import pawn_advancement, pawn_squares


def _average_advancement(board: chess.Board, side: GameColor) -> float:
    squares = pawn_squares(board, side)
    if not squares:
        return 0.0
    return sum(pawn_advancement(sq, side) for sq in squares) / len(squares)


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    if not plies:
        return None

    final_board = plies[-1].board_after
    enemy = GameColor.BLACK if side == GameColor.WHITE else GameColor.WHITE
    side_advancement = _average_advancement(final_board, side)
    enemy_advancement = _average_advancement(final_board, enemy)
    differential = side_advancement - enemy_advancement

    if differential < settings.theme_space_advantage_min_rank_differential:
        return None

    return ThemeDetection(
        ply=plies[-1].ply,
        confidence=0.6,
        evidence={
            "side_average_advancement": round(side_advancement, 2),
            "opponent_average_advancement": round(enemy_advancement, 2),
        },
    )


__all__ = ["detect"]
