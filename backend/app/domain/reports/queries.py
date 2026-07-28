"""Read-side lookups for persona reports (Phase 9)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameReport, Persona


async def get_latest_report(
    session: AsyncSession, game_id: uuid.UUID, persona: Persona
) -> GameReport | None:
    """The most recent report for this game and persona — versioned, same convention as
    `domain.analysis.queries.get_latest_analysis`."""
    result = await session.execute(
        select(GameReport)
        .where(GameReport.game_id == game_id, GameReport.persona == persona)
        .order_by(GameReport.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


__all__ = ["get_latest_report"]
