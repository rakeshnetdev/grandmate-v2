"""Persona report response schemas (Phase 9)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportFinding(BaseModel):
    fact_ids: list[str]
    text: str


class GameReportSummary(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    persona: str
    source: str
    model: str | None
    analysis_version: str
    summary: str
    findings: list[ReportFinding]
    recommendations: list[str]
    grounded: bool
    created_at: datetime


__all__ = ["GameReportSummary", "ReportFinding"]
