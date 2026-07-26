"""Identity, profile, and permission tables.

Deviation from `final_docs/v2/data-model.md`, deliberate and documented: that draft put
`lichess_id` directly on `users`. Now that both Lichess and Chess.com are login paths
(ADR-0007), provider columns on `users` would mean adding a column per provider and a
nullable-uniqueness rule for each. `user_identities` is the standard shape instead — one
row per linked provider account, so a user can hold both, and adding a third provider is
a row, not a migration.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum


class AuthProvider(enum.StrEnum):
    """Where an identity came from.

    `LICHESS` is real OAuth2 PKCE. `CHESSCOM` is a verified username claim, because
    Chess.com OAuth is approval-gated — see ADR-0014. The distinction matters for trust,
    so it is stored rather than inferred.
    """

    LICHESS = "lichess"
    CHESSCOM = "chesscom"


class ProfileKind(enum.StrEnum):
    """What a profile represents."""

    SELF = "self"
    CHILD = "child"
    STUDENT = "student"
    OPPONENT = "opponent"
    SHARED = "shared"


class Persona(enum.StrEnum):
    """Presentation mode. Orthogonal to role — see ADR-0011."""

    SELF_LEARNER = "self_learner"
    COACH = "coach"
    KID = "kid"


class RelationshipRole(enum.StrEnum):
    """A viewer's relationship to a profile. Governs permission, not presentation."""

    OWNER = "owner"
    COACH = "coach"
    PARENT = "parent"
    VIEWER = "viewer"
    STUDENT = "student"


class GameSource(enum.StrEnum):
    """Where a profile's games come from."""

    LICHESS = "lichess"
    CHESSCOM = "chesscom"
    UPLOAD = "upload"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An authenticated account.

    Deliberately thin: it holds no provider fields. Everything about *how* someone
    authenticates lives in `user_identities`.
    """

    __tablename__ = "users"

    # Nullable: `email:read` is a requested Lichess scope, not a guaranteed one, and the
    # Chess.com path never yields an email at all.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    identities: Mapped[list[UserIdentity]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    profiles: Mapped[list[Profile]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class UserIdentity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A platform account linked to a user, and the proof behind it."""

    __tablename__ = "user_identities"
    __table_args__ = (
        # One platform account maps to at most one user. Without this, two people could
        # both claim the same Chess.com username and each get their own account.
        UniqueConstraint(
            "provider", "provider_user_id", name="uq_user_identities_provider_subject"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[AuthProvider] = mapped_column(
        pg_enum(AuthProvider, "auth_provider"), nullable=False
    )
    # The provider's stable identifier. Usernames can be changed by their owner; this
    # must not be a username for providers that expose anything more durable.
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_username: Mapped[str] = mapped_column(String(255), nullable=False)

    # False would mean an unproven claim. Nothing writes False today — both paths prove
    # ownership before an identity row is created — but the column exists so an
    # unverified link can never be silently indistinguishable from a verified one.
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verification_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="identities")


class Profile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A player identity that can be analysed.

    Distinct from `users`: one account may hold several profiles, and an observed
    opponent has a profile but no account.
    """

    __tablename__ = "profiles"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ProfileKind] = mapped_column(pg_enum(ProfileKind, "profile_kind"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_persona: Mapped[Persona] = mapped_column(
        pg_enum(Persona, "persona"),
        nullable=False,
        default=Persona.SELF_LEARNER,
    )

    owner: Mapped[User] = relationship(back_populates="profiles")
    sources: Mapped[list[ProfileSource]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ProfileSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Links a profile to a platform account its games come from."""

    __tablename__ = "profile_sources"
    __table_args__ = (
        UniqueConstraint("profile_id", "source", "source_username", name="uq_profile_sources_link"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[GameSource] = mapped_column(pg_enum(GameSource, "game_source"), nullable=False)
    source_username: Mapped[str] = mapped_column(String(255), nullable=False)

    # A username someone typed is a claim, not a fact. Unverified sources must never be
    # presented as authoritatively belonging to the user.
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_method: Mapped[str | None] = mapped_column(String(64), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="sources")


class ProfileRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Who may view whom, in what role. The permission gate for ADR-0012.

    Revocation is soft: `revoked_at` is set and the row stays. A hard delete would erase
    the fact that access once existed, which is exactly what an audit needs to see.
    """

    __tablename__ = "profile_relationships"
    __table_args__ = (
        UniqueConstraint(
            "viewer_user_id", "subject_profile_id", "role", name="uq_profile_relationships_grant"
        ),
    )

    viewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[RelationshipRole] = mapped_column(
        pg_enum(RelationshipRole, "relationship_role"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


__all__ = [
    "AuthProvider",
    "GameSource",
    "Persona",
    "Profile",
    "ProfileKind",
    "ProfileRelationship",
    "ProfileSource",
    "RelationshipRole",
    "User",
    "UserIdentity",
]
