"""Daily LLM token usage (Phase 9, D-022).

One row per UTC calendar day, incremented atomically after each completion call using
the provider's own reported token counts — never estimated, same principle
`core/devinsight`'s recorder already documents for trace token counts. `day` is the
primary key directly rather than a surrogate UUID: there is exactly one row per day by
construction (upserted, never duplicated), so a separate identity column would carry no
information a lookup by day doesn't already have.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class LLMUsageDaily(Base, TimestampMixin):
    """Cumulative prompt+completion tokens spent across all LLM calls on one UTC day."""

    __tablename__ = "llm_usage_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    tokens_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


__all__ = ["LLMUsageDaily"]
