"""Read-side lookups for imported games.

Kept separate from `GameParsingService`, which only canonicalizes — same split as
`domain/analysis/queries.py` vs `domain/analysis/service.py`, for the same reason: a
different responsibility with a different lifecycle (called from request handlers, not
from ingestion).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game


async def list_games(session: AsyncSession, profile_id: uuid.UUID) -> list[Game]:
    """Every game the profile has imported, most recent first."""
    result = await session.execute(
        select(Game).where(Game.profile_id == profile_id).order_by(Game.created_at.desc())
    )
    return list(result.scalars().all())


async def get_game(session: AsyncSession, game_id: uuid.UUID, profile_id: uuid.UUID) -> Game | None:
    """A single game, scoped to `profile_id` so one profile can never look up another's
    game by guessing an id."""
    game = await session.get(Game, game_id)
    if game is None or game.profile_id != profile_id:
        return None
    return game


__all__ = ["get_game", "list_games"]
