"""Centre control: at the position the game ended in, `side` occupies or attacks more of
d4/d5/e4/e5 than the opponent does.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection
from app.domain.patterns.themes.board_helpers import CENTRE_SQUARES


def _control_count(board: chess.Board, chess_color: chess.Color) -> int:
    count = 0
    for square in CENTRE_SQUARES:
        occupant = board.piece_at(square)
        if (occupant is not None and occupant.color == chess_color) or board.attackers(
            chess_color, square
        ):
            count += 1
    return count


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    if not plies:
        return None

    final_board = plies[-1].board_after
    chess_color = chess.WHITE if side == GameColor.WHITE else chess.BLACK
    side_count = _control_count(final_board, chess_color)
    opponent_count = _control_count(final_board, not chess_color)

    if side_count - opponent_count < 2:
        return None

    return ThemeDetection(
        ply=plies[-1].ply,
        confidence=0.6,
        evidence={"side_control": side_count, "opponent_control": opponent_count},
    )


__all__ = ["detect"]
