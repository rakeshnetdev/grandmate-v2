"""Long-term memory audit schemas (Phase 11)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class MemoryOut(BaseModel):
    id: uuid.UUID
    kind: str
    content: str
    confidence: float
    source_thread_id: uuid.UUID | None
    created_at: datetime
    # `None` means active. A caller does not need a separate `is_active` flag — the
    # audit UI's own job is showing *when* something stopped being active, not hiding
    # that fact behind a boolean.
    superseded_at: datetime | None


__all__ = ["MemoryOut"]
