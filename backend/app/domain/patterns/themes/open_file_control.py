"""Open file control: a rook or queen of `side` occupies a file with no pawns (open) or
no pawns of `side`'s own (half-open), at the position the game ended in.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection
from app.domain.patterns.themes.board_helpers import pawn_squares


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    if not plies:
        return None

    final_board = plies[-1].board_after
    chess_color = chess.WHITE if side == GameColor.WHITE else chess.BLACK
    enemy = GameColor.BLACK if side == GameColor.WHITE else GameColor.WHITE

    own_pawn_files = {chess.square_file(sq) for sq in pawn_squares(final_board, side)}
    enemy_pawn_files = {chess.square_file(sq) for sq in pawn_squares(final_board, enemy)}

    for piece_type in (chess.ROOK, chess.QUEEN):
        for square in final_board.pieces(piece_type, chess_color):
            file = chess.square_file(square)
            if file in own_pawn_files:
                continue
            is_open = file not in enemy_pawn_files
            return ThemeDetection(
                ply=plies[-1].ply,
                confidence=0.65 if is_open else 0.55,
                evidence={
                    "square": chess.square_name(square),
                    "file": chess.FILE_NAMES[file],
                    "open": is_open,
                },
            )
    return None


__all__ = ["detect"]
