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

    findings: list[dict[str, Any]] = []
    for fact in other_facts:
        finding: dict[str, Any] = {"fact_ids": [fact.id], "text": _finding_text(fact, persona)}
        # "kind" is self-learner-game-format-only (Phase 16a, D-035 addendum) — coach
        # and kid keep their original Phase 9 finding shape unchanged.
        if persona == Persona.SELF_LEARNER:
            finding["kind"] = _finding_kind(fact)
        findings.append(finding)

    return {
        "summary": _summary_text(summary_fact, opening_fact, persona),
        "findings": findings,
        "recommendations": _recommendations(other_facts, persona),
    }


def _finding_kind(fact: Fact) -> str:
    return "strength" if fact.data.get("classification") == "best" else "mistake"


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
        if fact.data.get("classification") == "best":
            return _positive_move_finding_text(fact, persona)
        return _move_finding_text(fact, persona)
    if fact.kind == "motif":
        return _motif_finding_text(fact, persona)
    if fact.kind == "theme":
        return _theme_finding_text(fact, persona)
    return "Notable finding."


def _move_label(ply: int) -> tuple[int, str]:
    return ply // 2 + 1, "White" if ply % 2 == 0 else "Black"


def _move_ref(fact: Fact, move_number: int) -> str:
    san = fact.data.get("san")
    return f"{san} (move {move_number})" if san else f"move {move_number}"


def _positive_move_finding_text(fact: Fact, persona: Persona) -> str:
    """A BEST move that landed a real tactic (Phase 16a, D-035 addendum) — self-learner
    only in practice (`selection.py` never gives coach/kid these facts), but handled for
    all three personas rather than left to the generic "Notable finding." fallback."""
    ply = fact.data["ply"]
    move_number, side = _move_label(ply)
    move_ref = _move_ref(fact, move_number)
    motif = fact.data.get("motif")
    motif_note = f" — a {motif.replace('_', ' ')}" if motif else ""
    if persona == Persona.KID:
        return f"{side} found a great move at {move_ref}!"
    if persona == Persona.COACH:
        return f"The student's {move_ref} ({side}) was best{motif_note}."
    return f"{side}'s {move_ref} was best{motif_note}."


def _move_finding_text(fact: Fact, persona: Persona) -> str:
    ply = fact.data["ply"]
    classification = fact.data["classification"]
    swing = fact.data.get("eval_swing_cp")
    # A forced mate has no natural centipawn value (classification.py's
    # _MATE_SCORE_CP is a classification-strength sentinel, not a real swing) — describe
    # it in words instead of ever printing that sentinel as if it were centipawns.
    mate_swing = fact.data.get("mate_swing", False)
    move_number, side = _move_label(ply)

    if persona == Persona.KID:
        return f"Move {move_number} ({side}) was a big mistake — a chance to do better next time!"
    if persona == Persona.COACH:
        if mate_swing:
            swing_note = " (missed or allowed a forced mate)"
        elif swing:
            swing_note = f" (lost {swing} centipawns)"
        else:
            swing_note = ""
        return f"The student's move {move_number} ({side}) was a {classification}{swing_note}."

    # SELF_LEARNER (Phase 16a, D-035 addendum): third person (never "you"/"your"), names
    # the move played and the better move, no engine numbers — eval_swing_cp is a
    # classification-strength signal only now, never printed as text (mate_swing is
    # still described in words, since "a forced mate was missed" is a chess idea, not a
    # number — see the original bug this guards against in classification.py).
    move_ref = _move_ref(fact, move_number)
    best_san = fact.data.get("best_move_san")
    if mate_swing:
        better_note = " A forced mate was missed or allowed."
    elif best_san:
        better_note = f" {best_san} kept more of the position."
    else:
        better_note = ""
    return f"{side}'s {move_ref} was a {classification}.{better_note}"


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

    # SELF_LEARNER (Phase 16a, D-035 addendum): up to 2, each tied to a specific named
    # mistake rather than generic advice — mirrors _move_finding_text's move naming.
    mistakes = [f for f in facts if f.kind == "move" and f.data.get("classification") != "best"]
    recommendations = []
    for fact in mistakes[:2]:
        move_number, side = _move_label(fact.data["ply"])
        move_ref = _move_ref(fact, move_number)
        recommendations.append(f"Review {side}'s {move_ref} and practice the idea it missed.")
    return recommendations


__all__ = ["build_fallback_report"]
