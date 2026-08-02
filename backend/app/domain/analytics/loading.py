"""Loads a profile's analyzed games with everything the metric functions read (Phase 8;
extracted from `service.py` in Phase 19).

Lifted out of `ProfileAnalyticsService` when pattern feedback (Phase 19) needed the exact
same bundle for a different question — "the N games before *this* one" rather than "the
most recent N". Two loaders would have been two chances for the definitions to drift: what
counts as "analyzed", which `GameAnalysis` run wins when a game has been retried, and how
games are ordered by recency all have to mean the same thing in both places, or a game
could sit in the dashboard's window while being invisible to its own feedback baseline.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Game,
    GameAnalysis,
    MotifFinding,
    OpeningMatch,
    StrategicThemeFinding,
)
from app.domain.analytics.metrics import GameForAnalytics


async def load_analyzed_games(
    session: AsyncSession, profile_id: uuid.UUID
) -> list[GameForAnalytics]:
    """Every canonicalized, engine-analyzed game the profile owns, most recent first.

    "Analyzed" means canonicalized *and* engine-analyzed — a game still mid-import,
    pending its background analysis job, or that failed canonicalization contributes to
    nothing here; it simply isn't visible to aggregation yet, same as it isn't visible to
    `/analysis` or `/patterns` (see the Phase 8a report).
    """
    game_rows = await session.execute(
        select(Game)
        .where(Game.profile_id == profile_id, Game.canonicalized_at.is_not(None))
        .order_by(func.coalesce(Game.played_at, Game.created_at).desc())
    )
    games_by_recency = list(game_rows.scalars().all())
    if not games_by_recency:
        return []

    # Latest GameAnalysis per game (a retry, see analysis.py's route, adds a new version
    # rather than replacing one) — DISTINCT ON is the postgres-native way to pick one row
    # per game_id without a window-function subquery.
    analysis_rows = await session.execute(
        select(GameAnalysis)
        .where(GameAnalysis.game_id.in_([g.id for g in games_by_recency]))
        .distinct(GameAnalysis.game_id)
        .order_by(GameAnalysis.game_id, GameAnalysis.created_at.desc())
        .options(selectinload(GameAnalysis.evaluations))
    )
    analysis_by_game = {a.game_id: a for a in analysis_rows.scalars().all()}
    if not analysis_by_game:
        return []

    opening_rows = await session.execute(
        select(OpeningMatch).where(OpeningMatch.game_id.in_(analysis_by_game.keys()))
    )
    opening_by_game = {o.game_id: o for o in opening_rows.scalars().all()}

    analysis_ids = [a.id for a in analysis_by_game.values()]
    motif_rows = await session.execute(
        select(MotifFinding).where(MotifFinding.game_analysis_id.in_(analysis_ids))
    )
    motifs_by_analysis: dict[uuid.UUID, list[MotifFinding]] = {}
    for motif in motif_rows.scalars().all():
        motifs_by_analysis.setdefault(motif.game_analysis_id, []).append(motif)

    theme_rows = await session.execute(
        select(StrategicThemeFinding).where(
            StrategicThemeFinding.game_analysis_id.in_(analysis_ids)
        )
    )
    themes_by_analysis: dict[uuid.UUID, list[StrategicThemeFinding]] = {}
    for theme in theme_rows.scalars().all():
        themes_by_analysis.setdefault(theme.game_analysis_id, []).append(theme)

    result: list[GameForAnalytics] = []
    for game in games_by_recency:
        analysis = analysis_by_game.get(game.id)
        if analysis is None:
            continue
        result.append(
            GameForAnalytics(
                game=game,
                analysis=analysis,
                opening=opening_by_game.get(game.id),
                motifs=motifs_by_analysis.get(analysis.id, []),
                themes=themes_by_analysis.get(analysis.id, []),
            )
        )
    return result


__all__ = ["load_analyzed_games"]
