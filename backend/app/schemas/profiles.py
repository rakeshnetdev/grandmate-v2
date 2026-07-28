"""Profile listing response schema (Phase 8b)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class ProfileSummary(BaseModel):
    id: uuid.UUID
    kind: str
    display_name: str


__all__ = ["ProfileSummary"]
