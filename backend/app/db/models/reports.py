"""Persona-rendered game reports (Phase 9, D-023, `persona-matrix.md`).

Versioned the same way `GameAnalysis` and `ProfileAggregateSnapshot` are: a regenerated
report inserts a new row rather than overwriting the last one, so an old report's exact
wording stays reproducible even after prompts or the underlying analysis change.
`analysis_version` records which `GameAnalysis` run a report was built from — the same
reproducibility purpose `GameAnalysis.analysis_version` itself serves, one level up.

No `profile_id` column: ownership is resolved by joining through `game_id` to `Game`, the
same pattern `GameAnalysis` already uses — a report has no identity independent of the
game it explains, so it does not need a second, redundant path to the owning profile.
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.db.models.identity import Persona


class ReportSource(enum.StrEnum):
    """Where a report's text came from.

    `FALLBACK` is not a failure state to apologise for — persona-matrix.md's invariant
    ("a persona changes how a finding is said, never whether it is true") holds exactly
    as well for a deterministic fact listing as for LLM prose. It is the safe default
    whenever the LLM path can't be trusted (budget exhausted, or the critic rejected an
    ungrounded claim after one retry) rather than an error surfaced to the reader.
    """

    LLM = "llm"
    FALLBACK = "fallback"


class GameReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One persona-rendered report for one game, one version."""

    __tablename__ = "game_reports"

    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    persona: Mapped[Persona] = mapped_column(pg_enum(Persona, "persona"), nullable=False)
    # "findings" (Phase 9, the default) or "story" (Phase 16b — the full opening/
    # middlegame/endgame narrative). Two report *shapes* can coexist for the same
    # (game_id, persona) pair, so this is part of the lookup key, not just metadata —
    # see get_latest_report.
    report_type: Mapped[str] = mapped_column(String(20), nullable=False, default="findings")
    source: Mapped[ReportSource] = mapped_column(
        pg_enum(ReportSource, "report_source"), nullable=False
    )
    # Which model produced this report; `None` for a FALLBACK report, since no model ran.
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Which GameAnalysis run this was built from — see the module docstring.
    analysis_version: Mapped[str] = mapped_column(String(64), nullable=False)
    # {"summary": str, "findings": [{"fact_ids": [...], "text": str}, ...],
    #  "recommendations": [str, ...]}
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Every fact id referenced anywhere in `content`, flattened — lets the persona
    # fidelity evaluation (and the critic) check grounding without re-parsing `content`'s
    # structure.
    fact_ids_used: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Whether this report passed the grounding critic. Always True for a FALLBACK report
    # (it is built directly from facts, nothing to ground) and for an LLM report that
    # passed on the first or retried attempt; a report is only ever persisted after
    # grounding succeeds or the fallback path was used instead — this column exists so
    # that fact stays visible on the row itself, not only inferable from `source`.
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


__all__ = ["GameReport", "ReportSource"]
