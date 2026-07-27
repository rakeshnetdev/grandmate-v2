"""Standard chess facts shared by motif and theme detectors.

Not configuration (see `PatternSettings`'s docstring): piece values are a universal
domain fact, not a product policy someone might want to tune per deployment.
"""

from __future__ import annotations

import chess

PIECE_VALUES_CP: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,  # never traded, never a "target value" comparison operand
}

__all__ = ["PIECE_VALUES_CP"]
