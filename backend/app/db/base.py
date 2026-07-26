"""SQLAlchemy declarative base and shared column conventions.

The naming convention is not cosmetic. Alembic's autogenerate compares the database
against the models, and unnamed constraints get server-generated names that differ
between environments — which makes a downgrade unable to find what it needs to drop.
Naming them deterministically is what makes migrations reversible, and reversibility is
a requirement in `definition-of-done.md`.
"""

from __future__ import annotations

import enum as _enum
import uuid
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_EnumT = TypeVar("_EnumT", bound=_enum.Enum)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def pg_enum(python_enum: type[_EnumT], name: str) -> SAEnum:
    """A Postgres enum column that stores the member *values*, not their names.

    SQLAlchemy defaults to persisting `Enum.name`, so `AuditAction.USER_LOGIN` would be
    stored as `'USER_LOGIN'` while the Python `StrEnum` compares equal to `'user_login'`.
    That mismatch is invisible through the ORM and bites the moment anyone writes raw SQL
    or reads the table directly.

    `values_callable` makes the database values match the Python values exactly.
    """
    return SAEnum(
        python_enum,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


def utc_now() -> datetime:
    """Timezone-aware current time.

    Used as a Python-side default so tests can freeze time. Columns also carry a
    server-side default, so a row inserted by a migration or by psql is never missing a
    timestamp.
    """
    return datetime.now(UTC)


class UUIDPrimaryKeyMixin:
    """A UUID primary key generated application-side.

    UUIDs rather than serial integers because ids appear in URLs — `/players/{id}` — and
    sequential integers there leak how many profiles exist and invite enumeration.
    """

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """`created_at` and `updated_at`, maintained by the database.

    ``timezone=True`` is required, not stylistic. Without it the columns are
    ``TIMESTAMP WITHOUT TIME ZONE`` while ``utc_now()`` returns an aware datetime, and
    asyncpg refuses the mismatch outright. Beyond that, a platform whose users span time
    zones has no business storing naive timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


__all__ = [
    "NAMING_CONVENTION",
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "pg_enum",
    "utc_now",
]
