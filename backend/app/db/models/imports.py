"""Generic job tracking (Phase 3).

Deliberately generic — `kind` discriminates rather than one table per long-running
operation — because Phase 4 (canonicalization, folded into the import request itself),
Phase 5 (engine analysis), and Phase 9 (Lichess/Chess.com account imports) all need the
same shape: a unit of work with visible, pollable status. One table now avoids several
near-identical ones later. See `final_docs/v2/data-model.md`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum

if TYPE_CHECKING:
    from app.db.models.games import Game


class JobKind(enum.StrEnum):
    """What a job does. Extended as later phases add their own long-running work."""

    PGN_IMPORT = "pgn_import"


class JobStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A unit of ingestion work with visible, pollable status."""

    __tablename__ = "jobs"

    kind: Mapped[JobKind] = mapped_column(pg_enum(JobKind, "job_kind"), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), nullable=False, default=JobStatus.PENDING
    )
    # {"total": N, "imported": N, "duplicates": N, "rejected": [{"index", "reason", "detail"}]}
    progress: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    # Reserved for a future caller-supplied idempotency guard (e.g. re-triggering the same
    # Lichess sync). Unused by Phase 3; column exists so Phase 9 is additive, not a migration.
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    # Job-level failure only (e.g. "too many games in one submission"). Per-game rejections
    # that don't fail the whole job live in `progress`, not here.
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    games: Mapped[list[Game]] = relationship(back_populates="job")


__all__ = ["Job", "JobKind", "JobStatus"]
