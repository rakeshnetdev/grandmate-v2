"""Profile-level aggregate snapshots (Phase 8).

`ProfileAggregateSnapshot` is versioned the same way `GameAnalysis` is: every computation
inserts a new row rather than updating one in place. That is what makes "progress deltas"
meaningful — a later snapshot for the same `(profile_id, window_size)` can be compared
against an earlier one, and reproducibility (rule 7 of the phase gate) means an old
snapshot's numbers never silently change under it.

`metrics` is a JSONB bag rather than one column per statistic, same reasoning as
`GameAnalysis.summary`: what counts as a metric is a product policy that will keep
growing (Phase 8 already defines several), and a wide, mostly-nullable column set would
churn on every addition. `games_included` and `sufficient_sample` are pulled out as real
columns because they gate query/filter behaviour (e.g. "only show me confident
snapshots"), not just display.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProfileAggregateSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One computed aggregation over a profile's most recent `window_size` analyzed
    games, at a point in time. `created_at` (from `TimestampMixin`) is the computation
    timestamp — there is no separate "completed_at" the way `GameAnalysis` has one,
    since aggregation is a single in-request computation, not a job with its own
    lifecycle.
    """

    __tablename__ = "profile_aggregate_snapshots"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    window_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # How many games actually went into this snapshot — may be less than window_size for
    # a profile that hasn't imported/analyzed that many games yet.
    games_included: Mapped[int] = mapped_column(Integer, nullable=False)
    # Below ANALYTICS_MIN_GAMES_FOR_TREND (see AnalyticsSettings): trends and recurring
    # weaknesses are computed but the UI must caveat them rather than assert them.
    sufficient_sample: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # A free-text tag for the metric-computation logic version, same convention as
    # GameAnalysis.analysis_version — lets a later phase change what a metric means
    # without a schema migration, and lets old snapshots stay honestly labeled with the
    # logic that produced them.
    snapshot_version: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = ["ProfileAggregateSnapshot"]
