"""Opening identification and tactical/strategic finding response schemas (Phase 6)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class OpeningMatchSummary(BaseModel):
    eco: str
    opening_name: str
    epd: str
    matched_ply: int


class MotifFindingSummary(BaseModel):
    ply: int
    side: str
    motif: str
    confidence: float
    evidence: dict[str, Any]


class StrategicThemeFindingSummary(BaseModel):
    ply: int
    side: str
    theme: str
    confidence: float
    evidence: dict[str, Any]


class GamePatternsSummary(BaseModel):
    """Everything Phase 6 has to say about one game. `opening` is `None` and the finding
    lists are empty as normal outcomes, not error states — most positions fall outside
    any named opening line, and most games have no notable tactical/strategic findings."""

    game_id: uuid.UUID
    opening: OpeningMatchSummary | None
    motifs: list[MotifFindingSummary]
    themes: list[StrategicThemeFindingSummary]


__all__ = [
    "GamePatternsSummary",
    "MotifFindingSummary",
    "OpeningMatchSummary",
    "StrategicThemeFindingSummary",
]
