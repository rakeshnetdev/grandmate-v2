"""Deterministic, LLM-free report fallback (Phase 9, D-023).

Used whenever the LLM path can't be trusted — no budget left, or the critic rejected an
ungrounded claim after one retry. Not an error state: `persona-matrix.md`'s invariant
("a persona changes how a finding is said, never whether it is true") holds exactly as
well for a plain fact listing as for LLM prose, so this is the safe default, not a
degraded one.
"""

from __future__ import annotations

from typing import Any

from app.db.models import Persona
from app.domain.reports.facts import Fact


def build_fallback_report(facts: list[Fact], persona: Persona) -> dict[str, Any]:
    summary_fact = next((f for f in facts if f.kind == "summary"), None)
    opening_fact = next((f for f in facts if f.kind == "opening"), None)
    other_facts = [f for f in facts if f.kind not in ("summary", "opening")]

    return {
        "summary": _summary_text(summary_fact, opening_fact, persona),
        "findings": [{"fact_ids": [f.id], "text": _finding_text(f, persona)} for f in other_facts],
        "recommendations": _recommendations(other_facts, persona),
    }


def _summary_text(summary: Fact | None, opening: Fact | None, persona: Persona) -> str:
    if summary is None:
        return "No summary available."
    accuracy = summary.data.get("accuracy")
    opening_name = opening.data.get("opening_name") if opening else None

    if persona == Persona.KID:
        pieces = []
        if opening_name:
            pieces.append(f"You played the {opening_name}.")
        if accuracy is not None:
            pieces.append(f"You played well on {accuracy:.0f}% of your moves.")
        return " ".join(pieces) or "Here's how your game went."

    parts = []
    if opening_name:
        eco = opening.data.get("eco") if opening else None
        parts.append(f"Opening: {opening_name} ({eco})." if eco else f"Opening: {opening_name}.")
    if accuracy is not None:
        parts.append(f"Accuracy: {accuracy}%.")
    counts = summary.data.get("counts", {})
    counted = {k: v for k, v in counts.items() if v}
    if counted:
        parts.append("Move quality: " + ", ".join(f"{v} {k}" for k, v in counted.items()) + ".")
    return " ".join(parts) or "Game summary unavailable."


def _finding_text(fact: Fact, persona: Persona) -> str:
    if fact.kind == "move":
        return _move_finding_text(fact, persona)
    if fact.kind == "motif":
        return _motif_finding_text(fact, persona)
    if fact.kind == "theme":
        return _theme_finding_text(fact, persona)
    return "Notable finding."


def _move_label(ply: int) -> tuple[int, str]:
    return ply // 2 + 1, "White" if ply % 2 == 0 else "Black"


def _move_finding_text(fact: Fact, persona: Persona) -> str:
    ply = fact.data["ply"]
    classification = fact.data["classification"]
    swing = fact.data.get("eval_swing_cp")
    move_number, side = _move_label(ply)

    if persona == Persona.KID:
        return f"Move {move_number} ({side}) was a big mistake — a chance to do better next time!"
    if persona == Persona.COACH:
        swing_note = f" (lost {swing} centipawns)" if swing else ""
        return f"The student's move {move_number} ({side}) was a {classification}{swing_note}."
    swing_note = f", costing {swing} centipawns" if swing else ""
    return f"Your move {move_number} ({side}) was a {classification}{swing_note}."


def _motif_finding_text(fact: Fact, persona: Persona) -> str:
    motif = fact.data["motif"].replace("_", " ")
    move_number = fact.ply // 2 + 1 if fact.ply is not None else None
    if persona == Persona.KID:
        where = f" around move {move_number}" if move_number else ""
        return f"There was a {motif}{where} — good to watch for next time!"
    if persona == Persona.COACH:
        return f"{motif.capitalize()} at ply {fact.ply}."
    return f"A {motif} occurred at ply {fact.ply}."


def _theme_finding_text(fact: Fact, persona: Persona) -> str:
    theme = fact.data["theme"].replace("_", " ")
    if persona == Persona.KID:
        return f"Something to work on: {theme}."
    if persona == Persona.COACH:
        return f"{theme.capitalize()} observed."
    return f"{theme.capitalize()} was a factor in this game."


def _recommendations(facts: list[Fact], persona: Persona) -> list[str]:
    if not facts:
        return []
    if persona == Persona.KID:
        return ["Look for one thing to practice from this game."]
    if persona == Persona.COACH:
        return ["Review the flagged findings with the student and assign a related drill."]
    return ["Review the flagged moves and consider a focused drill on the recurring pattern."]


__all__ = ["build_fallback_report"]
