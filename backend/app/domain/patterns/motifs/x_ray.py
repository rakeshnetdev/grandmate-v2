"""X-ray: a sliding piece's line of control passes through an enemy piece to reinforce
one of the mover's own pieces sitting behind it — latent support that isn't visible from
attack counts alone, since the enemy piece in between blocks the "real" attack.

Distinguished from skewer/pin by what's on the far side of the line: those two are about
threatening the enemy piece in front; x-ray is about the mover's own piece being braced
through it.
"""

from __future__ import annotations

import chess

from app.core.config import PatternSettings
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

    mover_color = moved_piece.color
    for direction in sliding_directions(moved_piece.piece_type):
        occupied = first_two_occupied(board_after, move.to_square, direction)
        if len(occupied) < 2:
            continue
        (through_square, through_piece), (supported_square, supported_piece) = occupied
        if through_piece.color == mover_color:
            continue  # not x-raying through an enemy piece
        if supported_piece.color != mover_color:
            continue  # the far piece must be the mover's own to call this "support"
        return MotifDetection(
            confidence=0.6,
            evidence={
                "attacking_square": chess.square_name(move.to_square),
                "through_square": chess.square_name(through_square),
                "supported_square": chess.square_name(supported_square),
            },
        )
    return None


__all__ = ["detect"]
