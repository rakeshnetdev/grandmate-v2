"""Deterministic, LLM-free training-plan fallback (Phase 15, D-032).

Same role `fallback.py` documents for game reports: used whenever the LLM path can't be
trusted (no budget, or the critic rejected an ungrounded claim after one retry). A plain
weakness listing is exactly as true as LLM prose describing the same weaknesses —
persona-matrix.md's invariant holds here too.
"""

from __future__ import annotations

from typing import Any

from app.db.models import Persona
from app.domain.reports.facts import Fact


def build_fallback_training_plan(facts: list[Fact], persona: Persona) -> dict[str, Any]:
    weaknesses = [f for f in facts if f.kind == "recurring_weakness"]
    chunks_by_weakness: dict[str, list[Fact]] = {}
    for fact in facts:
        if fact.kind == "knowledge_chunk":
            chunks_by_weakness.setdefault(fact.data["weakness_name"], []).append(fact)

    return {
        "summary": _summary_text(weaknesses, persona),
        "findings": [
            _finding(weakness, chunks_by_weakness.get(weakness.data["name"], []), persona)
            for weakness in weaknesses
        ],
        "recommendations": _recommendations(weaknesses, persona),
    }


def _summary_text(weaknesses: list[Fact], persona: Persona) -> str:
    if not weaknesses:
        return (
            "No recurring pattern stood out clearly enough yet — keep playing and "
            "check back once more games are analysed."
        )
    names = ", ".join(w.data["name"].replace("_", " ") for w in weaknesses)
    if persona == Persona.KID:
        return f"Your games show a few things to practise: {names}."
    if persona == Persona.COACH:
        return f"The student's recent games show recurring: {names}."
    return f"Your recent games show a recurring pattern in: {names}."


def _finding(weakness: Fact, chunks: list[Fact], persona: Persona) -> dict[str, Any]:
    name = weakness.data["name"].replace("_", " ")
    rate_pct = round(weakness.data["occurrence_rate"] * 100)
    fact_ids = [weakness.id] + [c.id for c in chunks]

    if persona == Persona.KID:
        text = f"You've run into {name} in a few of your games — a great thing to practise!"
    elif persona == Persona.COACH:
        text = (
            f"{name.capitalize()} recurs in {rate_pct}% of the student's analysed games "
            f"({weakness.data['games_with_finding']} games)."
        )
    else:
        text = (
            f"{name.capitalize()} shows up in {rate_pct}% of your recent games "
            f"({weakness.data['games_with_finding']} games)."
        )
    return {"fact_ids": fact_ids, "text": text}


def _recommendations(weaknesses: list[Fact], persona: Persona) -> list[str]:
    if not weaknesses:
        return []
    top = weaknesses[0].data["name"].replace("_", " ")
    if persona == Persona.KID:
        return [f"Practice spotting {top} in a few puzzles this week."]
    if persona == Persona.COACH:
        return [f"Assign the student a focused drill set on {top} and review it next session."]
    return [f"Work through a set of {top} puzzles or study material this week."]


__all__ = ["build_fallback_training_plan"]
