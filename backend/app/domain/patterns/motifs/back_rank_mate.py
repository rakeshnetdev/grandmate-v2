"""Back-rank mate: checkmate delivered against a king trapped on its own back rank by its
own pieces (classically pawns on the second/seventh rank) leaving no escape square.
Highly constrained pattern per the glossary, hence low difficulty.
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

    mated_color = board_after.turn  # the side to move is the side just mated
    king_square = board_after.king(mated_color)
    if king_square is None:
        return None

    back_rank = 0 if mated_color == chess.WHITE else 7
    if chess.square_rank(king_square) != back_rank:
        return None

    # The classic pattern: every square directly in front of the king (toward the
    # centre) is occupied by the mated side's own pieces, which is what traps the king
    # on the back rank in the first place.
    forward = 1 if mated_color == chess.WHITE else -1
    king_file = chess.square_file(king_square)
    for delta_file in (-1, 0, 1):
        file = king_file + delta_file
        if not (0 <= file < 8):
            continue
        escape_square = chess.square(file, back_rank + forward)
        occupant = board_after.piece_at(escape_square)
        if occupant is None or occupant.color != mated_color:
            return None

    return MotifDetection(confidence=0.9, evidence={"king_square": chess.square_name(king_square)})


__all__ = ["detect"]
