"""Profile-level aggregation orchestration (Phase 8).

Computed on demand rather than via a background job: aggregation only reads
already-computed per-game data (`GameAnalysis`, `OpeningMatch`, motif/theme findings), so
it is cheap enough to recompute at request time rather than needing its own
dispatch/polling lifecycle the way engine analysis does. Every call still persists its
result as a new versioned `ProfileAggregateSnapshot` row (never updates one in place) —
that history is what lets "progress deltas" mean something and keeps old snapshots
honestly reproducible (rule 7 of the phase gate) even as metric logic evolves under a new
`SNAPSHOT_VERSION`.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import AnalyticsSettings
from app.db.models import (
    Game,
    GameAnalysis,
    MotifFinding,
    OpeningMatch,
    ProfileAggregateSnapshot,
    StrategicThemeFinding,
)
from app.domain.analytics import metrics

# Bumped when the *meaning* of a metric changes (a new field, a changed formula) — not on
# every code change. Old snapshots keep the version they were computed under, so a report
# reading snapshot history can tell "the numbers changed because the game history changed"
# from "the numbers changed because we changed how we compute them".
SNAPSHOT_VERSION = "agg-v1"


def _numeric_delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round(current - previous, 3)


def _rate_delta(
    current: dict[str, float], previous: dict[str, float] | None
) -> dict[str, float] | None:
    if not previous:
        return None
    keys = set(current) | set(previous)
    return {key: round(current.get(key, 0.0) - previous.get(key, 0.0), 3) for key in keys}


class ProfileAnalyticsService:
    """Computes and persists one profile's aggregate snapshot for a given window size."""

    def __init__(self, session: AsyncSession, settings: AnalyticsSettings) -> None:
        self._session = session
        self._settings = settings

    async def compute_snapshot(
        self, profile_id: uuid.UUID, window_size: int
    ) -> ProfileAggregateSnapshot:
        """The current `window_size` analyzed games vs. the `window_size` before them.

        "Analyzed" means canonicalized *and* engine-analyzed — a game still mid-import,
        pending its background analysis job, or that failed canonicalization contributes
        to neither window; it simply isn't visible to aggregation yet, same as it isn't
        visible to `/analysis` or `/patterns` (see the Phase 8a report).
        """
        games = await self._load_analyzed_games(profile_id)
        current = games[:window_size]
        previous = games[window_size : window_size * 2]

        current_accuracy = metrics.average_accuracy(current)
        current_rates = metrics.classification_rates(current)
        current_critical = metrics.average_critical_moments(current)
        previous_accuracy = metrics.average_accuracy(previous)
        previous_rates = metrics.classification_rates(previous)
        previous_critical = metrics.average_critical_moments(previous)

        games_included = len(current)
        sufficient_sample = games_included >= self._settings.analytics_min_games_for_trend

        metrics_payload: dict[str, Any] = {
            "accuracy": {
                "current": current_accuracy,
                "previous": previous_accuracy,
                "delta": _numeric_delta(current_accuracy, previous_accuracy),
            },
            "classification_rates": {
                "current": current_rates,
                "previous": previous_rates,
                "delta": _rate_delta(current_rates, previous_rates),
            },
            "critical_moment_rate": {
                "current": current_critical,
                "previous": previous_critical,
                "delta": _numeric_delta(current_critical, previous_critical),
            },
            "opening_family_performance": [
                asdict(s) for s in metrics.opening_family_performance(current)
            ],
            "color_segmentation": [asdict(s) for s in metrics.color_segmentation(current)],
            "time_control_segmentation": [
                asdict(s) for s in metrics.time_control_segmentation(current, self._settings)
            ],
            "recurring_weaknesses": [
                asdict(s) for s in metrics.recurring_weaknesses(current, self._settings)
            ],
        }

        snapshot = ProfileAggregateSnapshot(
            profile_id=profile_id,
            window_size=window_size,
            games_included=games_included,
            sufficient_sample=sufficient_sample,
            snapshot_version=SNAPSHOT_VERSION,
            metrics=metrics_payload,
        )
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def _load_analyzed_games(self, profile_id: uuid.UUID) -> list[metrics.GameForAnalytics]:
        game_rows = await self._session.execute(
            select(Game)
            .where(Game.profile_id == profile_id, Game.canonicalized_at.is_not(None))
            .order_by(func.coalesce(Game.played_at, Game.created_at).desc())
        )
        games_by_recency = list(game_rows.scalars().all())
        if not games_by_recency:
            return []

        # Latest GameAnalysis per game (a retry, see analysis.py's route, adds a new
        # version rather than replacing one) — DISTINCT ON is the postgres-native way to
        # pick one row per game_id without a window-function subquery.
        analysis_rows = await self._session.execute(
            select(GameAnalysis)
            .where(GameAnalysis.game_id.in_([g.id for g in games_by_recency]))
            .distinct(GameAnalysis.game_id)
            .order_by(GameAnalysis.game_id, GameAnalysis.created_at.desc())
            .options(selectinload(GameAnalysis.evaluations))
        )
        analysis_by_game = {a.game_id: a for a in analysis_rows.scalars().all()}
        if not analysis_by_game:
            return []

        opening_rows = await self._session.execute(
            select(OpeningMatch).where(OpeningMatch.game_id.in_(analysis_by_game.keys()))
        )
        opening_by_game = {o.game_id: o for o in opening_rows.scalars().all()}

        analysis_ids = [a.id for a in analysis_by_game.values()]
        motif_rows = await self._session.execute(
            select(MotifFinding).where(MotifFinding.game_analysis_id.in_(analysis_ids))
        )
        motifs_by_analysis: dict[uuid.UUID, list[MotifFinding]] = {}
        for motif in motif_rows.scalars().all():
            motifs_by_analysis.setdefault(motif.game_analysis_id, []).append(motif)

        theme_rows = await self._session.execute(
            select(StrategicThemeFinding).where(
                StrategicThemeFinding.game_analysis_id.in_(analysis_ids)
            )
        )
        themes_by_analysis: dict[uuid.UUID, list[StrategicThemeFinding]] = {}
        for theme in theme_rows.scalars().all():
            themes_by_analysis.setdefault(theme.game_analysis_id, []).append(theme)

        result: list[metrics.GameForAnalytics] = []
        for game in games_by_recency:
            analysis = analysis_by_game.get(game.id)
            if analysis is None:
                continue
            result.append(
                metrics.GameForAnalytics(
                    game=game,
                    analysis=analysis,
                    opening=opening_by_game.get(game.id),
                    motifs=motifs_by_analysis.get(analysis.id, []),
                    themes=themes_by_analysis.get(analysis.id, []),
                )
            )
        return result


__all__ = ["SNAPSHOT_VERSION", "ProfileAnalyticsService"]
