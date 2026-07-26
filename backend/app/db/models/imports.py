"""Ingestion job tracking and game persistence (Phase 3, ADR-0015 storage).

`Job` is deliberately generic — `kind` discriminates rather than one table per ingestion
route — because Phase 5 (engine analysis) and Phase 9 (Lichess/Chess.com account imports)
need the same shape: a long-running unit of work with visible status. One table now
avoids three near-identical ones later. See `final_docs/v2/data-model.md`.

`Game` mirrors the documented `games` table. `focus_color` and `opponent_name` are
nullable and unpopulated by Phase 3: determining which side a profile played requires the
header-normalisation policy that Phase 4 owns, not raw ingestion. The columns are laid
down now so Phase 4 does not need a schema-reshaping migration, the same precedent as
`ProfileRelationship` in Phase 2.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.db.models.identity import GameSource


class JobKind(enum.StrEnum):
    """What a job does. Extended as later phases add their own long-running work."""

    PGN_IMPORT = "pgn_import"


class JobStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class GameColor(enum.StrEnum):
    WHITE = "white"
    BLACK = "black"


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


class Game(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A successfully ingested, deduplicated game.

    Only games that pass validation and are not duplicates get a row here — rejections are
    reported through the owning `Job.progress`, not persisted as game rows.
    """

    __tablename__ = "games"
    __table_args__ = (
        # Scopes deduplication to a profile: the same game uploaded by two different
        # profiles is not a duplicate of each other.
        UniqueConstraint("profile_id", "content_hash", name="uq_games_profile_content_hash"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[GameSource] = mapped_column(pg_enum(GameSource, "game_source"), nullable=False)
    # Platform game id for Lichess/Chess.com imports (Phase 9). Null for manual upload.
    source_game_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # sha256 over normalised movetext + result + players + date — see
    # app/domain/imports/parsing.py for the exact recipe.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    headers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    focus_color: Mapped[GameColor | None] = mapped_column(
        pg_enum(GameColor, "game_color"), nullable=True
    )
    opponent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    time_control: Mapped[str | None] = mapped_column(String(64), nullable=True)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_pgn_path: Mapped[str] = mapped_column(String(500), nullable=False)

    job: Mapped[Job | None] = relationship(back_populates="games")


__all__ = ["Game", "GameColor", "Job", "JobKind", "JobStatus"]
