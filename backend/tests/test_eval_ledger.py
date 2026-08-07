"""Unit tests for `evals/harness/ledger.py` (Phase 16) — pure logic, no DB or LLM key
needed, unlike the eval harnesses themselves, so this lives in the hermetic suite."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.config import EvaluationSettings
from evals.harness.ledger import (
    RunRecord,
    _suite_name,
    build_ledger_report,
    check_gates,
    find_regressions,
)


def _settings(**overrides: object) -> EvaluationSettings:
    return EvaluationSettings(**overrides)  # type: ignore[arg-type]


def _run(
    suite: str,
    results: dict[str, object],
    *,
    timestamp: str = "2026-07-28T00:00:00+00:00",
    reviewed_scenario_count: int | None = None,
) -> RunRecord:
    raw: dict[str, object] = {"timestamp": timestamp, "results": results}
    if reviewed_scenario_count is not None:
        raw["reviewed_scenario_count"] = reviewed_scenario_count
    return RunRecord(
        suite=suite,
        path=Path(f"/tmp/{timestamp}_{suite}.json"),
        timestamp=datetime.fromisoformat(timestamp),
        raw=raw,
    )


class TestSuiteName:
    def test_parses_the_suite_out_of_a_timestamped_filename(self) -> None:
        assert _suite_name(Path("20260729T063820Z_training_fidelity.json")) == "training_fidelity"

    def test_handles_a_multi_word_suite_name(self) -> None:
        assert _suite_name(Path("20260728T162429Z_single_game_chat.json")) == "single_game_chat"


class TestFlatResults:
    def test_flattens_nested_dicts_into_dotted_paths(self) -> None:
        run = _run("retrieval", {"dense": {"context_precision": 0.9}, "n": 3})
        assert run.flat_results == {"dense.context_precision": 0.9, "n": 3.0}

    def test_drops_non_scalar_leaves_like_lists(self) -> None:
        run = _run("x", {"tags": ["a", "b"], "score": 0.5})
        assert run.flat_results == {"score": 0.5}

    def test_preserves_booleans_as_booleans_not_zero_or_one(self) -> None:
        run = _run("memory_quality", {"cross_profile_isolated": True})
        assert run.flat_results == {"cross_profile_isolated": True}


class TestIsReviewed:
    def test_a_suite_with_no_review_concept_counts_as_reviewed(self) -> None:
        run = _run("x", {"score": 0.5})
        assert run.is_reviewed is True

    def test_zero_reviewed_rows_is_not_reviewed(self) -> None:
        run = _run("x", {"score": 0.5}, reviewed_scenario_count=0)
        assert run.is_reviewed is False

    def test_at_least_one_reviewed_row_is_reviewed(self) -> None:
        run = _run("x", {"score": 0.5}, reviewed_scenario_count=1)
        assert run.is_reviewed is True


class TestFindRegressions:
    def test_a_drop_beyond_tolerance_is_flagged(self) -> None:
        previous = _run("x", {"faithfulness": 0.90}, timestamp="2026-07-28T00:00:00+00:00")
        current = _run("x", {"faithfulness": 0.80}, timestamp="2026-07-28T01:00:00+00:00")
        regressions = find_regressions([previous, current], tolerance=0.05)
        assert len(regressions) == 1
        assert regressions[0].metric == "faithfulness"
        assert regressions[0].delta == -0.1

    def test_a_drop_within_tolerance_is_not_flagged(self) -> None:
        previous = _run("x", {"faithfulness": 0.90}, timestamp="2026-07-28T00:00:00+00:00")
        current = _run("x", {"faithfulness": 0.87}, timestamp="2026-07-28T01:00:00+00:00")
        assert find_regressions([previous, current], tolerance=0.05) == []

    def test_an_improvement_is_never_flagged(self) -> None:
        previous = _run("x", {"faithfulness": 0.70}, timestamp="2026-07-28T00:00:00+00:00")
        current = _run("x", {"faithfulness": 0.95}, timestamp="2026-07-28T01:00:00+00:00")
        assert find_regressions([previous, current], tolerance=0.05) == []

    def test_a_single_run_has_nothing_to_compare_against(self) -> None:
        only = _run("x", {"faithfulness": 0.5})
        assert find_regressions([only], tolerance=0.05) == []

    def test_boolean_metrics_are_never_treated_as_a_magnitude_regression(self) -> None:
        previous = _run(
            "x", {"cross_profile_isolated": True}, timestamp="2026-07-28T00:00:00+00:00"
        )
        current = _run(
            "x", {"cross_profile_isolated": False}, timestamp="2026-07-28T01:00:00+00:00"
        )
        assert find_regressions([previous, current], tolerance=0.05) == []


class TestCheckGates:
    # Derived from the configured floor rather than hardcoded: these tests are about the
    # gating *logic*, not about any particular threshold, and a literal here silently stops
    # testing anything the moment `ragas_faithfulness_threshold` is retuned past it.
    def _below_faithfulness_floor(self) -> float:
        return _settings().ragas_faithfulness_threshold - 0.1

    def test_faithfulness_below_threshold_fails_once_reviewed(self) -> None:
        run = _run(
            "single_game_chat",
            {"faithfulness": self._below_faithfulness_floor()},
            reviewed_scenario_count=5,
        )
        gates = check_gates(run, _settings())
        assert len(gates) == 1
        assert gates[0].hard is True
        assert gates[0].passed is False

    def test_faithfulness_below_threshold_is_informative_only_when_unreviewed(self) -> None:
        run = _run(
            "single_game_chat",
            {"faithfulness": self._below_faithfulness_floor()},
            reviewed_scenario_count=0,
        )
        gates = check_gates(run, _settings())
        assert gates[0].hard is False
        assert gates[0].passed is False

    def test_context_precision_is_always_soft_even_when_reviewed(self) -> None:
        run = _run("retrieval", {"context_precision": 0.5}, reviewed_scenario_count=10)
        gates = check_gates(run, _settings())
        assert gates[0].hard is False

    def test_cross_profile_isolation_is_hard_regardless_of_review_status(self) -> None:
        run = _run("memory_quality", {"cross_profile_isolated": False}, reviewed_scenario_count=0)
        gates = check_gates(run, _settings())
        assert gates[0].hard is True
        assert gates[0].passed is False

    def test_kid_safety_rate_below_one_is_informative_only_when_unreviewed(self) -> None:
        run = _run("persona_fidelity", {"kid_safety_rate": 0.9}, reviewed_scenario_count=0)
        gates = check_gates(run, _settings())
        assert gates[0].hard is False
        assert gates[0].passed is False

    def test_an_unrated_metric_produces_no_gate(self) -> None:
        run = _run("training_fidelity", {"n_scenarios": 30}, reviewed_scenario_count=30)
        assert check_gates(run, _settings()) == []


class TestBuildLedgerReport:
    def test_reads_real_run_files_and_reports_the_latest_per_suite(self, tmp_path: Path) -> None:
        (tmp_path / "20260728T000000Z_suite_a.json").write_text(
            '{"timestamp": "2026-07-28T00:00:00+00:00", "results": {"score": 0.5}}'
        )
        (tmp_path / "20260729T000000Z_suite_a.json").write_text(
            '{"timestamp": "2026-07-29T00:00:00+00:00", "results": {"score": 0.9}}'
        )

        report = build_ledger_report(tmp_path, _settings())

        assert report.latest_by_suite["suite_a"].flat_results == {"score": 0.9}
        assert report.regressions == []
