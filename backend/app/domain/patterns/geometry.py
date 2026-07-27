"""Ray-walking helpers shared by the sliding-piece motif detectors (skewer, x-ray).

Pin has no need of this — `chess.Board.is_pinned`/`chess.Board.pin` already answer "is
this piece pinned, and along which ray" directly. Skewer and x-ray need to walk a ray and
inspect the first two occupied squares along it, which python-chess has no built-in for.
"""

from __future__ import annotations

from collections.abc import Iterator

import chess

_ORTHOGONAL: list[tuple[int, int]] = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_DIAGONAL: list[tuple[int, int]] = [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def sliding_directions(piece_type: chess.PieceType) -> list[tuple[int, int]]:
    """The (file, rank) step directions a sliding piece moves along. Empty for
    non-sliding piece types — callers use this to skip them, not to error."""
    if piece_type == chess.BISHOP:
        return _DIAGONAL
    if piece_type == chess.ROOK:
        return _ORTHOGONAL
    if piece_type == chess.QUEEN:
        return _ORTHOGONAL + _DIAGONAL
    return []


def walk_ray(origin: chess.Square, direction: tuple[int, int]) -> Iterator[chess.Square]:
    """Every square from (but not including) `origin` to the board edge, in `direction`
    order. Board occupancy is irrelevant here — callers filter for occupied squares
    themselves, since "first two occupied squares along the ray" is the shape every
    caller of this function actually wants."""
    df, dr = direction
    file, rank = chess.square_file(origin) + df, chess.square_rank(origin) + dr
    while 0 <= file < 8 and 0 <= rank < 8:
        yield chess.square(file, rank)
        file += df
        rank += dr


def first_two_occupied(
    board: chess.Board, origin: chess.Square, direction: tuple[int, int]
) -> list[tuple[chess.Square, chess.Piece]]:
    """The first two occupied squares (with their pieces) along a ray from `origin`,
    in ray order. Returns fewer than two entries if the ray runs off the board first."""
    occupied: list[tuple[chess.Square, chess.Piece]] = []
    for square in walk_ray(origin, direction):
        piece = board.piece_at(square)
        if piece is not None:
            occupied.append((square, piece))
            if len(occupied) == 2:
                break
    return occupied


__all__ = ["first_two_occupied", "sliding_directions", "walk_ray"]
