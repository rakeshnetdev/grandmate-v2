"""Memory-quality suite (Phase 11, `evaluation-strategy.md`).

Not part of the hermetic `tests/` suite — this needs a real `OPENAI_API_KEY` and a
reachable Postgres. Run explicitly:

    uv run pytest evals/

`staleness_resolved` and `cross_profile_isolated` are hard-gated unconditionally, not
soft-gated behind the golden set's review status the way retention rates are: they are
code-level guarantees (`MemoryService`'s supersession policy, profile-scoped queries),
not something a real model's judgment could ever make pass or fail, so there is no
"informative until reviewed" case for them the way there is for anything measuring an
LLM's extraction quality.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from app.core.config import DatabaseSettings, get_settings

pytestmark = [
    pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"),
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::ResourceWarning"),
]


def _postgres_reachable() -> bool:
    try:
        sync_url = DatabaseSettings(database_url=get_settings().database.database_url).sync_url  # type: ignore[arg-type]
        engine = create_engine(sync_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _postgres_reachable(), reason="Postgres not reachable")
class TestMemoryQuality:
    async def test_staleness_is_resolved_by_supersession(self) -> None:
        from evals.harness.memory_eval import run

        record = await run()

        assert record["results"]["staleness_resolved"] is True

    async def test_memories_never_cross_profile_boundaries(self) -> None:
        from evals.harness.memory_eval import run

        record = await run()

        assert record["results"]["cross_profile_isolated"] is True

    async def test_retention_rates_clear_the_bar_once_the_dataset_is_reviewed(self) -> None:
        from evals.harness.memory_eval import run

        record = await run()

        if record["reviewed_scenario_count"] == 0:
            pytest.skip(
                "Golden set has no reviewed_by entries yet — scores are informative "
                "only until a human spot-checks it (see this module's docstring)."
            )

        tp_rate = record["results"]["retention_true_positive_rate"]
        tn_rate = record["results"]["retention_true_negative_rate"]
        assert tp_rate is not None and tp_rate >= 0.8, (
            f"retention_true_positive_rate {tp_rate} below 0.8"
        )
        assert tn_rate is not None and tn_rate >= 0.8, (
            f"retention_true_negative_rate {tn_rate} below 0.8"
        )
