"""Deterministic, LLM-free pattern feedback (Phase 19, D-037).

Mirrors `reports/fallback.py`'s role: used whenever the LLM path can't be trusted — no
budget, malformed JSON, or a critic rejection on both attempts. Plainer than generated
prose, but it makes exactly the same claims from exactly the same facts, which for this
report matters more than usual: the numbers a player is told about their own history
should not depend on whether an API call succeeded.
"""

from __future__ import annotations

from typing import Any

from app.domain.reports.facts import Fact

_BAND_PHRASES = {
    "well_above": "clearly better than your recent games",
    "above": "a little better than your recent games",
    "in_line": "in line with your recent games",
    "below": "a little below your recent games",
    "well_below": "clearly below your recent games",
}


def _label(name: str) -> str:
    """`hanging_piece` -> `hanging piece`, matching the frontend's own weakness naming."""
    return name.replace("_", " ")


def build_fallback_feedback(facts: list[Fact]) -> dict[str, Any]:
    overall = next((f for f in facts if f.id == "verdict-overall"), None)
    metric_facts = [f for f in facts if f.kind == "verdict" and f.id != "verdict-overall"]
    repeat_facts = [f for f in facts if f.kind == "repeat"]
    improvement_facts = [f for f in facts if f.kind == "improvement"]

    findings: list[dict[str, Any]] = []
    if overall is not None:
        # One plain verdict, citing the per-metric facts alongside the overall one — the
        # metrics are what it rests on, even though (like everything here) it does not
        # reproduce their figures. The table above the prose already shows those.
        findings.append(
            {
                "fact_ids": [overall.id, *(f.id for f in metric_facts)],
                "kind": "verdict",
                "text": _overall_text(overall),
            }
        )
    for fact in repeat_facts:
        findings.append({"fact_ids": [fact.id], "kind": "repeated", "text": _repeat_text(fact)})
    for fact in improvement_facts:
        findings.append(
            {"fact_ids": [fact.id], "kind": "improved", "text": _improvement_text(fact)}
        )

    return {
        "summary": _summary_text(overall, repeat_facts, improvement_facts),
        "findings": findings,
        "recommendations": [
            f"Work on {_label(fact.data['name'])} — it keeps coming back, including in this game."
            for fact in repeat_facts
        ],
    }


def _summary_text(overall: Fact | None, repeats: list[Fact], improvements: list[Fact]) -> str:
    if overall is None:
        return "There was not enough history to compare this game against."
    parts = [f"This game was {_BAND_PHRASES[overall.data['band']]}."]
    if repeats:
        parts.append("Habits you have been carrying showed up again.")
    if improvements:
        # "stayed away" rather than "improved" — the sustained/not-sustained distinction
        # is made per item below, so the summary deliberately makes the weaker claim for
        # all of them.
        parts.append(
            "Others stayed away." if repeats else "Habits you have been carrying stayed away."
        )
    return " ".join(parts)


def _overall_text(fact: Fact) -> str:
    return (
        f"Judged against how you normally play, this game was {_BAND_PHRASES[fact.data['band']]}."
    )


def _repeat_text(fact: Fact) -> str:
    # No move numbers and no counts: the panel above this prose already lists both for
    # every repeat. What is left worth saying is that it is a habit, not an accident.
    return (
        f"{_label(fact.data['name']).capitalize()} came up again — this is something you "
        "keep doing, not a one-off in this game."
    )


def _improvement_text(fact: Fact) -> str:
    name = _label(fact.data["name"])
    if fact.data["sustained"]:
        return f"No {name} — you have kept that out of your games for a while now."
    # One clean game only. Stated as an absence, never as a fix.
    return (
        f"No {name} in this game. It is a habit of yours, so treat this as one clean game "
        "rather than a habit broken."
    )


__all__ = ["build_fallback_feedback"]
