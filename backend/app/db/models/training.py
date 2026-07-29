"""Persona-rendered training-plan recommendations (Phase 15, D-032).

Profile-scoped, not game-scoped — `GameReport` joins ownership through `game_id`
because a report has no identity independent of the game it explains; a training plan
explains a *profile's* recurring pattern across many games, so it carries `profile_id`
directly, the same way `ProfileAggregateSnapshot` does.

Versioned the same way every other generated artifact in this project is: a new
recommendation inserts a new row rather than overwriting the last one, both for
reproducibility and because history is the entire mechanism D-032 uses to avoid
repeating the same suggestion (see `themes_covered` below).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.db.models.identity import Persona
from app.db.models.reports import ReportSource


class TrainingRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One persona-rendered training plan for one profile, one version."""

    __tablename__ = "training_recommendations"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    persona: Mapped[Persona] = mapped_column(pg_enum(Persona, "persona"), nullable=False)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # Which ProfileAggregateSnapshot.snapshot_version this plan was built from — the
    # analytics-side analogue of GameReport.analysis_version.
    snapshot_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[ReportSource] = mapped_column(
        pg_enum(ReportSource, "report_source"), nullable=False
    )
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # {"summary": str, "findings": [{"fact_ids": [...], "text": str}, ...],
    #  "recommendations": [str, ...]} — identical shape to GameReport.content.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fact_ids_used: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Recurring-weakness names this plan actually surfaced (a subset of what was
    # candidate — persona caps may exclude some). The next generation for this profile
    # reads this column across recent rows to deprioritise (never hard-exclude, D-032)
    # a weakness it already recommended.
    themes_covered: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


__all__ = ["TrainingRecommendation"]
