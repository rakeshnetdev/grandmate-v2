"""Read-side lookups for opening matches and tactical/strategic findings (Phase 6).

Kept separate from `PatternDetectionService`, which only detects and persists — same
split as `domain/analysis/queries.py` vs `domain/analysis/service.py`, for the same
reason: a different responsibility with a different lifecycle (called from request
handlers, not from ingestion or the background dispatcher).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game, GameAnalysis, MotifFinding, OpeningMatch, StrategicThemeFinding


@dataclass(frozen=True)
class PatternFindings:
    """Every tactical/strategic finding from a game's most recent analysis run."""

    motifs: list[MotifFinding]
    themes: list[StrategicThemeFinding]


async def get_opening_match(
    session: AsyncSession, game_id: uuid.UUID, profile_id: uuid.UUID
) -> OpeningMatch | None:
    """The opening identified for a game the profile owns. `None` is a normal outcome —
    most positions in most games fall outside any named opening line."""
    result = await session.execute(
        select(OpeningMatch)
        .join(Game, Game.id == OpeningMatch.game_id)
        .where(OpeningMatch.game_id == game_id, Game.profile_id == profile_id)
    )
    return result.scalar_one_or_none()


async def get_pattern_findings(
    session: AsyncSession, game_id: uuid.UUID, profile_id: uuid.UUID
) -> PatternFindings:
    """Motif and theme findings from the most recent `GameAnalysis` run for a game the
    profile owns. Empty lists (not `None`) when no analysis exists yet or nothing was
    detected — both are normal outcomes, not errors."""
    latest_analysis_id = await session.execute(
        select(GameAnalysis.id)
        .join(Game, Game.id == GameAnalysis.game_id)
        .where(GameAnalysis.game_id == game_id, Game.profile_id == profile_id)
        .order_by(GameAnalysis.created_at.desc())
        .limit(1)
    )
    analysis_id = latest_analysis_id.scalar_one_or_none()
    if analysis_id is None:
        return PatternFindings(motifs=[], themes=[])

    motifs = await session.execute(
        select(MotifFinding)
        .where(MotifFinding.game_analysis_id == analysis_id)
        .order_by(MotifFinding.ply)
    )
    themes = await session.execute(
        select(StrategicThemeFinding)
        .where(StrategicThemeFinding.game_analysis_id == analysis_id)
        .order_by(StrategicThemeFinding.ply)
    )
    return PatternFindings(motifs=list(motifs.scalars().all()), themes=list(themes.scalars().all()))


__all__ = ["PatternFindings", "get_opening_match", "get_pattern_findings"]
