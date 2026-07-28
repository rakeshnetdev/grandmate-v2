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


__all__ = ["JobProgress", "JobSummary", "RejectedGameSummary"]
