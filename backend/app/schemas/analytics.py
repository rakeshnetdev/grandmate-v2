"""Profile analytics response schemas (Phase 8)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class MetricTrend(BaseModel):
    """A single numeric metric for the current window, the window before it (`None` if
    there weren't enough prior games), and their difference."""

    current: float | None
    previous: float | None
    delta: float | None


class ClassificationRateTrend(BaseModel):
    current: dict[str, float]
    previous: dict[str, float]
    delta: dict[str, float] | None


class OpeningFamilyPerformance(BaseModel):
    family: str
    games: int
    wins: int
    draws: int
    losses: int
    win_rate: float | None
    average_accuracy: float | None


class ColorSegment(BaseModel):
    color: str
    games: int
    average_accuracy: float | None
    classification_rates: dict[str, float]
    win_rate: float | None


class TimeControlSegment(BaseModel):
    bucket: str
    games: int
    average_accuracy: float | None
    win_rate: float | None


class RecurringWeakness(BaseModel):
    kind: str
    name: str
    games_with_finding: int
    occurrence_rate: float


class ProfileAnalyticsSummary(BaseModel):
    """One computed, persisted aggregate snapshot for a profile's window."""

    profile_id: uuid.UUID
    window_size: int
    games_included: int
    # Below AnalyticsSettings.analytics_min_games_for_trend — the metrics below are still
    # populated, but a caller should caveat rather than assert them.
    sufficient_sample: bool
    snapshot_version: str
    computed_at: datetime

    accuracy: MetricTrend
    classification_rates: ClassificationRateTrend
    critical_moment_rate: MetricTrend
    opening_family_performance: list[OpeningFamilyPerformance]
    color_segmentation: list[ColorSegment]
    time_control_segmentation: list[TimeControlSegment]
    recurring_weaknesses: list[RecurringWeakness]


__all__ = [
    "ClassificationRateTrend",
    "ColorSegment",
    "MetricTrend",
    "OpeningFamilyPerformance",
    "ProfileAnalyticsSummary",
    "RecurringWeakness",
    "TimeControlSegment",
]
