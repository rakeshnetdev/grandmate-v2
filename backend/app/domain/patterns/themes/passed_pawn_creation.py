"""Passed pawn creation: a passed pawn appears for `side` and persists rather than being
traded off immediately. Tracked by file, not square, so a pawn advancing after it becomes
passed is still recognised as the same pawn.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess

from app.core.config import PatternSettings
from app.db.models import GameColor
from app.domain.patterns.themes.base import PlyContext, ThemeDetection
from app.domain.patterns.themes.board_helpers import passed_pawn_squares


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    side_plies = [p for p in plies if p.side == side]
    if not side_plies:
        return None

    previous_files: set[int] = set()
    creation: tuple[int, int, int] | None = None  # (ply, file, side-ply index created at)
    for index, ply_context in enumerate(side_plies):
        current_files = {
            chess.square_file(square)
            for square in passed_pawn_squares(ply_context.board_after, side)
        }
        newly_passed = current_files - previous_files
        if newly_passed and creation is None:
            creation = (ply_context.ply, min(newly_passed), index)
        elif creation is not None and creation[1] not in current_files:
            # Traded off or blocked before it could persist — keep watching for a
            # different file becoming passed and staying that way.
            creation = None
        elif (
            creation is not None and index - creation[2] >= settings.theme_passed_pawn_persist_plies
        ):
            # Survived long enough (in the side's own moves) to count as "created", even
            # if a later move eventually trades it off — the persistence bar has been met.
            break
        previous_files = current_files

    if creation is None:
        return None

    creation_ply, file, _ = creation
    return ThemeDetection(
        ply=creation_ply,
        confidence=0.7,
        evidence={"file": chess.FILE_NAMES[file]},
    )


__all__ = ["detect"]
