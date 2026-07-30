"""Deterministic, LLM-free fallback for the full game-story report (Phase 16b).

Mirrors `fallback.py`'s role for the "game" findings-format report: used whenever the
LLM path can't be trusted for the story specifically. Not as narratively rich as an
LLM-generated story — a safe, honest minimum, not a degraded state.
"""

from __future__ import annotations

from typing import Any

from app.domain.reports.facts import Fact

_PHASE_LABELS = {"opening": "Opening", "middlegame": "Middlegame", "endgame": "Endgame"}


def build_story_fallback_report(facts: list[Fact]) -> dict[str, Any]:
    summary_fact = next((f for f in facts if f.kind == "summary"), None)
    opening_fact = next((f for f in facts if f.kind == "opening"), None)
    phase_facts = {f.data["phase"]: f for f in facts if f.kind == "phase"}
    mistake_facts = [
        f for f in facts if f.kind == "move" and f.data.get("classification") != "best"
    ]

    findings: list[dict[str, Any]] = []
    for phase_name in ("opening", "middlegame", "endgame"):
        phase_fact = phase_facts.get(phase_name)
        if phase_fact is None:
            continue
        findings.append(
            {
                "fact_ids": [phase_fact.id],
                "text": _phase_text(phase_name, phase_fact, opening_fact),
                "kind": phase_name,
            }
        )

    for fact in mistake_facts[:2]:
        findings.append({"fact_ids": [fact.id], "text": _lesson_text(fact), "kind": "lesson"})

    return {"summary": _summary_text(summary_fact), "findings": findings, "recommendations": []}


def _summary_text(summary_fact: Fact | None) -> str:
    if summary_fact is None:
        return "No summary available."
    accuracy = summary_fact.data.get("accuracy")
    if accuracy is None:
        return "Game summary unavailable."
    return f"Overall accuracy was {accuracy}%."


def _phase_text(phase_name: str, phase_fact: Fact, opening_fact: Fact | None) -> str:
    label = _PHASE_LABELS[phase_name]
    white_counts = phase_fact.data.get("white_counts", {})
    black_counts = phase_fact.data.get("black_counts", {})
    opening_note = ""
    if phase_name == "opening" and opening_fact is not None:
        opening_note = (
            f" The opening was {opening_fact.data['opening_name']} ({opening_fact.data['eco']})."
        )
    return (
        f"{label}: White's moves were {_count_summary(white_counts)}; "
        f"Black's moves were {_count_summary(black_counts)}.{opening_note}"
    )


def _count_summary(counts: dict[str, int]) -> str:
    if not counts:
        return "not notable"
    return ", ".join(f"{v} {k}" for k, v in counts.items())


def _lesson_text(fact: Fact) -> str:
    ply = fact.data["ply"]
    move_number = ply // 2 + 1
    side = str(fact.data.get("side", "")).capitalize()
    classification = fact.data["classification"]
    san = fact.data.get("san")
    move_ref = f"{san} (move {move_number})" if san else f"move {move_number}"
    return f"{side}'s {move_ref} was a {classification} — worth reviewing."


__all__ = ["build_story_fallback_report"]
