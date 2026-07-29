"""Agent-trajectory comparison suite — Phase 13's exit criterion
(`rag-architecture.md` §7, `evaluation-strategy.md`).

Not part of the hermetic `tests/` suite — needs a real `OPENAI_API_KEY` and a reachable
Postgres. Run explicitly:

    uv run pytest evals/

`grounded_rate` is a structural guarantee on both paths (the Phase 10 guardrail and the
Phase 13 critic both hard-enforce it, never delivering an ungrounded answer) — asserted
at 1.0 unconditionally regardless of dataset review status, same reasoning
`test_single_game_chat_quality.py` uses for its own `grounded_rate` check.

The win/lose comparison and routing accuracy are **not** gated here even provisionally:
the dataset is synthetic and unreviewed (D-029), and n=12 is too small for RAGAS's
judge variance to settle into a reliable signal either way. These tests only assert the
harness runs and records a result — reading whether multi-agent actually won is a
phase-report judgement call, not a pass/fail gate a human hasn't reviewed yet.
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
class TestAgentTrajectoryQuality:
    async def test_both_paths_deliver_only_grounded_answers(self) -> None:
        """Structural guarantee on both graphs, not a judge estimate — the Phase 10
        guardrail and the Phase 13 critic each hard-enforce this independently."""
        from evals.harness.agent_trajectory_eval import run

        record = await run()

        assert record["results"]["single_agent"]["grounded_rate"] == 1.0
        assert record["results"]["multi_agent"]["grounded_rate"] == 1.0

    async def test_the_comparison_is_recorded_for_the_phase_report(self) -> None:
        """Informative only — see the module docstring for why this does not gate a
        win/lose verdict at n=12 against an unreviewed set."""
        from evals.harness.agent_trajectory_eval import run

        record = await run()

        assert record["results"]["single_agent"]["faithfulness"] is not None
        assert record["results"]["multi_agent"]["faithfulness"] is not None
        assert record["results"]["routing_accuracy"] is not None
        assert "multi_agent_wins" in record["exit_criterion"]
