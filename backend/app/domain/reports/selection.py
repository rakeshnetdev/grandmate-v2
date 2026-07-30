"""Persona-specific fact selection: ranking and capping (Phase 9, D-023,
`persona-matrix.md`).
"""

from __future__ import annotations

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.facts import Fact

_SEVERITY_RANK = {"critical": 0, "notable": 1, "info": 2}
_ALWAYS_KEPT_KINDS = frozenset({"summary", "opening"})


def rank_facts(facts: list[Fact]) -> list[Fact]:
    """Deterministic severity-then-confidence ordering, so capping to N always keeps the
    N most significant facts rather than an arbitrary N."""
    return sorted(
        facts,
        key=lambda f: (_SEVERITY_RANK[f.severity], -(f.confidence or 0.0), f.ply or 0),
    )


def _is_positive_move_fact(fact: Fact) -> bool:
    return fact.kind == "move" and fact.data.get("classification") == "best"


def select_for_persona(facts: list[Fact], persona: Persona, settings: ReportSettings) -> list[Fact]:
    """The exact facts one persona's report is built from.

    `summary`/`opening` are unconditional for every persona — they are not "findings"
    the matrix's per-persona caps apply to. The remaining facts are ranked once (the
    same ranking regardless of persona — this is what makes fact-invariance meaningful:
    every persona's cap is a prefix of the *same* ordering, so the most significant fact
    is never hidden from any of them) and then capped per persona's own rule.

    Positive ("what went well") move facts (Phase 16a, D-035 addendum) are self-learner
    only — coach and kid never saw them before this addendum, and folding them into
    coach's unbounded pool or kid's severity-ranked cap would silently change what those
    two personas' reports contain. Only self-learner explicitly opted into this format.
    """
    always_kept = [f for f in facts if f.kind in _ALWAYS_KEPT_KINDS]
    other = [f for f in facts if f.kind not in _ALWAYS_KEPT_KINDS]

    if persona == Persona.SELF_LEARNER:
        positive = rank_facts([f for f in other if _is_positive_move_fact(f)])
        mistakes = rank_facts([f for f in other if not _is_positive_move_fact(f)])
        selected = (
            positive[: settings.report_self_learner_positive_max]
            + mistakes[: settings.report_self_learner_mistake_max]
        )
        return always_kept + selected

    # Coach and kid never receive positive move facts — see the docstring above.
    rankable = rank_facts([f for f in other if not _is_positive_move_fact(f)])

    if persona == Persona.KID:
        rankable = [
            f
            for f in rankable
            if f.confidence is None or f.confidence >= settings.report_kid_min_confidence_to_show
        ]
        rankable = rankable[: settings.report_kid_max_findings]
    # COACH: unbounded — persona-matrix.md states it explicitly, so there is no cap to
    # apply here.

    return always_kept + rankable


__all__ = ["rank_facts", "select_for_persona"]
