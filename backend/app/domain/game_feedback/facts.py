"""Turns a `GameComparison` into grounded facts (Phase 19, D-037).

Same contract as `reports/facts.py`: the prompt, the critic, and the deterministic
fallback all read `Fact` objects and never the comparison dataclasses directly, so the
model is structurally incapable of citing a claim the comparison did not make. Reuses that
module's `Fact` type rather than defining a parallel one — the id/kind/severity/data
vocabulary and the critic's fact_id check are already generic, and pattern feedback is a
new report type, not a new fact model (the same reasoning Phase 15 and 16b recorded).
"""

from __future__ import annotations

from app.domain.game_feedback.comparison import (
    GameComparison,
    ImprovedWeakness,
    MetricComparison,
    RepeatedWeakness,
)
from app.domain.reports.facts import Fact, Severity

# Human-facing metric names. Kept next to the facts rather than in the prompt so the
# fallback and the LLM path describe the same measure with the same words.
_METRIC_LABELS = {
    "accuracy": "your own move accuracy",
    "blunder_rate": "your blunder rate",
    "critical_moments": "critical moments in your play",
}


def format_metric(name: str, value: float) -> str:
    """A metric rendered the way it should be spoken.

    Every metric reaches the reader through this, because the raw stored value is not
    always the readable one: `blunder_rate` is a ratio, and left alone a model will
    dutifully write "your blunder rate was 0.3704" — observed on a real generation. The
    prompt is given the formatted string and told to use it verbatim, so the LLM path and
    the deterministic fallback cannot drift into different units.
    """
    if name == "accuracy":
        return f"{value:.1f}%"
    if name == "blunder_rate":
        return f"{value * 100:.1f}%"
    return f"{value:.0f}"


# How many move numbers a single repeat fact names before it stops listing them.
_MAX_MOVES_NAMED = 3


def move_number(ply: int) -> int:
    """The move number a 0-indexed ply belongs to — what a player actually counts in."""
    return ply // 2 + 1


def extract_comparison_facts(comparison: GameComparison) -> list[Fact]:
    """Every fact the feedback report may reference, and nothing else."""
    facts: list[Fact] = [
        Fact(
            id="baseline",
            kind="baseline",
            severity="info",
            ply=None,
            confidence=None,
            data={
                "baseline_games": comparison.baseline_games,
                "outcome": comparison.outcome,
            },
        ),
        Fact(
            id="verdict-overall",
            kind="verdict",
            severity="info",
            ply=None,
            confidence=None,
            data={
                "band": comparison.overall_band,
                "outcome": comparison.outcome,
                "baseline_games": comparison.baseline_games,
            },
        ),
    ]
    facts.extend(_metric_fact(metric) for metric in comparison.metrics)
    facts.extend(_repeat_fact(item) for item in comparison.repeated)
    facts.extend(_improvement_fact(item) for item in comparison.improved)
    return facts


def _metric_fact(metric: MetricComparison) -> Fact:
    return Fact(
        id=f"verdict-{metric.name}",
        kind="verdict",
        severity="info",
        ply=None,
        confidence=None,
        data={
            "metric": metric.name,
            "label": _METRIC_LABELS[metric.name],
            # Formatted, not raw — see `format_metric`. The raw numbers stay out of the
            # fact entirely so there is nothing unreadable for a model to quote.
            "value": format_metric(metric.name, metric.value),
            "baseline_mean": format_metric(metric.name, metric.baseline_mean),
            "band": metric.band,
        },
    )


def _repeat_fact(item: RepeatedWeakness) -> Fact:
    # "Critical" once it recurs in more than half the baseline: at that point it is not a
    # tendency the player has, it is how they play, and the report should say so plainly.
    severity: Severity = "critical" if item.occurrence_rate > 0.5 else "notable"
    return Fact(
        id=f"repeat-{item.kind}-{item.name}",
        kind="repeat",
        severity=severity,
        # The first occurrence in this game, so a finding can anchor to a real position;
        # the full list is in `data` for reports that want to name more than one.
        ply=item.plies[0] if item.plies else None,
        confidence=None,
        data={
            "weakness_kind": item.kind,
            "name": item.name,
            "baseline_games_with_finding": item.baseline_games_with_finding,
            "baseline_games": item.baseline_games,
            "occurrence_rate": item.occurrence_rate,
            "occurrences_in_game": len(item.plies),
            # Capped: a habit can fire ten times in one game, and a sentence listing ten
            # move numbers is a wall, not a coaching point (observed on real data). The
            # count above keeps the scale honest; the full list stays on the API response
            # for the UI, which can lay it out rather than having to read it aloud.
            "move_numbers": [move_number(ply) for ply in item.plies[:_MAX_MOVES_NAMED]],
        },
    )


def _improvement_fact(item: ImprovedWeakness) -> Fact:
    return Fact(
        id=f"improved-{item.kind}-{item.name}",
        kind="improvement",
        severity="notable" if item.sustained else "info",
        ply=None,
        confidence=None,
        data={
            "weakness_kind": item.kind,
            "name": item.name,
            "baseline_games_with_finding": item.baseline_games_with_finding,
            "baseline_games": item.baseline_games,
            "occurrence_rate": item.occurrence_rate,
            "clear_streak": item.clear_streak,
            # The prompt keys its wording off this: sustained absence may be called an
            # improvement, a single clean game may only be called an absence.
            "sustained": item.sustained,
        },
    )


__all__ = ["extract_comparison_facts", "format_metric", "move_number"]
