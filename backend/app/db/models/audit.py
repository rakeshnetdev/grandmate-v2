"""Audit trail.

Cross-profile access and long-term memory writes both emit events here. The reason is
concrete: a coach viewing twelve students is normal, an account viewing four hundred
profiles is not, and without a log there is no way to tell those apart.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, pg_enum, utc_now


class AuditAction(enum.StrEnum):
    """Auditable actions. Extended as later phases add their own."""

    USER_LOGIN = "user_login"
    IDENTITY_LINKED = "identity_linked"
    PROFILE_CREATED = "profile_created"
    PROFILE_VIEWED = "profile_viewed"
    RELATIONSHIP_GRANTED = "relationship_granted"
    RELATIONSHIP_REVOKED = "relationship_revoked"


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """An append-only record of a permission-sensitive action.

    No `TimestampMixin`: audit rows are never updated, so an `updated_at` column would be
    a lie. `created_at` alone, set by the database.
    """

    __tablename__ = "audit_events"

    # Nullable so a failed login attempt — where no user is established — is still
    # recordable. `SET NULL` on delete keeps the event after the account goes.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[AuditAction] = mapped_column(
        pg_enum(AuditAction, "audit_action"), nullable=False, index=True
    )
    subject_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Free-form context. Must never contain secrets — this table is for who-did-what, not
    # for payloads.
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utc_now,
        nullable=False,
        index=True,
    )


__all__ = ["AuditAction", "AuditEvent"]
