"""Skewer: the inverse of a pin. A valuable enemy piece is attacked along a line and,
directly behind it on the same line, sits a less valuable enemy piece that becomes
capturable once the front piece is forced to move.
"""

from __future__ import annotations

import chess

from app.core.config import PatternSettings
from app.domain.patterns.chess_constants import PIECE_VALUES_CP
from app.domain.patterns.geometry import first_two_occupied, sliding_directions
from app.domain.patterns.motifs.base import MotifDetection


def detect(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    settings: PatternSettings,
) -> MotifDetection | None:
    moved_piece = board_after.piece_at(move.to_square)
    if moved_piece is None:
        return None

    enemy_color = not moved_piece.color
    for direction in sliding_directions(moved_piece.piece_type):
        occupied = first_two_occupied(board_after, move.to_square, direction)
        if len(occupied) < 2:
            continue
        (front_square, front_piece), (back_square, back_piece) = occupied
        if front_piece.color != enemy_color or back_piece.color != enemy_color:
            continue
        # A king behind the front piece is a *pin* (see pin.py) — PIECE_VALUES_CP[KING]
        # is deliberately 0 (it is never a trade-value operand), which would otherwise
        # make every pin also register here, since any real piece's value is > 0.
        if back_piece.piece_type == chess.KING:
            continue
        # A king *in front* is the mirror case: it is forced to move because it is in
        # check, regardless of its (deliberately 0) trade value, so it always outranks
        # whatever sits behind it on the line — the plain value comparison below would
        # otherwise never fire for this case (0 is never greater than a real piece's
        # value), silently missing the classic "check exposes a piece behind the king"
        # skewer.
        if (
            front_piece.piece_type == chess.KING
            or PIECE_VALUES_CP[front_piece.piece_type] > PIECE_VALUES_CP[back_piece.piece_type]
        ):
            return MotifDetection(
                confidence=0.75,
                evidence={
                    "attacking_square": chess.square_name(move.to_square),
                    "front_square": chess.square_name(front_square),
                    "back_square": chess.square_name(back_square),
                },
            )
    return None


__all__ = ["detect"]
