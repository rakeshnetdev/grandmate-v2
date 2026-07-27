"""Hanging piece: after the move, one of the mover's own pieces is attacked and has zero
defenders. High frequency, high coaching value per the glossary — this is the motif the
training-theme map ties directly to "blunder-check discipline".

Deliberately checks the *mover's own* pieces, not the opponent's: this motif exists to
catch the player's own blunders, matching how `training_map.py` uses it.
"""

from __future__ import annotations

import chess

from app.core.config import PatternSettings
from app.domain.patterns.chess_constants import PIECE_VALUES_CP
from app.domain.patterns.motifs.base import MotifDetection


def detect(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    settings: PatternSettings,
) -> MotifDetection | None:
    mover_color = board_before.turn
    enemy_color = not mover_color

    hanging_squares = [
        square
        for square, piece in board_after.piece_map().items()
        if piece.color == mover_color
        and PIECE_VALUES_CP[piece.piece_type] >= settings.motif_hanging_piece_min_value_cp
        and board_after.attackers(enemy_color, square)
        and not board_after.attackers(mover_color, square)
    ]
    if not hanging_squares:
        return None

    # The most valuable hanging piece is the one worth surfacing to a learner first.
    square = max(
        hanging_squares,
        key=lambda sq: PIECE_VALUES_CP[board_after.piece_at(sq).piece_type],  # type: ignore[union-attr]
    )
    piece = board_after.piece_at(square)
    assert piece is not None  # square came from board_after.piece_map()
    return MotifDetection(
        confidence=0.8,
        evidence={"hanging_square": chess.square_name(square), "piece": piece.symbol()},
    )


__all__ = ["detect"]
