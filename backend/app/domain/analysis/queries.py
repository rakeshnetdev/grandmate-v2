"""Read-side lookups and manual retry for engine analysis (Phase 5).

Kept separate from `AnalysisService`, which only runs analysis — these exist for the API
layer to poll status and fetch results, a different responsibility with a different
lifecycle (called from request handlers, not from the background dispatcher).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Game, GameAnalysis, GameMove, Job, JobKind, JobStatus


async def get_analysis_job(
    session: AsyncSession, job_id: uuid.UUID, profile_id: uuid.UUID
) -> Job | None:
    """Scoped to `profile_id` so one profile can never poll another's job."""
    result = await session.execute(
        select(Job).where(
            Job.id == job_id, Job.profile_id == profile_id, Job.kind == JobKind.ENGINE_ANALYSIS
        )
    )
    return result.scalar_one_or_none()


async def get_latest_analysis(
    session: AsyncSession, game_id: uuid.UUID, profile_id: uuid.UUID
) -> GameAnalysis | None:
    """The most recent analysis run for a game the profile owns, moves eager-loaded so
    the route does not trigger N+1 lazy loads while serialising the response."""
    result = await session.execute(
        select(GameAnalysis)
        .join(Game, Game.id == GameAnalysis.game_id)
        .where(GameAnalysis.game_id == game_id, Game.profile_id == profile_id)
        .options(selectinload(GameAnalysis.evaluations))
        .order_by(GameAnalysis.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_retry_job(
    session: AsyncSession, game_id: uuid.UUID, profile_id: uuid.UUID
) -> Job | None:
    """Queue a fresh analysis job for a game the profile owns.

    Returns `None` if the game does not exist or is not the caller's — the route maps
    that to a 404, same as any other cross-profile-invisible resource. A previous
    analysis run, if any, is left in place: `GameAnalysis` is versioned (see its own
    docstring), so a retry adds a new run rather than overwriting the last one.
    `get_latest_analysis` always returns the most recent.
    """
    game = await session.get(Game, game_id)
    if game is None or game.profile_id != profile_id:
        return None

    job = Job(
        kind=JobKind.ENGINE_ANALYSIS,
        profile_id=profile_id,
        game_id=game_id,
        status=JobStatus.PENDING,
    )
    session.add(job)
    await session.flush()
    return job


async def get_moves(
    session: AsyncSession, game_id: uuid.UUID, profile_id: uuid.UUID
) -> list[GameMove]:
    """A game's canonical moves, ply-ordered — scoped the same way as
    `get_latest_analysis` (Phase 10's `get_game_analysis` tool pairs the two to attach
    SAN move text to each ply's evaluation)."""
    result = await session.execute(
        select(GameMove)
        .join(Game, Game.id == GameMove.game_id)
        .where(GameMove.game_id == game_id, Game.profile_id == profile_id)
        .order_by(GameMove.ply)
    )
    return list(result.scalars().all())


__all__ = ["create_retry_job", "get_analysis_job", "get_latest_analysis", "get_moves"]
