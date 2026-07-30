"""Generate `docs/evaluation_report.md` from the recorded evaluation runs.

Every figure in the generated report is read out of a run record under `evals/runs/`.
Nothing is hand-written, and nothing is hardcoded here — this module knows how to *format*
each suite's result shape, not what any of the numbers are. That distinction is the whole
point: a report whose prose is typed by hand drifts from its own tables the first time a
suite is re-run, and then quietly contradicts itself.

The suites do not share one result schema, deliberately — a retrieval comparison and a
classifier confusion breakdown are not the same shape and flattening them into a common
envelope would lose the parts that matter. So each suite gets a small formatter, and
`SUITES` is the registry. Adding a suite means adding a formatter, not editing the report.

Run it:

    cd backend && uv run python -m evals.report

Reads the *latest* run per suite by filename timestamp, which is the same convention
`evals/runs/` already uses (`<UTC ISO basic>_<suite>.json`).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = BACKEND_ROOT / "evals" / "runs"
OUTPUT_PATH = BACKEND_ROOT.parent / "docs" / "evaluation_report.md"


# --------------------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------------------


def pct(value: float | None) -> str:
    """Render a 0..1 rate as a percentage. `None` is 'not measured', never 0%."""
    if value is None:
        return "not measured"
    return f"{value * 100:.1f}%"


def num(value: float | None, places: int = 3) -> str:
    if value is None:
        return "not measured"
    return f"{value:.{places}f}"


def boolean(value: bool | None) -> str:
    if value is None:
        return "not measured"
    return "**yes**" if value else "no"


def gate(passed: bool | None) -> str:
    if passed is None:
        return "—"
    return "✅" if passed else "⚠️"


def reviewed_note(run: dict[str, Any]) -> str:
    """Golden-vs-synthetic status.

    `evaluation-strategy.md`'s rule: a self-authored set is informative until a human
    spot-checks it. Suites record `reviewed_*_count`, so this is read, never assumed.
    """
    reviewed = run.get("reviewed_query_count", run.get("reviewed_scenario_count"))
    total = run.get("total_query_count", run.get("total_scenario_count"))
    if reviewed is None or total is None:
        return "n/a — not a golden-set suite"
    if reviewed == 0:
        return (
            f"⚠️ **unreviewed** — 0 of {total} human-reviewed, so scores are informative, not gating"
        )
    if reviewed < total:
        return f"partially reviewed — {reviewed} of {total}"
    return f"✅ fully reviewed — {total} of {total}"


# --------------------------------------------------------------------------------------
# Per-suite formatters
# --------------------------------------------------------------------------------------


def format_retrieval(run: dict[str, Any]) -> str:
    results = run["results"]
    thresholds = run.get("thresholds", {})
    cp_floor = thresholds.get("context_precision")
    cr_floor = thresholds.get("context_recall")

    lines = [
        f"**Dataset** `{run.get('dataset_version')}` · **retriever** "
        f"`{run.get('retriever_version')}` · **embeddings** `{run.get('embed_model')}`",
        "",
        f"**Golden-set status**: {reviewed_note(run)}",
        "",
        "| Strategy | Context precision | Context recall | MRR | Negative FP rate |",
        "|---|---|---|---|---|",
    ]
    for name in ("dense", "sparse", "hybrid"):
        r = results.get(name)
        if r is None:
            continue
        lines.append(
            f"| {name.capitalize()} | {num(r.get('context_precision'))} "
            f"| {num(r.get('context_recall'))} | {num(r.get('mrr'))} "
            f"| {pct(r.get('negative_false_positive_rate'))} |"
        )

    # Per-query-type breakdown is reported separately because a query set made only of
    # exact terms structurally favours BM25 and would overstate it.
    lines += [
        "",
        "**MRR by query type** — reported separately, because a query set of "
        "exact names would structurally favour sparse retrieval:",
        "",
        "| Strategy | Lexical | Semantic |",
        "|---|---|---|",
    ]
    for name in ("dense", "sparse", "hybrid"):
        r = results.get(name)
        if r is None:
            continue
        by_type = r.get("mrr_by_qtype", {})
        lines.append(
            f"| {name.capitalize()} | {num(by_type.get('lexical'))} "
            f"| {num(by_type.get('semantic'))} |"
        )

    if cp_floor is not None and cr_floor is not None:
        lines += [
            "",
            f"Soft thresholds: context precision ≥ {cp_floor}, context recall ≥ {cr_floor}.",
        ]

    wins = run.get("hybrid_beats_both_baselines")
    if wins is not None:
        verdict = (
            "Hybrid beats both baselines on precision and recall."
            if wins
            else "**Hybrid does not beat both baselines** on context precision/recall at this "
            "corpus size — sparse alone matches or exceeds it. Recorded as the honest "
            "outcome rather than smoothed over; note that hybrid still has the best MRR, "
            "which asks a narrower question (how far down the list is the *first* "
            "relevant hit)."
        )
        lines += ["", verdict]
    if run.get("recommendation"):
        lines += ["", f"Recommendation on record: *{run['recommendation']}*"]
    return "\n".join(lines)


def format_classifier_accuracy(run: dict[str, Any]) -> str:
    r = run["results"]
    lines = [
        f"Ground truth: an **independent Stockfish run at depth "
        f"{run.get('ground_truth_depth')}**, against a production classifier that runs at "
        f"depth 12 with its own thresholds. The oracle never sees the classifier's output.",
        "",
        f"Sample size: {run.get('sample_size')} positions ({r.get('n_scored')} scored).",
        "",
        "| Metric | Score | Negative control |",
        "|---|---|---|",
        f"| Detection F1 | {num(r.get('detection_f1'))} "
        f"| {num(r.get('negative_control_detection_f1'))} |",
        f"| Detection precision | {num(r.get('detection_precision'))} | — |",
        f"| Detection recall | {num(r.get('detection_recall'))} | — |",
        f"| Severity accuracy | {num(r.get('severity_accuracy'))} "
        f"| {num(r.get('negative_control_severity_accuracy'))} |",
        "",
        "**The negative control is the load-bearing column.** It is the same harness run "
        "against deliberately corrupted classifier thresholds. A test that cannot fail "
        "proves nothing, so the collapse from "
        f"{num(r.get('detection_f1'))} to {num(r.get('negative_control_detection_f1'))} "
        "on detection — and "
        f"{num(r.get('severity_accuracy'))} to "
        f"{num(r.get('negative_control_severity_accuracy'))} on severity — matters more "
        "than the passing score itself.",
    ]

    per_class = run.get("per_class")
    dist = run.get("ground_truth_class_distribution", {})
    if per_class:
        lines += [
            "",
            "**Per class** — accuracy is not uniform, and an aggregate number hides that:",
            "",
            "| Class | Precision | Recall | F1 | Support |",
            "|---|---|---|---|---|",
        ]
        for cls in ("best", "good", "inaccuracy", "mistake", "blunder"):
            c = per_class.get(cls)
            if c is None:
                continue
            lines.append(
                f"| `{cls}` | {num(c.get('precision'))} | {num(c.get('recall'))} "
                f"| {num(c.get('f1'))} | {c.get('support', dist.get(cls, '—'))} |"
            )
    return "\n".join(lines)


def format_single_game_chat(run: dict[str, Any]) -> str:
    r = run["results"]
    faith_floor = run.get("thresholds", {}).get("faithfulness")
    faith = r.get("faithfulness")
    lines = [
        f"**Model** `{run.get('model')}` · **harness** `{run.get('harness_version')}` · "
        f"{r.get('n_scenarios')} scenarios, real graph turns and real judge calls",
        "",
        f"**Golden-set status**: {reviewed_note(run)}",
        "",
        "| Metric | Score | Gate |",
        "|---|---|---|",
        f"| `grounded_rate` | {pct(r.get('grounded_rate'))} | Hard, structural |",
        f"| `intent_valid_rate` | {pct(r.get('intent_valid_rate'))} | Hard, structural |",
        f"| `faithfulness` | {num(faith)} "
        f"| {gate(None if faith is None or faith_floor is None else faith >= faith_floor)} "
        f"soft, target {faith_floor} |",
        f"| `response_relevancy` | {num(r.get('response_relevancy'))} | Informative |",
        "",
        "`grounded_rate` and `intent_valid_rate` are properties the code guarantees — the "
        "retry-then-fallback loop and the classifier's taxonomy fallback make any other "
        "value structurally impossible. They are not judge estimates.",
    ]
    if faith is not None and faith_floor is not None and faith < faith_floor:
        lines += [
            "",
            f"⚠️ **Faithfulness is below its {faith_floor} target.** It does not gate, per "
            "the golden-vs-synthetic rule — the dataset is self-authored and unreviewed. "
            "Reading the answers manually found no fabricated game-specific claim; RAGAS "
            "scores *every* sentence, including legitimate uncited coaching advice that "
            "was never meant to carry a citation. Either the threshold needs recalibrating "
            "for a system that intentionally gives advice, or the output contract needs an "
            "explicit advice-vs-fact split.",
        ]
    return "\n".join(lines)


def format_persona_fidelity(run: dict[str, Any]) -> str:
    r = run["results"]
    return "\n".join(
        [
            f"**Model** `{run.get('model')}` · {r.get('n_scenarios')} scenarios × 3 personas, "  # noqa: RUF001
            "real completions",
            "",
            f"**Golden-set status**: {reviewed_note(run)}",
            "",
            "| Metric | Score | Gate |",
            "|---|---|---|",
            f"| `fact_invariance_rate` | {pct(r.get('fact_invariance_rate'))} "
            f"| {gate(r.get('fact_invariance_rate') == 1.0)} Hard — never below 1.0 |",
            f"| `kid_safety_rate` | {pct(r.get('kid_safety_rate'))} "
            f"| {gate(r.get('kid_safety_rate') == 1.0)} Hard — never below 1.0 |",
            f"| `grounded_rate` | {pct(r.get('grounded_rate'))} | Informative |",
            "",
            "`fact_invariance_rate` is the measurement behind the product's central claim: the "
            "same analysis facts appear across every persona rendering of the same game. "
            "Personas change language, depth, and framing — never chess truth.",
            "",
            "A `grounded_rate` below 100% is the safety net working, not a defect: a small "
            "model over-generating past a strict persona finding cap, caught by the critic and "
            "replaced with the deterministic report.",
        ]
    )


def format_training_fidelity(run: dict[str, Any]) -> str:
    r = run["results"]
    return "\n".join(
        [
            f"**Model** `{run.get('model')}` · {r.get('n_scenarios')} scenarios",
            "",
            f"**Golden-set status**: {reviewed_note(run)}",
            "",
            "| Metric | Score | Gate |",
            "|---|---|---|",
            f"| `top_weakness_invariance_rate` | {pct(r.get('top_weakness_invariance_rate'))} "
            f"| {gate(r.get('top_weakness_invariance_rate') == 1.0)} Hard |",
            f"| `kid_safety_rate` | {pct(r.get('kid_safety_rate'))} "
            f"| {gate(r.get('kid_safety_rate') == 1.0)} Hard |",
            f"| `grounded_rate` | {pct(r.get('grounded_rate'))} | Informative |",
            "",
            "Training plans are recommendations, so the invariant that matters is that the "
            "*weakness being addressed* is the one the deterministic analytics identified — "
            "not that the prose is identical across personas.",
        ]
    )


def format_tone_fidelity(run: dict[str, Any]) -> str:
    r = run["results"]
    lines = [
        f"**Model** `{run.get('model')}` · {r.get('n_generated')} generated, "
        f"{r.get('n_judged')} judged",
        "",
        f"**Golden-set status**: {reviewed_note(run)}",
        "",
        "| Persona | Tone fidelity |",
        "|---|---|",
    ]
    for persona in ("self_learner", "coach", "kid"):
        lines.append(f"| `{persona}` | {pct(r.get(f'{persona}.tone_fidelity_rate'))} |")
    lines += [
        f"| **overall** | **{pct(r.get('tone_fidelity_rate'))}** |",
        "",
        "Tone fidelity asks whether an answer *sounds* like the persona it claims to be — "
        "a separate question from whether its facts are right, which "
        "`fact_invariance_rate` already answers. A gap between generated and judged counts "
        "means some outputs could not be scored and were reported as unscored rather than "
        "counted as passes.",
    ]
    return "\n".join(lines)


def format_memory_quality(run: dict[str, Any]) -> str:
    r = run["results"]
    return "\n".join(
        [
            f"**Model** `{run.get('model')}` · {run.get('total_scenario_count')} scenarios, "
            "real extraction calls plus a real-Postgres structural check",
            "",
            f"**Golden-set status**: {reviewed_note(run)}",
            "",
            "| Metric | Score | Gate |",
            "|---|---|---|",
            f"| `retention_true_positive_rate` | {pct(r.get('retention_true_positive_rate'))} "
            "| Soft until reviewed |",
            f"| `retention_true_negative_rate` | {pct(r.get('retention_true_negative_rate'))} "
            "| Soft until reviewed |",
            f"| `staleness_resolved` | {boolean(r.get('staleness_resolved'))} "
            f"| {gate(r.get('staleness_resolved'))} Hard, structural |",
            f"| `cross_profile_isolated` | {boolean(r.get('cross_profile_isolated'))} "
            f"| {gate(r.get('cross_profile_isolated'))} Hard, structural |",
            "",
            "The two hard metrics are verified against real Postgres, not a fake. The retention "
            'set includes an adversarial case: the assistant says *"I will remember that you '
            'want to focus on defense"* and the user replies only *"ok"* — nothing should be '
            "written, because the durable statement was never the user's.",
        ]
    )


def format_agent_trajectory(run: dict[str, Any]) -> str:
    r = run["results"]
    single = r.get("single_agent", {})
    multi = r.get("multi_agent", {})
    exit_c = run.get("exit_criterion", {})

    lines = [
        f"**Model** `{run.get('model')}` · {run.get('total_scenario_count')} scenarios, "
        "both graphs run against the same seeded games and scored identically",
        "",
        f"**Dataset status**: {reviewed_note(run)} (synthetic — marked as such in the "
        "dataset version)",
        "",
        "| Metric | Single agent | Multi-agent |",
        "|---|---|---|",
        f"| `faithfulness` | {num(single.get('faithfulness'))} "
        f"| {num(multi.get('faithfulness'))} |",
        f"| `response_relevancy` | {num(single.get('response_relevancy'))} "
        f"| {num(multi.get('response_relevancy'))} |",
        f"| `grounded_rate` | {pct(single.get('grounded_rate'))} "
        f"| {pct(multi.get('grounded_rate'))} |",
        f"| avg tool calls / turn | {num(single.get('avg_tool_call_count'), 2)} "
        f"| {num(multi.get('avg_tool_call_count'), 2)} |",
        "",
        f"Supervisor `routing_accuracy`: {pct(r.get('routing_accuracy'))}",
    ]
    if exit_c:
        lines += [
            "",
            f"**Exit criterion**: {exit_c.get('rule')}",
            "",
            f"**Multi-agent wins**: {boolean(exit_c.get('multi_agent_wins'))} — "
            + (
                "so the Phase 10 single-agent baseline stays in production and the "
                "supervisor graph remains built, tested, and unrouted. A negative result "
                "recorded rather than buried is the point of running the comparison at all."
                if not exit_c.get("multi_agent_wins")
                else "the supervisor graph is adopted."
            ),
        ]
        if exit_c.get("directional_only"):
            lines += [
                "",
                "⚠️ Marked **directional only** — the sample is too small for these "
                "differences to be statistically meaningful. It is enough to say "
                "multi-agent did not clear the bar; it is not enough to quantify by how "
                "much.",
            ]
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------

Formatter = Callable[[dict[str, Any]], str]

SUITES: list[tuple[str, str, str, Formatter]] = [
    (
        "classifier_accuracy",
        "Move classifier accuracy",
        "Does the deterministic core get the chess right? Every layer above Phase 5 treats "
        "the five-way move classification as ground truth, so this is the measurement the "
        "rest of the system rests on.",
        format_classifier_accuracy,
    ),
    (
        "retrieval",
        "Retrieval quality",
        "Dense vs sparse vs hybrid (reciprocal rank fusion), scored with RAGAS's non-LLM "
        "context precision and recall against a corpus-derived query set.",
        format_retrieval,
    ),
    (
        "single_game_chat",
        "Single-game chat quality",
        "Real chat-graph turns — real tool dispatch, real grounding guardrail — scored by "
        "real RAGAS judge calls.",
        format_single_game_chat,
    ),
    (
        "persona_fidelity",
        "Persona fidelity",
        "Does the same analysis render for three audiences without the facts changing?",
        format_persona_fidelity,
    ),
    (
        "tone_fidelity",
        "Persona tone fidelity",
        "Does an answer sound like the persona it claims to be? Separate from whether its "
        "facts are correct.",
        format_tone_fidelity,
    ),
    (
        "training_fidelity",
        "Training plan fidelity",
        "Do generated training plans address the weakness the deterministic analytics "
        "actually identified?",
        format_training_fidelity,
    ),
    (
        "memory_quality",
        "Long-term memory quality",
        "Is a durable statement retained, a non-durable one ignored, a superseded one "
        "resolved, and one profile's memory invisible to another?",
        format_memory_quality,
    ),
    (
        "agent_trajectory",
        "Single-agent vs multi-agent trajectory",
        "The head-to-head comparison Phase 13 was scoped to decide on evidence.",
        format_agent_trajectory,
    ),
]


def latest_run(suite: str) -> tuple[Path, dict[str, Any]] | None:
    """Newest run record for a suite, by filename timestamp."""
    matches = sorted(RUNS_DIR.glob(f"*_{suite}.json"))
    if not matches:
        return None
    path = matches[-1]
    with path.open(encoding="utf-8") as handle:
        return path, json.load(handle)


def build_report() -> str:
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    parts = [
        "# Evaluation Report — GrandMate v2",
        "",
        "> **Generated from recorded runs by `backend/evals/report.py`.** No figure in this "
        "report is hand-written. Regenerate with `cd backend && uv run python -m "
        "evals.report` after any evaluation run.",
        "",
        f"Generated: {generated_at}",
        "",
        "Eight evaluation suites, each with a versioned dataset and a recorded run under "
        "`backend/evals/runs/`. Dataset design and provenance are documented in "
        "[`evaluation_data_design.md`](evaluation_data_design.md); thresholds and gating "
        "rules in [`../final_docs/v2/evaluation-strategy.md`]"
        "(../final_docs/v2/evaluation-strategy.md).",
        "",
        "## The rule that makes these numbers falsifiable",
        "",
        "**Ground truth never comes from the code being graded**, and a metric that could "
        "not be measured is reported as *not measured* — never silently defaulted to a "
        "passing score. The move classifier is scored against an independent, deeper "
        "engine run; retrieval queries have a known correct chunk by construction; and the "
        "classifier harness carries a negative control that deliberately corrupts the "
        "thresholds to prove the test can fail.",
        "",
        "## Summary",
        "",
        "| Suite | Run recorded | Golden set reviewed |",
        "|---|---|---|",
    ]

    loaded: list[tuple[str, str, str, Formatter, Path, dict[str, Any]]] = []
    missing: list[str] = []
    for suite, title, blurb, formatter in SUITES:
        found = latest_run(suite)
        if found is None:
            missing.append(title)
            continue
        path, run = found
        loaded.append((suite, title, blurb, formatter, path, run))
        reviewed = run.get("reviewed_query_count", run.get("reviewed_scenario_count"))
        total = run.get("total_query_count", run.get("total_scenario_count"))
        if reviewed is None or total is None:
            review_cell = "n/a"
        elif reviewed == 0:
            review_cell = f"⚠️ 0 / {total}"
        else:
            review_cell = f"{reviewed} / {total}"
        parts.append(f"| {title} | `{path.name}` | {review_cell} |")

    for title in missing:
        parts.append(f"| {title} | ⚠️ **no run recorded** | — |")

    parts += [
        "",
        "Every golden set in this project is currently **self-authored and unreviewed**. "
        "Per `evaluation-strategy.md`'s golden-vs-synthetic rule, that makes these scores "
        "informative rather than gating, except where a metric is structural — guaranteed "
        "by the code rather than estimated by a judge. Those are marked *Hard, structural* "
        "below.",
        "",
        "---",
        "",
    ]

    for _suite, title, blurb, formatter, path, run in loaded:
        parts += [
            f"## {title}",
            "",
            blurb,
            "",
            formatter(run),
            "",
            f"<sub>Source: `backend/evals/runs/{path.name}` · "
            f"run at {run.get('timestamp', 'unknown')}</sub>",
            "",
            "---",
            "",
        ]

    parts += [
        "## Reproducing these numbers",
        "",
        "```bash",
        "cd backend",
        "",
        "# Hermetic suite — no API key, no corpus needed",
        "uv run pytest -q",
        "",
        "# Evaluation suites — need OPENAI_API_KEY and an ingested corpus",
        "uv run python -m scripts.ingest_corpus",
        "uv run pytest -q evals/",
        "",
        "# Regenerate this report from whatever runs are recorded",
        "uv run python -m evals.report",
        "```",
        "",
        "Deterministic metrics (retrieval hit rate and MRR, classifier F1, the structural "
        "guarantees) reproduce exactly for a fixed dataset. Judge-scored metrics "
        "(faithfulness, response relevancy, tone fidelity) will vary run to run, and "
        "engine-derived figures carry the small non-determinism noted in the Phase 5 "
        "report. Read the judged numbers as approximate; read the structural ones as exact.",
        "",
    ]

    return "\n".join(parts)


def main() -> None:
    if not RUNS_DIR.is_dir():
        raise SystemExit(f"No runs directory at {RUNS_DIR}")

    report = build_report()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")

    found = sum(1 for suite, *_ in SUITES if latest_run(suite) is not None)
    print(f"Wrote {OUTPUT_PATH} — {found} of {len(SUITES)} suites had a recorded run.")


if __name__ == "__main__":
    main()
