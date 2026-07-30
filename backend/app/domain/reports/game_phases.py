"""Opening/middlegame/endgame phase segmentation for the game-story report (Phase 16b).

Adapted in spirit from the sibling `grandmate/` app's ply-count/material heuristic (no
code copied — see `changes/0001-reuse-ledger.md`), but computed once here for narrative
sectioning, rather than per-move theme tagging as the sibling does.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from app.db.models import GameMove, OpeningMatch

# Same ply cutoff the sibling app uses to tag an individual move "Opening" when there is
# no book match to narrow it down — a crude but reasonable default.
_DEFAULT_OPENING_PLY_CUTOFF = 12

# Combined queen/rook/bishop/knight count (both sides) at or below which a position
# counts as an endgame — same heuristic and threshold the sibling app uses.
_ENDGAME_MATERIAL_THRESHOLD = 6


@dataclass(frozen=True)
class GamePhases:
    """Ply ranges (0-indexed), inclusive of the boundary ply itself.

    `endgame_start_ply` is `None` when the game never reaches a position at or below the
    material threshold — most decisive middlegame games. Callers must treat
    `opening_end_ply >= endgame_start_ply` (a short, sharp game) as "no middlegame
    section", not as an error.
    """

    opening_end_ply: int
    endgame_start_ply: int | None
    total_plies: int


def segment_game_phases(moves: list[GameMove], opening: OpeningMatch | None) -> GamePhases:
    """`moves` must be ply-ordered, as `get_moves` already returns them."""
    total_plies = len(moves)
    opening_end_ply = min(
        opening.matched_ply if opening is not None else _DEFAULT_OPENING_PLY_CUTOFF,
        total_plies,
    )

    endgame_start_ply = None
    for move in moves:
        if _major_minor_piece_count(move.fen_after) <= _ENDGAME_MATERIAL_THRESHOLD:
            endgame_start_ply = move.ply + 1  # the position *after* this move
            break

    return GamePhases(
        opening_end_ply=opening_end_ply,
        endgame_start_ply=endgame_start_ply,
        total_plies=total_plies,
    )


def _major_minor_piece_count(fen: str) -> int:
    board = chess.Board(fen)
    return sum(
        len(board.pieces(piece_type, color))
        for color in (chess.WHITE, chess.BLACK)
        for piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
    )


__all__ = ["GamePhases", "segment_game_phases"]
