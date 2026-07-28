"""Integration tests for `LLMBudgetTracker` against a real transactional database — the
atomic upsert is the entire point, so an in-memory fake would not exercise it.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LLMSettings
from app.domain.llm_usage import LLMBudgetTracker


def _settings(**overrides: object) -> LLMSettings:
    return LLMSettings(**overrides)  # type: ignore[arg-type]


class TestHasBudget:
    async def test_uncapped_when_ceiling_is_none(self, db_session: AsyncSession) -> None:
        tracker = LLMBudgetTracker(db_session, _settings(llm_daily_token_ceiling=None))
        await tracker.record_usage(prompt_tokens=10_000_000, completion_tokens=10_000_000)
        assert await tracker.has_budget() is True

    async def test_true_when_under_the_ceiling(self, db_session: AsyncSession) -> None:
        tracker = LLMBudgetTracker(db_session, _settings(llm_daily_token_ceiling=1000))
        await tracker.record_usage(prompt_tokens=100, completion_tokens=100)
        assert await tracker.has_budget() is True

    async def test_false_once_usage_reaches_the_ceiling(self, db_session: AsyncSession) -> None:
        tracker = LLMBudgetTracker(db_session, _settings(llm_daily_token_ceiling=200))
        await tracker.record_usage(prompt_tokens=100, completion_tokens=100)
        assert await tracker.has_budget() is False

    async def test_true_with_no_usage_recorded_yet(self, db_session: AsyncSession) -> None:
        tracker = LLMBudgetTracker(db_session, _settings(llm_daily_token_ceiling=100))
        assert await tracker.has_budget() is True


class TestRecordUsage:
    async def test_repeated_calls_accumulate_atomically(self, db_session: AsyncSession) -> None:
        tracker = LLMBudgetTracker(db_session, _settings(llm_daily_token_ceiling=1000))
        await tracker.record_usage(prompt_tokens=50, completion_tokens=50)
        await tracker.record_usage(prompt_tokens=30, completion_tokens=20)

        # 150 total so far; the ceiling is 1000, so budget must still be available —
        # this only holds if the second call added to the first rather than overwriting.
        assert await tracker.has_budget() is True
        await tracker.record_usage(prompt_tokens=400, completion_tokens=450)
        # 150 + 850 = 1000, at the ceiling.
        assert await tracker.has_budget() is False

    async def test_zero_token_calls_are_a_no_op(self, db_session: AsyncSession) -> None:
        tracker = LLMBudgetTracker(db_session, _settings(llm_daily_token_ceiling=10))
        await tracker.record_usage(prompt_tokens=0, completion_tokens=0)
        assert await tracker.has_budget() is True
