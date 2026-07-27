"""Pawn structure damage: doubled or isolated pawns present for `side` at the position
the game ended in. Checking the final position rather than "did this ever happen" is
deliberate — a doubled pawn that gets traded off two moves later isn't damage that
persisted, and persistence is what makes this a *structural* theme rather than a one-move
tactical blip.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection
from app.domain.patterns.themes.board_helpers import doubled_pawn_files, isolated_pawn_files


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    if not plies:
        return None

    final_board = plies[-1].board_after
    doubled = doubled_pawn_files(final_board, side)
    isolated = isolated_pawn_files(final_board, side)
    if not doubled and not isolated:
        return None

    # Both defects present is a stronger structural claim than either alone.
    confidence = 0.75 if doubled and isolated else 0.6
    return ThemeDetection(
        ply=plies[-1].ply,
        confidence=confidence,
        evidence={"doubled_files": doubled, "isolated_files": isolated},
    )


__all__ = ["detect"]
