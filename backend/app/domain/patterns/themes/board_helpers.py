"""Small structural queries shared by several theme detectors — kept out of any one
detector module so "what counts as doubled/isolated" has exactly one definition.
"""

from __future__ import annotations

import chess

from app.db.models import GameColor

CENTRE_SQUARES = (chess.D4, chess.D5, chess.E4, chess.E5)

# Knight/bishop starting squares, keyed by side — used by development_lag to check how
# many minors never left home.
HOME_MINOR_SQUARES: dict[GameColor, tuple[chess.Square, ...]] = {
    GameColor.WHITE: (chess.B1, chess.C1, chess.F1, chess.G1),
    GameColor.BLACK: (chess.B8, chess.C8, chess.F8, chess.G8),
}


def _to_chess_color(side: GameColor) -> chess.Color:
    return chess.WHITE if side == GameColor.WHITE else chess.BLACK


def pawn_squares(board: chess.Board, side: GameColor) -> list[chess.Square]:
    return list(board.pieces(chess.PAWN, _to_chess_color(side)))


def doubled_pawn_files(board: chess.Board, side: GameColor) -> list[int]:
    """Files with two or more of `side`'s own pawns."""
    counts: dict[int, int] = {}
    for square in pawn_squares(board, side):
        file = chess.square_file(square)
        counts[file] = counts.get(file, 0) + 1
    return [file for file, count in counts.items() if count >= 2]


def isolated_pawn_files(board: chess.Board, side: GameColor) -> list[int]:
    """Files holding a `side` pawn with no `side` pawn on either adjacent file."""
    files_with_pawns = {chess.square_file(sq) for sq in pawn_squares(board, side)}
    return [
        file
        for file in files_with_pawns
        if (file - 1) not in files_with_pawns and (file + 1) not in files_with_pawns
    ]


def king_shield_squares(board: chess.Board, side: GameColor) -> list[chess.Square]:
    """The three squares one rank in front of `side`'s king — the classic pawn shield.
    Off-board squares (a king on the back rank has no rank behind it to shield, but every
    king has a rank in front) are simply omitted, not padded."""
    king_square = board.king(_to_chess_color(side))
    if king_square is None:
        return []
    forward = 1 if side == GameColor.WHITE else -1
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    squares = []
    for delta_file in (-1, 0, 1):
        file = king_file + delta_file
        rank = king_rank + forward
        if 0 <= file < 8 and 0 <= rank < 8:
            squares.append(chess.square(file, rank))
    return squares


def passed_pawn_squares(board: chess.Board, side: GameColor) -> set[chess.Square]:
    """`side`'s pawns with no enemy pawn on the same or an adjacent file ahead of them."""
    enemy = GameColor.BLACK if side == GameColor.WHITE else GameColor.WHITE
    enemy_pawns = pawn_squares(board, enemy)
    passed = set()
    for square in pawn_squares(board, side):
        file, rank = chess.square_file(square), chess.square_rank(square)
        blocked = any(
            abs(chess.square_file(enemy_sq) - file) <= 1
            and (
                chess.square_rank(enemy_sq) > rank
                if side == GameColor.WHITE
                else chess.square_rank(enemy_sq) < rank
            )
            for enemy_sq in enemy_pawns
        )
        if not blocked:
            passed.add(square)
    return passed


def pawn_advancement(square: chess.Square, side: GameColor) -> int:
    """How far a pawn has travelled from its own side's second rank, 0-5. Same scale for
    both colours so a White and a Black pawn's advancement can be compared directly."""
    rank = chess.square_rank(square)
    return rank - 1 if side == GameColor.WHITE else 6 - rank


__all__ = [
    "CENTRE_SQUARES",
    "HOME_MINOR_SQUARES",
    "doubled_pawn_files",
    "isolated_pawn_files",
    "king_shield_squares",
    "passed_pawn_squares",
    "pawn_advancement",
    "pawn_squares",
]
