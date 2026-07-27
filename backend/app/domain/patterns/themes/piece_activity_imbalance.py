"""Piece activity imbalance: a sustained mobility deficit for `side`, not a one-move dip.
Measured over the last `THEME_PIECE_ACTIVITY_WINDOW_PLIES` plies of the game — mobility
swings constantly move-to-move, so only a differential that holds for the *entire* window
counts as a pattern rather than noise.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    window = plies[-settings.theme_piece_activity_window_plies :]
    side_window = [p for p in window if p.side == side]
    # Need at least two data points to call a differential "sustained" rather than a
    # single snapshot — one move proves nothing about a pattern.
    if len(side_window) < 2:
        return None

    deficits = []
    for ply_context in side_window:
        # `LegalMoveGenerator` has no `len()`/`count()` — materializing the list is the
        # documented way to get a move count out of python-chess.
        side_mobility = len(list(ply_context.board_before.legal_moves))
        opponent_mobility = len(list(ply_context.board_after.legal_moves))
        deficits.append(opponent_mobility - side_mobility)

    if any(deficit <= 0 for deficit in deficits):
        return None  # the opponent wasn't ahead at every sampled point — not sustained

    return ThemeDetection(
        ply=side_window[0].ply,
        confidence=0.6,
        evidence={
            "window_plies": len(side_window),
            "average_mobility_deficit": sum(deficits) / len(deficits),
        },
    )


__all__ = ["detect"]
