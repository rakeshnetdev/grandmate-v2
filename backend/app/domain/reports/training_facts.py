"""Extracts structured facts for a training-plan report from a profile's aggregate
analytics and retrieved corpus content (Phase 15, D-032).

Two new `FactKind`s, not a second `Fact` model — training-plan generation is "a new
report type" (D-032), sharing the exact grounding vocabulary and critic (`critic.py`'s
fact_id check) `facts.py`'s game reports already use. This module is the one place that
turns `WeaknessStats` (Phase 8, deterministic) and `RetrievedChunk`s (Phase 7, retrieval)
into that vocabulary — mirroring `facts.py`'s own "translate deterministic
analysis/retrieval into the report layer's vocabulary, nothing downstream touches the
originals" role.
"""

from __future__ import annotations

from app.domain.analytics.metrics import WeaknessStats
from app.domain.reports.facts import Fact
from app.domain.retrieval import RetrievedChunk

# A weakness recurring in at least half the sampled games is treated as more urgent than
# one just above the detection floor — the same two-tier severity split `facts.py` uses
# for moves (blunder/critical-moment vs. inaccuracy/mistake), applied to occurrence rate
# since a weakness fact has no single centipawn swing to judge severity by instead.
_CRITICAL_OCCURRENCE_RATE = 0.5


def extract_training_facts(
    weaknesses: list[WeaknessStats],
    retrieved_by_weakness: dict[str, list[RetrievedChunk]],
    *,
    recently_recommended: set[str],
) -> list[Fact]:
    """The full candidate fact pool for a training plan — persona-independent, same
    "one pool, persona-specific selection downstream" split `extract_facts` uses.

    `recently_recommended` (weakness names present in the profile's own most recent
    prior training plan, any window size — see `training_service.py`) is recorded on
    each weakness fact rather than used to drop facts here: selection, not extraction,
    decides what a persona-capped plan actually shows, and a weakness that keeps
    recurring should still be visible to that decision, just deprioritised against
    fresher ones (D-032: history informs prioritisation, not a hard exclusion).
    """
    facts: list[Fact] = []
    for weakness in weaknesses:
        weakness_id = f"weakness-{weakness.kind}-{weakness.name}"
        facts.append(
            Fact(
                id=weakness_id,
                kind="recurring_weakness",
                severity=(
                    "critical"
                    if weakness.occurrence_rate >= _CRITICAL_OCCURRENCE_RATE
                    else "notable"
                ),
                ply=None,
                confidence=weakness.occurrence_rate,
                data={
                    "weakness_kind": weakness.kind,
                    "name": weakness.name,
                    "games_with_finding": weakness.games_with_finding,
                    "occurrence_rate": weakness.occurrence_rate,
                    "recently_recommended": weakness.name in recently_recommended,
                },
            )
        )
        for index, chunk in enumerate(retrieved_by_weakness.get(weakness.name, [])):
            facts.append(
                Fact(
                    id=f"chunk-{weakness.name}-{index}",
                    kind="knowledge_chunk",
                    severity="info",
                    ply=None,
                    confidence=chunk.score,
                    data={
                        "weakness_name": weakness.name,
                        "content": chunk.content,
                        "retrieved_by": chunk.retrieved_by,
                        "metadata": chunk.metadata,
                    },
                )
            )
    return facts


__all__ = ["extract_training_facts"]
