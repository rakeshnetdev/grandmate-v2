"""Profile-level multi-game aggregation (Phase 8).

Thin per the "routes delegate" rule: computation lives in
`domain/analytics/service.py`. Unlike `/imports` and `/analysis`, there is no job/polling
shape here — aggregation is cheap enough (it only reads already-computed per-game data)
to run and return within the request, same reasoning as Phase 3's original inline
ingestion. See that module's docstring for the full reasoning.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.profile_scope import ScopedProfileIdDep
from app.api.dependencies.settings import SettingsDep
from app.db.models import ProfileAggregateSnapshot
from app.domain.analytics import ProfileAnalyticsService
from app.schemas.analytics import ProfileAnalyticsSummary

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _to_summary(row: ProfileAggregateSnapshot) -> ProfileAnalyticsSummary:
    return ProfileAnalyticsSummary.model_validate(
        {
            "profile_id": row.profile_id,
            "window_size": row.window_size,
            "games_included": row.games_included,
            "sufficient_sample": row.sufficient_sample,
            "snapshot_version": row.snapshot_version,
            "computed_at": row.created_at,
            **row.metrics,
        }
    )


@router.get("/profile", response_model=ProfileAnalyticsSummary)
async def get_profile_analytics(
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    window: int | None = None,
) -> ProfileAnalyticsSummary:
    """Recomputed on every call — see the module docstring for why that's cheap enough
    to do rather than caching. Still persists each computation as a new versioned
    `ProfileAggregateSnapshot` row, which is what makes reproducibility and future
    snapshot-history comparisons possible."""
    window_size = window if window is not None else settings.analytics.analytics_default_window
    allowed_windows = settings.analytics.window_sizes_list
    if window_size not in allowed_windows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"window must be one of {allowed_windows}",
        )

    service = ProfileAnalyticsService(session, settings.analytics)
    snapshot = await service.compute_snapshot(profile_id, window_size)
    return _to_summary(snapshot)


__all__ = ["router"]
