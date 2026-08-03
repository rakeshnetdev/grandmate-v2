"""The agent-trajectory dataset's game fixtures (Phase 13a).

These are hermetic checks on the *fixtures*, not on agent behaviour — the live comparison
is `evals/harness/agent_trajectory_eval.py`, which needs an API key and a real Postgres.

They exist because of a defect that was invisible for the entire life of the harness:
seeded games never set `canonicalized_at`, which `load_analyzed_games` filters on, so
every cross-game tool saw an empty profile. `ag-accuracy-trend` scored 0.00 relevancy on
both paths in every recorded run, and both agents were right — they had no games to
aggregate. A wrong fixture reads exactly like a wrong answer, which is why it survived so
long, and why the fixture contract is worth asserting directly.
"""

from __future__ import annotations

from pathlib import Path

from evals.harness.agent_trajectory_dataset import (
    HistoryGameFixture,
    load_agent_trajectory_scenarios,
)

DATASET = Path(__file__).resolve().parents[1] / "evals/datasets/synthetic/agent_trajectory.jsonl"

# Mirrors `AnalyticsSettings.analytics_default_window`. Asserted rather than imported so
# that raising the product default cannot silently make this fixture inadequate — the
# test should fail and be looked at, not quietly follow along.
_ANALYTICS_WINDOW = 10


def _scenario(scenario_id: str):
    scenarios = load_agent_trajectory_scenarios(DATASET)
    return next(s for s in scenarios if s.scenario_id == scenario_id)


class TestHistoryFixtureSummary:
    def test_accuracy_is_derived_from_counts_not_asserted(self) -> None:
        """The same rule `AnalysisService._summarize` applies: share of moves that were
        best-or-good. A fixture stating its own accuracy could drift from how production
        computes it, and the trend question would be scored against a number the product
        would never produce."""
        entry = HistoryGameFixture(
            result="1-0",
            focus_color="white",
            counts={"best": 30, "good": 10, "inaccuracy": 5, "mistake": 4, "blunder": 1},
            critical_moments=2,
            days_ago=1,
        )

        summary = entry.summary()

        assert summary["total_moves"] == 50
        assert summary["accuracy"] == 80.0
        assert summary["critical_moments"] == 2


class TestCrossGameScenarioHasEnoughHistory:
    """`ag-accuracy-trend` asks about "my last 10 games". The analytics service compares
    the most recent `window` games against the `window` before them, so a history shorter
    than two full windows leaves the comparison with nothing to compare against — and the
    only honest answer to the question is that there is no trend."""

    def test_the_trend_scenario_spans_two_full_windows(self) -> None:
        scenario = _scenario("ag-accuracy-trend")

        # The active game occupies one slot of the current window, hence 2*window - 1.
        assert len(scenario.history) >= _ANALYTICS_WINDOW * 2 - 1

    def test_the_history_is_ordered_and_unambiguous(self) -> None:
        """Distinct `days_ago` values: ordering is what splits current from previous, and
        ties would make which window a game lands in depend on insertion order."""
        scenario = _scenario("ag-accuracy-trend")

        days = [entry.days_ago for entry in scenario.history]
        assert len(set(days)) == len(days)

    def test_there_is_a_real_trend_to_report(self) -> None:
        """A flat history would score identically whether or not the agent read it. The
        recent window has to actually differ from the older one for the question to have a
        checkable answer."""
        scenario = _scenario("ag-accuracy-trend")
        recent = scenario.history[: _ANALYTICS_WINDOW - 1]
        older = scenario.history[_ANALYTICS_WINDOW - 1 :]

        recent_accuracy = sum(e.summary()["accuracy"] for e in recent) / len(recent)
        older_accuracy = sum(e.summary()["accuracy"] for e in older) / len(older)

        assert recent_accuracy - older_accuracy > 10


class TestSingleGameScenariosAreUnchanged:
    def test_history_defaults_to_empty(self) -> None:
        """`history` is additive: every scenario that predates it keeps loading, with no
        prior games, exactly as before."""
        scenarios = load_agent_trajectory_scenarios(DATASET)
        without_history = [s for s in scenarios if not s.history]

        assert len(without_history) == len(scenarios) - 1
        assert _scenario("ag-my-opening").history == []
