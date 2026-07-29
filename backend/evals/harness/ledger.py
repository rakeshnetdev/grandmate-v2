"""Consolidated score ledger across every eval suite (Phase 16, `evaluation-strategy.md`).

Every harness in `evals/harness/` already writes one JSON record per run to
`evals/runs/`, per rule 12's "evaluation is never run informally and discarded." What
did not exist before this module is a single place that reads *all* of them, trends each
suite's scores run-over-run, and flags a regression — the "unify the harness across all
datasets" task project-plan.md's Phase 16 lists.

Deliberately not a schema migration. Rewriting every harness to emit an identical
`results` shape would touch six already-working, already-evaluated modules for a purely
cosmetic gain. Each suite's `results` dict is genuinely heterogeneous by design — a
retrieval run reports per-strategy sub-metrics, an agent-trajectory run reports
per-agent-type sub-metrics, a memory run reports booleans — so this module works with
that heterogeneity by flattening any nested `results` dict into `dotted.path -> value`
pairs and trending each path independently, rather than forcing one flat shape.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import EvaluationSettings

_TIMESTAMP_PREFIX_RE = re.compile(r"^\d{8}T\d{6}Z_")

# Metric-name suffix -> (settings attribute for the threshold, direction, gating
# strength). "min" means the value must be >= threshold; a run below it is a failure.
# Only Faithfulness/Answer Accuracy are hard per evaluation-strategy.md's threshold
# table — Context Precision/Recall are soft (recorded and reported, never blocking).
# Faithfulness/Answer Accuracy are *review-gated* (see `_REVIEW_GATED_INVARIANT_NAMES`
# below) — hard only once the golden set backing the run has been human-reviewed.
_RAGAS_GATE_RULES: dict[str, tuple[str, str, bool]] = {
    "faithfulness": ("ragas_faithfulness_threshold", "min", True),
    "answer_accuracy": ("ragas_answer_accuracy_threshold", "min", True),
    "context_precision": ("ragas_context_precision_threshold", "min", False),
    "context_recall": ("ragas_context_recall_threshold", "min", False),
}

# Zero-tolerance invariants (evaluation-strategy.md's threshold table): each of these
# metric names means "no divergence/unsafe output at all" by construction — always
# exactly 1.0, not a tunable policy value, the same way `claude.md` rule 11 treats a
# fixed correctness invariant differently from a real policy threshold. Review-gated:
# "a synthetic/unreviewed set never silently becomes the golden set" per
# evaluation-strategy.md's Datasets section — a content-quality judgment (did the model
# actually preserve every fact, stay safe for a child) is only as trustworthy as the
# golden set it was judged against, exactly the reasoning `test_persona_fidelity_quality.
# py` and `test_training_fidelity_quality.py` already apply per-suite.
_REVIEW_GATED_INVARIANT_NAMES = {
    "fact_invariance_rate",
    "top_weakness_invariance_rate",
    "kid_safety_rate",
    "retention_true_positive_rate",
    "retention_true_negative_rate",
}

# Unconditionally hard, review status notwithstanding: both are code-level mechanism
# checks ("did isolation hold", "did the stale flag actually get resolved"), not a
# judgment about golden-set content quality — evaluation-strategy.md calls this out
# explicitly for cross-profile isolation ("a code-level guarantee, not something a
# model's judgment could pass or fail").
_UNCONDITIONAL_INVARIANT_NAMES = {"cross_profile_isolated", "staleness_resolved"}


@dataclass(frozen=True)
class RunRecord:
    suite: str
    path: Path
    timestamp: datetime
    raw: dict[str, Any]

    @property
    def flat_results(self) -> dict[str, float | bool]:
        return _flatten(self.raw.get("results", {}))

    @property
    def is_reviewed(self) -> bool:
        """Whether *any* row of the golden set behind this run has a human
        `reviewed_by`. Field name varies by harness (`reviewed_scenario_count` vs
        retrieval's `reviewed_query_count`) since each dataset's unit is named for what
        it actually contains; a suite with neither field (none exist yet) counts as
        reviewed, since it has no review concept to gate on in the first place."""
        count = self.raw.get("reviewed_scenario_count", self.raw.get("reviewed_query_count"))
        return count is None or count > 0


def _flatten(value: dict[str, Any], prefix: str = "") -> dict[str, float | bool]:
    """Recursively flattens a `results` dict into `dotted.path -> scalar` pairs.
    Non-scalar leaves that aren't further dicts (e.g. `mrr_by_qtype`'s nested dict is
    flattened too, but a list value has nothing meaningful to trend and is dropped)."""
    out: dict[str, float | bool] = {}
    for key, val in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            out.update(_flatten(val, path))
        elif isinstance(val, bool):
            out[path] = val
        elif isinstance(val, (int, float)):
            out[path] = float(val)
    return out


def _suite_name(path: Path) -> str:
    """`20260729T063820Z_training_fidelity.json` -> `training_fidelity` — the harness
    that produced this run, not a value stored redundantly inside the JSON itself."""
    stem = path.stem
    if _TIMESTAMP_PREFIX_RE.match(stem + "_"):
        return stem[stem.index("_") + 1 :]
    return stem


def discover_runs(runs_dir: Path) -> dict[str, list[RunRecord]]:
    """Every recorded run, grouped by suite and ordered oldest-to-newest."""
    by_suite: dict[str, list[RunRecord]] = {}
    for path in sorted(runs_dir.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        suite = _suite_name(path)
        timestamp = datetime.fromisoformat(raw["timestamp"])
        by_suite.setdefault(suite, []).append(
            RunRecord(suite=suite, path=path, timestamp=timestamp, raw=raw)
        )
    for runs in by_suite.values():
        runs.sort(key=lambda r: r.timestamp)
    return by_suite


@dataclass(frozen=True)
class Regression:
    suite: str
    metric: str
    previous: float
    current: float

    @property
    def delta(self) -> float:
        return round(self.current - self.previous, 4)


def find_regressions(runs: list[RunRecord], tolerance: float) -> list[Regression]:
    """Compares the latest run to the one immediately before it. A metric that drops by
    more than `tolerance` is a regression — flagged even if the absolute value still
    clears its own threshold, per evaluation-strategy.md's own example (0.94 -> 0.86 is
    a real signal even though both pass 0.85). Boolean metrics never regress by
    magnitude; only `True -> False` counts, handled by the hard-invariant gate instead."""
    if len(runs) < 2:
        return []
    previous, current = runs[-2], runs[-1]
    regressions = []
    for metric, current_value in current.flat_results.items():
        if isinstance(current_value, bool):
            continue
        previous_value = previous.flat_results.get(metric)
        if previous_value is None or isinstance(previous_value, bool):
            continue
        if current_value < previous_value - tolerance:
            regressions.append(
                Regression(
                    suite=current.suite,
                    metric=metric,
                    previous=previous_value,
                    current=current_value,
                )
            )
    return regressions


@dataclass(frozen=True)
class GateResult:
    suite: str
    metric: str
    value: float | bool
    threshold: float | bool
    hard: bool
    passed: bool


def check_gates(run: RunRecord, settings: EvaluationSettings) -> list[GateResult]:
    """Every metric in this run that a threshold applies to, gated or informative per
    evaluation-strategy.md's own table. A metric name with no matching rule (e.g. a
    suite-specific count like `n_scenarios`) is simply not gated — absence of a rule is
    not a pass, it means the metric carries no threshold to begin with.

    A rule that is nominally "hard" only actually gates once `run.is_reviewed` — an
    unreviewed golden set can produce a real, informative score (D-025's Phase 10
    example: 0.70 faithfulness against an unreviewed set, correctly not blocking that
    phase), it just cannot be the thing that stops a phase on its own yet."""
    results: list[GateResult] = []
    for metric, value in run.flat_results.items():
        leaf = metric.rsplit(".", 1)[-1]

        if leaf in _UNCONDITIONAL_INVARIANT_NAMES or leaf in _REVIEW_GATED_INVARIANT_NAMES:
            threshold: float | bool = True if isinstance(value, bool) else 1.0
            passed = value is True if isinstance(value, bool) else value >= 1.0
            enforced = leaf in _UNCONDITIONAL_INVARIANT_NAMES or run.is_reviewed
            results.append(
                GateResult(
                    suite=run.suite,
                    metric=metric,
                    value=value,
                    threshold=threshold,
                    hard=enforced,
                    passed=passed,
                )
            )
            continue

        rule = _RAGAS_GATE_RULES.get(leaf)
        if rule is None or isinstance(value, bool):
            continue
        setting_name, direction, nominally_hard = rule
        threshold = getattr(settings, setting_name)
        passed = value >= threshold if direction == "min" else value <= threshold
        results.append(
            GateResult(
                suite=run.suite,
                metric=metric,
                value=value,
                threshold=threshold,
                hard=nominally_hard and run.is_reviewed,
                passed=passed,
            )
        )
    return results


@dataclass(frozen=True)
class LedgerReport:
    generated_at: datetime
    latest_by_suite: dict[str, RunRecord]
    regressions: list[Regression] = field(default_factory=list)
    gates: list[GateResult] = field(default_factory=list)

    @property
    def failed_hard_gates(self) -> list[GateResult]:
        return [g for g in self.gates if g.hard and not g.passed]


def build_ledger_report(
    runs_dir: Path, settings: EvaluationSettings, *, tolerance: float | None = None
) -> LedgerReport:
    tol = tolerance if tolerance is not None else settings.eval_regression_tolerance
    by_suite = discover_runs(runs_dir)
    latest_by_suite = {suite: runs[-1] for suite, runs in by_suite.items()}
    regressions = [r for runs in by_suite.values() for r in find_regressions(runs, tol)]
    gates = [g for run in latest_by_suite.values() for g in check_gates(run, settings)]
    return LedgerReport(
        generated_at=datetime.now(),
        latest_by_suite=latest_by_suite,
        regressions=regressions,
        gates=gates,
    )


def render_markdown(report: LedgerReport) -> str:
    lines = [
        "# Evaluation Score Ledger",
        "",
        f"Generated: {report.generated_at.isoformat()}",
        "",
        "## Latest score per suite",
        "",
    ]
    for suite in sorted(report.latest_by_suite):
        run = report.latest_by_suite[suite]
        lines.append(f"### {suite}")
        lines.append(f"Run: `{run.path.name}` ({run.timestamp.isoformat()})")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for metric, value in sorted(run.flat_results.items()):
            lines.append(f"| {metric} | {value} |")
        lines.append("")

    lines.append("## Regressions (run-over-run)")
    lines.append("")
    if report.regressions:
        lines.append("| Suite | Metric | Previous | Current | Delta |")
        lines.append("|-------|--------|----------|---------|-------|")
        for r in report.regressions:
            lines.append(f"| {r.suite} | {r.metric} | {r.previous} | {r.current} | {r.delta} |")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Hard gate failures")
    lines.append("")
    failed = report.failed_hard_gates
    if failed:
        lines.append("| Suite | Metric | Value | Threshold |")
        lines.append("|-------|--------|-------|-----------|")
        for g in failed:
            lines.append(f"| {g.suite} | {g.metric} | {g.value} | {g.threshold} |")
    else:
        lines.append("None.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    runs_dir = Path(__file__).resolve().parents[1] / "runs"
    reports_dir = Path(__file__).resolve().parents[1] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report = build_ledger_report(runs_dir, settings.evaluation)
    markdown = render_markdown(report)
    (reports_dir / "ledger.md").write_text(markdown, encoding="utf-8")
    print(markdown)

    if report.failed_hard_gates:
        print(f"\n{len(report.failed_hard_gates)} hard gate(s) failed.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()


__all__ = [
    "GateResult",
    "LedgerReport",
    "Regression",
    "RunRecord",
    "build_ledger_report",
    "check_gates",
    "discover_runs",
    "find_regressions",
    "render_markdown",
]
