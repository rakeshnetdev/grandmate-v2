"""Game list/detail response schemas.

Moved out of `schemas/imports.py`: `GameSummary` describes a `Game` row, a distinct
resource from an import `Job` — same reasoning as splitting `/analysis` from
`/patterns` (see `api/routes/patterns.py`), even though both started out defined next to
the import job schema for lack of a dedicated route to serve them.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class GameSummary(BaseModel):
    """One imported game. `canonicalized_at` being `None` means Phase 4 replay hasn't
    succeeded (or hasn't run) for this game — the analysis and patterns endpoints won't
    have anything to show yet, since no analysis job is queued without canonicalization."""

    id: uuid.UUID
    source: str
    headers: dict[str, str]
    played_at: datetime | None
    canonicalized_at: datetime | None
    created_at: datetime


__all__ = ["GameSummary"]
