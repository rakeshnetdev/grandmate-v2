"""Daily LLM token budget: check-before-call, atomic record-after-call (Phase 9, D-022).

Enforcement is deliberately a soft-overflow, hard-stop-next guard, not a mid-call abort:
a single call that pushes the running total over the ceiling is allowed to finish
(tokens already spent by the provider can't be un-spent), but the *next* call is refused
before it starts. `LLMSettings.llm_daily_token_ceiling` being `None` means uncapped, the
same meaning that field has documented since Phase 1.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LLMSettings
from app.db.base import utc_now
from app.db.models import LLMUsageDaily


def _today() -> date:
    return datetime.now(UTC).date()


class LLMBudgetTracker:
    def __init__(self, session: AsyncSession, settings: LLMSettings) -> None:
        self._session = session
        self._settings = settings

    async def has_budget(self) -> bool:
        """Whether a new LLM call is allowed to start."""
        ceiling = self._settings.llm_daily_token_ceiling
        if ceiling is None:
            return True
        used = await self._today_usage()
        return used < ceiling

    async def record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Atomically add tokens actually spent — read from the provider's own response,
        never estimated — to today's running total.

        An upsert, not read-then-write: two report generations completing at the same
        moment must not have one's increment silently overwrite the other's. Postgres
        resolves the race, not application code.
        """
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens <= 0:
            return

        now = utc_now()
        stmt = insert(LLMUsageDaily).values(
            day=_today(), tokens_used=total_tokens, created_at=now, updated_at=now
        )
        # `onupdate=utc_now` on the model only fires for ORM-flush updates, not this
        # Core-level upsert, so `updated_at` is set explicitly on both branches here.
        stmt = stmt.on_conflict_do_update(
            index_elements=[LLMUsageDaily.day],
            set_={
                "tokens_used": LLMUsageDaily.tokens_used + stmt.excluded.tokens_used,
                "updated_at": now,
            },
        )
        await self._session.execute(stmt)

    async def _today_usage(self) -> int:
        result = await self._session.execute(
            select(LLMUsageDaily.tokens_used).where(LLMUsageDaily.day == _today())
        )
        return result.scalar_one_or_none() or 0


__all__ = ["LLMBudgetTracker"]
