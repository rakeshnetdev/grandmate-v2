"""Golden training-plan fidelity dataset loading (Phase 15, D-032).

Schema per line: `scenario_id`, `facts` (a pre-built pool of `recurring_weakness` and
`knowledge_chunk` Fact-shaped dicts, in `training_facts.py`'s exact id/data convention),
`reviewed_by` (`null` until a human spot-checks it — same golden-vs-synthetic rule
`persona_fidelity_dataset.py` documents).

Facts are pre-built rather than derived from a real profile's analytics snapshot and a
real corpus, for the same reason `persona_fidelity_dataset.py` gives: this evaluation is
about the training-plan report layer (`training_selection.py`, `training_prompts.py`, the
LLM, the shared `critic.py`) — weakness detection itself is Phase 8's own suite, and
retrieval itself is Phase 7's, and neither needs re-proving here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.reports.facts import Fact


@dataclass(frozen=True)
class TrainingFidelityScenario:
    scenario_id: str
    facts: list[Fact]
    reviewed_by: str | None


def _fact_from_dict(raw: dict[str, Any]) -> Fact:
    return Fact(
        id=raw["id"],
        kind=raw["kind"],
        severity=raw["severity"],
        ply=raw.get("ply"),
        confidence=raw.get("confidence"),
        data=raw.get("data", {}),
    )


def load_training_fidelity_scenarios(path: Path) -> list[TrainingFidelityScenario]:
    scenarios = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            scenarios.append(
                TrainingFidelityScenario(
                    scenario_id=row["scenario_id"],
                    facts=[_fact_from_dict(f) for f in row["facts"]],
                    reviewed_by=row.get("reviewed_by"),
                )
            )
    return scenarios


__all__ = ["TrainingFidelityScenario", "load_training_fidelity_scenarios"]
