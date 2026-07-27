"""Pin: an enemy piece cannot move without exposing its own king to check.

Absolute pins only (against the king) — python-chess's `is_pinned`/`pin` answer exactly
this directly. The glossary tracks relative pins (against a piece more valuable than the
king is impossible, so read: against a piece the opponent cannot afford to expose) as a
separate variant; that needs its own "which piece is worth protecting more" heuristic and
is deferred alongside the six high-difficulty motifs — shipping it half-considered here
would be a confident wrong label, exactly what the glossary's sequencing note warns
against.
"""

from __future__ import annotations

import chess

from app.core.config import PatternSettings
from app.domain.patterns.motifs.base import MotifDetection

_SLIDING_PIECES = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def detect(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    settings: PatternSettings,
) -> MotifDetection | None:
    moved_piece = board_after.piece_at(move.to_square)
    if moved_piece is None or moved_piece.piece_type not in _SLIDING_PIECES:
        return None

    enemy_color = not moved_piece.color
    for square, piece in board_after.piece_map().items():
        if piece.color != enemy_color or not board_after.is_pinned(enemy_color, square):
            continue
        # `pin()` returns the ray between the king and the pinner (inclusive of both).
        # The moved piece is only "the" pinner if it actually sits on that ray — without
        # this check, a pre-existing pin by some other piece would be misattributed to
        # this move.
        pin_ray = board_after.pin(enemy_color, square)
        if move.to_square in pin_ray:
            return MotifDetection(
                confidence=0.85,
                evidence={
                    "pinned_square": chess.square_name(square),
                    "pinning_square": chess.square_name(move.to_square),
                },
            )
    return None


__all__ = ["detect"]
