"""Persona report generation: facts, selection, prompting, grounding, and the
deterministic fallback (Phase 9, D-023, `persona-matrix.md`, ADR-0006)."""

from app.domain.reports.facts import Fact, extract_facts
from app.domain.reports.queries import get_latest_report
from app.domain.reports.service import ReportService

__all__ = ["Fact", "ReportService", "extract_facts", "get_latest_report"]
