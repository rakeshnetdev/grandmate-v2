"""Discovered attack: moving one piece unmasks an attack from a *different* piece that
was blocked before the move. Requires tracking the unmasked line, not just the square the
moved piece landed on — that is what makes this medium rather than low difficulty.
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

    discoveries: list[tuple[chess.Square, chess.Piece]] = []
    for square, piece in board_after.piece_map().items():
        if piece.color != enemy_color:
            continue
        newly_attacking = board_after.attackers(mover_color, square) - board_before.attackers(
            mover_color, square
        )
        # The moved piece directly attacking something new is just a normal attack, not a
        # *discovered* one — the whole point is a different piece's line opening up.
        newly_attacking.discard(move.to_square)
        if newly_attacking:
            discoveries.append((square, piece))

    if not discoveries:
        return None

    # A discovered check (king target) is always the headline finding, however many other
    # pieces also came under fire — PIECE_VALUES_CP[KING] == 0 alone would rank it last.
    target_square, target_piece = max(
        discoveries,
        key=lambda item: (item[1].piece_type == chess.KING, PIECE_VALUES_CP[item[1].piece_type]),
    )
    confidence = 0.85 if target_piece.piece_type == chess.KING else 0.65
    return MotifDetection(
        confidence=confidence,
        evidence={
            "target_square": chess.square_name(target_square),
            "vacated_square": chess.square_name(move.from_square),
        },
    )


__all__ = ["detect"]
