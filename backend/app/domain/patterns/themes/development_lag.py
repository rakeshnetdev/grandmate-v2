"""Development lag: at the point `THEME_OPENING_PHASE_PLY_CUTOFF` is reached (or the
game's end, if it ended sooner), `side` still has most of its minor pieces on their home
squares.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection
from app.domain.patterns.themes.board_helpers import HOME_MINOR_SQUARES


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    if not plies:
        return None

    cutoff_ply = min(settings.theme_opening_phase_ply_cutoff, plies[-1].ply)
    # The last ply at or before the cutoff — plies are contiguous from 0, so this is
    # always found while the loop above still has at least one entry.
    checkpoint = next(p for p in reversed(plies) if p.ply <= cutoff_ply)

    home_squares = HOME_MINOR_SQUARES[side]
    board = checkpoint.board_after
    chess_color = chess.WHITE if side == GameColor.WHITE else chess.BLACK
    undeveloped = [
        square
        for square in home_squares
        if (piece := board.piece_at(square)) is not None
        and piece.color == chess_color
        and piece.piece_type in (chess.KNIGHT, chess.BISHOP)
    ]
    if len(undeveloped) < 2:
        return None

    return ThemeDetection(
        ply=checkpoint.ply,
        confidence=0.5 + 0.1 * len(undeveloped),
        evidence={
            "undeveloped_squares": [chess.square_name(sq) for sq in undeveloped],
            "checkpoint_ply": checkpoint.ply,
        },
    )


__all__ = ["detect"]
