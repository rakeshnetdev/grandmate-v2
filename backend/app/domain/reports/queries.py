"""Read-side lookups for persona reports (Phase 9) and training plans (Phase 15)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameReport, Persona, TrainingRecommendation


async def get_latest_report(
    session: AsyncSession, game_id: uuid.UUID, persona: Persona, *, report_type: str = "findings"
) -> GameReport | None:
    """The most recent report for this game, persona, and report type — versioned, same
    convention as `domain.analysis.queries.get_latest_analysis`. `report_type` (Phase
    16b) distinguishes the default findings-list report from the full game-story
    narrative; the two coexist per (game_id, persona) without colliding."""
    result = await session.execute(
        select(GameReport)
        .where(
            GameReport.game_id == game_id,
            GameReport.persona == persona,
            GameReport.report_type == report_type,
        )
        .order_by(GameReport.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_recently_recommended_themes(session: AsyncSession, profile_id: uuid.UUID) -> set[str]:
    """Weakness names surfaced in the profile's own most recent prior training plan —
    across any persona or window size, per `training_facts.py`'s docstring: the point is
    "did this profile just see this weakness recommended," not a per-persona history.
    Empty for a profile with no prior plan, which is not an error — everything ranks
    as fresh."""
    result = await session.execute(
        select(TrainingRecommendation.themes_covered)
        .where(TrainingRecommendation.profile_id == profile_id)
        .order_by(TrainingRecommendation.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return set(row) if row else set()


__all__ = ["get_latest_report", "get_recently_recommended_themes"]
