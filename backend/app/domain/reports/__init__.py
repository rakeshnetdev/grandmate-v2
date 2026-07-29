"""Persona report generation: facts, selection, prompting, grounding, and the
deterministic fallback (Phase 9, D-023, `persona-matrix.md`, ADR-0006).

Also training-plan generation (Phase 15, D-032), the same pattern applied to a
profile's recurring weaknesses instead of one game's moves."""

from app.domain.reports.facts import Fact, extract_facts
from app.domain.reports.queries import get_latest_report, get_recently_recommended_themes
from app.domain.reports.service import ReportService
from app.domain.reports.training_service import TrainingService

__all__ = [
    "Fact",
    "ReportService",
    "TrainingService",
    "extract_facts",
    "get_latest_report",
    "get_recently_recommended_themes",
]
