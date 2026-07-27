"""Bad bishop: a bishop hemmed in by too many of its own pawns on its own square colour,
at the position the game ended in. A simplified read of "fixed" — this counts *any* own
pawn on the bishop's colour, not only pawns that are immobile — documented here as the
detector's known simplification rather than left implicit.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection
from app.domain.patterns.themes.board_helpers import pawn_squares


def _square_colour(square: chess.Square) -> bool:
    """True for a light square, matching `chess.Board.is_light_square` semantics without
    needing an extra dependency on it (it's a one-line parity check)."""
    file, rank = chess.square_file(square), chess.square_rank(square)
    return (file + rank) % 2 == 1


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    if not plies:
        return None

    final_board = plies[-1].board_after
    chess_color = chess.WHITE if side == GameColor.WHITE else chess.BLACK
    bishops = list(final_board.pieces(chess.BISHOP, chess_color))
    if not bishops:
        return None

    own_pawns = pawn_squares(final_board, side)
    for bishop_square in bishops:
        bishop_colour = _square_colour(bishop_square)
        same_colour_pawns = [sq for sq in own_pawns if _square_colour(sq) == bishop_colour]
        if len(same_colour_pawns) >= settings.theme_bad_bishop_min_fixed_pawns:
            return ThemeDetection(
                ply=plies[-1].ply,
                confidence=0.6,
                evidence={
                    "bishop_square": chess.square_name(bishop_square),
                    "same_colour_pawn_count": len(same_colour_pawns),
                },
            )
    return None


__all__ = ["detect"]
