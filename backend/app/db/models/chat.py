"""Chat thread identity (Phase 10, ADR-0005 short-term memory layer).

`ChatThread` is deliberately thin — it is the listing/identity row a route can query
without touching LangGraph internals, the same role `GameReport` plays for persona
reports. It is **not** where message history lives: the actual turn-by-turn state
(messages, tool calls, intermediate context) is owned by the LangGraph Postgres
checkpointer, keyed on this row's own `id` used as the checkpointer's `thread_id`. Two
separate writes for "a thread exists" and "a thread has this message" would be the same
dual-write inconsistency ADR-0005 flags as a real cost for long-term memory; here there is
only one durable store for messages, and this table exists purely so a caller has
something to list and scope permissions against.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChatThread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A chat conversation, scoped to one profile.

    `active_game_id` is the optional context-injection anchor (project-plan.md's "active
    game and profile context injection") — set when the thread was opened from a game
    detail page, null for a profile-wide conversation. It is a plain nullable FK, not a
    required one: `SET NULL` on the game's deletion so the thread survives losing its
    anchor rather than cascading away a conversation.
    """

    __tablename__ = "chat_threads"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Filled from the first user message once one arrives; null for a brand-new thread
    # with no messages yet.
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_game_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


__all__ = ["ChatThread"]
