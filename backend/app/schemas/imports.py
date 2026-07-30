"""Import request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RejectedGameSummary(BaseModel):
    """One game that did not make it in, and why."""

    source: str
    index: int
    reason: str
    detail: str


class JobProgress(BaseModel):
    total: int = 0
    imported: int = 0
    duplicates: int = 0
    rejected: list[RejectedGameSummary] = []


class JobSummary(BaseModel):
    """An import job's visible status. Returned by create, get, and list."""

    id: uuid.UUID
    kind: str
    status: str
    progress: JobProgress
    error: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None


class PlatformSyncRequest(BaseModel):
    """Sync request body (Phase 14). `window` is optional — the route falls back to
    `AnalyticsSettings.analytics_default_window`, the same "how many recent games"
    default the profile-analytics window picker already uses (D-030/D-031: no new
    window-size concept is introduced for imports)."""

    window: int | None = None
    # Phase 16b follow-up: whose games to fetch. Omitted means the caller's own linked
    # account for this provider (Phase 14's only behaviour). Supplied means an arbitrary
    # player being studied — the games land in the caller's study profile on their own,
    # because `ImportService._target_profile_id` already routes per game on "do these
    # headers match a linked username of mine" (D-021, ADR-0016). No target-profile
    # field is needed here, and adding one would duplicate that routing decision.
    username: str | None = None


__all__ = ["JobProgress", "JobSummary", "PlatformSyncRequest", "RejectedGameSummary"]
