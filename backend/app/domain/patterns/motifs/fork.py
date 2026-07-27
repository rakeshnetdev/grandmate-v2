"""Fork: one piece attacking two or more valuable enemy targets at once.

Lowest-difficulty motif in the taxonomy (`glossary.md`) — a direct read of the position
after the move, no history needed.
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
    moved_piece = board_after.piece_at(move.to_square)
    if moved_piece is None:
        return None

    attacker_color = moved_piece.color
    targets = [
        square
        for square in board_after.attacks(move.to_square)
        if (target := board_after.piece_at(square)) is not None
        and target.color != attacker_color
        # The king is always a qualifying target regardless of the value floor — it has
        # no trade value (PIECE_VALUES_CP[KING] == 0 on purpose, see that constant's
        # docstring), but a check threat is significant however low that number reads.
        and (
            target.piece_type == chess.KING
            or PIECE_VALUES_CP[target.piece_type] >= settings.motif_fork_min_target_value_cp
        )
    ]
    if len(targets) < 2:
        return None

    has_king_target = any(board_after.piece_at(sq).piece_type == chess.KING for sq in targets)  # type: ignore[union-attr]
    # A royal fork (king + at least one other piece) is essentially unmissable coaching
    # value and structurally unambiguous; a fork of two non-royal pieces is still a real
    # fork but leaves more room for "but one of them just moves away next turn" nuance.
    confidence = 0.9 if has_king_target else 0.7

    return MotifDetection(
        confidence=confidence,
        evidence={
            "from_square": chess.square_name(move.to_square),
            "target_squares": [chess.square_name(sq) for sq in targets],
        },
    )


__all__ = ["detect"]
