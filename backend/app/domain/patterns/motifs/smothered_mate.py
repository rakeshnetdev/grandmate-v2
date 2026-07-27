"""Smothered mate: checkmate by a knight where the king has no legal escape because every
adjacent square is occupied by the king's own pieces (not merely attacked — physically
blocked). Mechanically constrained, hence low difficulty per the glossary.
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
    if not board_after.is_checkmate():
        return None

    moved_piece = board_after.piece_at(move.to_square)
    if moved_piece is None or moved_piece.piece_type != chess.KNIGHT:
        return None

    mated_color = board_after.turn
    king_square = board_after.king(mated_color)
    if king_square is None:
        return None

    for adjacent_square in chess.SquareSet(chess.BB_KING_ATTACKS[king_square]):
        occupant = board_after.piece_at(adjacent_square)
        if occupant is None or occupant.color != mated_color:
            return None  # an empty or enemy square means the king isn't smothered

    return MotifDetection(confidence=0.95, evidence={"king_square": chess.square_name(king_square)})


__all__ = ["detect"]
