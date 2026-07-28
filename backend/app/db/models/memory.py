"""Long-term profile memory (Phase 11, ADR-0005, D-013, D-026).

The audited Postgres mirror ADR-0005 requires alongside the LangGraph store: this table
is what an audit UI can list and a user can delete, in plain typed SQL, independent of
the store's own generic key-value representation
(`orchestration/store.py`). Entries **supersede** rather than get overwritten by the
system — `superseded_at` is set, the row remains, so a wrong memory stays traceable — but
an explicit user-initiated delete (the audit UI's own action, not the system correcting
itself) removes the row outright: "delete" as a user-facing action means gone, a
different guarantee than the system's own supersession trail.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum


class MemoryKind(enum.StrEnum):
    """`coach_note` is deliberately not a member yet — there is no coach-viewing feature
    for it to attach to (ADR-0012 still defers cross-account viewing); adding it now
    would mean testing and maintaining a kind nothing can use (D-026)."""

    PREFERENCE = "preference"
    GOAL = "goal"
    RECURRING_FINDING = "recurring_finding"


class LongTermMemory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One durable, cross-session fact about a profile."""

    __tablename__ = "long_term_memory"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[MemoryKind] = mapped_column(pg_enum(MemoryKind, "memory_kind"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # The chat thread a memory was extracted from — provenance, so "why does the
    # assistant think this" is always answerable. Nullable: not every future writer of
    # this table need be chat (e.g. a later onboarding-preferences flow).
    source_thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_threads.id", ondelete="SET NULL"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_active(self) -> bool:
        return self.superseded_at is None


__all__ = ["LongTermMemory", "MemoryKind"]
