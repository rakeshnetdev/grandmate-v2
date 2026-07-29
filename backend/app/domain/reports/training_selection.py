"""Persona-specific weakness selection for a training plan (Phase 15, D-032).

Mirrors `selection.py`'s ranking-then-capping shape exactly, with one addition: a
weakness recently recommended (present in the profile's own last training plan) ranks
behind fresher ones at the same severity, so a plan doesn't repeat itself when there are
other real candidates — but is never dropped outright, since a weakness that keeps
recurring is still true and still worth surfacing if nothing else qualifies (D-032:
history informs prioritisation, not a hard exclusion).
"""

from __future__ import annotations

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.facts import Fact

_SEVERITY_RANK = {"critical": 0, "notable": 1, "info": 2}


def rank_weaknesses(weaknesses: list[Fact]) -> list[Fact]:
    """Not-recently-recommended first, then severity, then occurrence rate — the same
    "rank once, cap per persona from a prefix of one ordering" reasoning
    `selection.py`'s `rank_facts` documents, so no persona's plan hides a weakness a
    more generous persona would also be shown."""
    return sorted(
        weaknesses,
        key=lambda f: (
            f.data["recently_recommended"],
            _SEVERITY_RANK[f.severity],
            -(f.confidence or 0.0),
        ),
    )


def _cap_for(persona: Persona, settings: ReportSettings) -> int | None:
    if persona == Persona.KID:
        return settings.report_kid_max_findings
    if persona == Persona.SELF_LEARNER:
        return settings.report_self_learner_max_findings
    return None  # COACH: unbounded, same as persona-matrix.md states for game reports.


def select_training_facts(
    facts: list[Fact], persona: Persona, settings: ReportSettings
) -> list[Fact]:
    """The exact facts one persona's training plan is built from: the capped set of
    weaknesses, plus every knowledge chunk retrieved for one of them — a chunk is never
    shown for a weakness the cap excluded, since it exists only to ground that
    weakness's recommendation."""
    weaknesses = [f for f in facts if f.kind == "recurring_weakness"]
    ranked = rank_weaknesses(weaknesses)

    cap = _cap_for(persona, settings)
    selected_weaknesses = ranked if cap is None else ranked[:cap]
    selected_names = {f.data["name"] for f in selected_weaknesses}

    chunks = [
        f
        for f in facts
        if f.kind == "knowledge_chunk" and f.data["weakness_name"] in selected_names
    ]
    return selected_weaknesses + chunks


__all__ = ["rank_weaknesses", "select_training_facts"]
