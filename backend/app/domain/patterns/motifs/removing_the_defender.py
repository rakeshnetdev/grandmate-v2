"""Removing the defender: the move captures a piece that was the sole defender of
another enemy piece or square, leaving that second target hanging. Requires modelling the
defensive relationship the capture just broke, not only the capture itself — medium
difficulty per the glossary.
"""

from __future__ import annotations

import chess

from app.core.config import PatternSettings
from app.domain.patterns.chess_constants import PIECE_VALUES_CP
from app.domain.patterns.motifs.base import MotifDetection


def _captured_square(board_before: chess.Board, move: chess.Move) -> chess.Square:
    """Where the captured piece actually sat before the move. Differs from `move.to_square`
    only for en passant, where the captured pawn is not on the destination square."""
    if board_before.is_en_passant(move):
        direction = -8 if board_before.turn == chess.WHITE else 8
        return move.to_square + direction
    return move.to_square


def detect(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    settings: PatternSettings,
) -> MotifDetection | None:
    if not board_before.is_capture(move):
        return None

    captured_square = _captured_square(board_before, move)
    captured_piece = board_before.piece_at(captured_square)
    if captured_piece is None:
        return None

    enemy_color = captured_piece.color
    mover_color = board_before.turn

    # What did the just-captured piece defend, one move ago?
    formerly_defended = [
        square
        for square, piece in board_before.piece_map().items()
        if piece.color == enemy_color
        and square != captured_square
        and captured_square in board_before.attackers(enemy_color, square)
    ]

    newly_hanging = [
        square
        for square in formerly_defended
        if (piece := board_after.piece_at(square)) is not None
        and PIECE_VALUES_CP[piece.piece_type] >= settings.motif_hanging_piece_min_value_cp
        and board_after.attackers(mover_color, square)
        and not board_after.attackers(enemy_color, square)
    ]
    if not newly_hanging:
        return None

    square = max(
        newly_hanging,
        key=lambda sq: PIECE_VALUES_CP[board_after.piece_at(sq).piece_type],  # type: ignore[union-attr]
    )
    return MotifDetection(
        confidence=0.7,
        evidence={
            "removed_defender_square": chess.square_name(captured_square),
            "newly_hanging_square": chess.square_name(square),
        },
    )


__all__ = ["detect"]
