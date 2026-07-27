"""Shared shape for every strategic theme detector.

Unlike motifs, themes are span-of-plies judgements (glossary.md), so a detector gets the
whole game's context — every played ply, paired with its engine evaluation where one
exists — rather than a single before/after position pair. `PlyContext.board_after` is
derived from the stored FEN on demand rather than replayed once and cached, since a full
game (~40-80 plies) parses fast enough that the simplicity is worth more than the saved
microseconds (MVP-scope discipline: this is not a hot path).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import chess

from app.core.config import PatternSettings
from app.db.models import GameColor, GameMove, MoveEvaluation


@dataclass(frozen=True)
class PlyContext:
    """One played ply, with its engine evaluation if one was computed."""

    move: GameMove
    evaluation: MoveEvaluation | None

    @property
    def ply(self) -> int:
        return self.move.ply

    @property
    def side(self) -> GameColor:
        """Ply 0 is White's first move (`GameMove`'s own convention)."""
        return GameColor.WHITE if self.ply % 2 == 0 else GameColor.BLACK

    @property
    def board_before(self) -> chess.Board:
        return chess.Board(self.move.fen_before)

    @property
    def board_after(self) -> chess.Board:
        return chess.Board(self.move.fen_after)


@dataclass(frozen=True)
class ThemeDetection:
    """What a detector found. `ply` is the span's *start* — per data-model.md, "ply
    range start for strategy tags" — with the span's end and supporting detail in
    `evidence`, since what a span looks like genuinely differs by theme."""

    ply: int
    confidence: float
    evidence: dict[str, object]


class ThemeDetector(Protocol):
    """Signature every theme detector module's `detect` function must match."""

    def __call__(
        self,
        plies: Sequence[PlyContext],
        side: GameColor,
        settings: PatternSettings,
    ) -> ThemeDetection | None: ...


__all__ = ["PlyContext", "ThemeDetection", "ThemeDetector"]
