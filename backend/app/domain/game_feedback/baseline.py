"""Assembles one game and the recent history it is judged against (Phase 19, D-037).

The baseline is defined positionally rather than by timestamp arithmetic: the profile's
analyzed games already come back from `load_analyzed_games` ordered most-recent-first by
the same `played_at`-then-`created_at` key the rest of the product sorts on, so "the games
before this one" is simply the slice after the target's own position in that list. Doing
it any other way would mean re-deriving a recency comparison that already exists, and
re-deriving it slightly differently is how a game ends up in the dashboard's window but
missing from its own feedback baseline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analytics.loading import load_analyzed_games
from app.domain.analytics.metrics import GameForAnalytics


@dataclass(frozen=True)
class Baseline:
    """A game plus the analyzed games immediately preceding it, most recent first."""

    target: GameForAnalytics
    prior: list[GameForAnalytics]


async def load_baseline(
    session: AsyncSession,
    profile_id: uuid.UUID,
    game_id: uuid.UUID,
    window: int,
) -> Baseline | None:
    """The target game and up to `window` analyzed games played before it.

    `None` when the target game itself is not analyzed yet — the caller turns that into
    the same "no analysis for this game" response every other per-game route gives, since
    from the reader's point of view it is the identical situation.

    A profile's very first game legitimately returns an empty `prior`; that is a real
    state with a real answer ("nothing to compare against yet"), not an error.
    """
    games = await load_analyzed_games(session, profile_id)
    position = next((i for i, g in enumerate(games) if g.game.id == game_id), None)
    if position is None:
        return None
    return Baseline(target=games[position], prior=games[position + 1 : position + 1 + window])


__all__ = ["Baseline", "load_baseline"]
