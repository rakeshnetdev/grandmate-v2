"""Golden persona-fidelity dataset loading (Phase 9, `evaluation-strategy.md`).

Schema per line: `scenario_id`, `headers` (PGN-style White/Black/Result), `facts` (a
pre-built list of `Fact`-shaped dicts — the fact *pool* a scenario presents to every
persona), `reviewed_by` (`null` until a human spot-checks it, same
golden-vs-synthetic rule Phase 7's retrieval dataset already documents).

Facts are pre-built rather than derived from a real `GameAnalysis`/pattern-finding rows:
this evaluation is about the report layer (`selection.py`, `prompts.py`, the LLM,
`critic.py`), which is already fully exercised by fixed, known fact pools — extraction
itself (`facts.py`) is separately unit-tested (`test_reports_facts.py`) and does not need
re-proving here. Pre-built facts also mean this suite has no dependency on any specific
game existing in a database.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.reports.facts import Fact


@dataclass(frozen=True)
class PersonaFidelityScenario:
    scenario_id: str
    headers: dict[str, str]
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


def load_persona_fidelity_scenarios(path: Path) -> list[PersonaFidelityScenario]:
    scenarios = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            scenarios.append(
                PersonaFidelityScenario(
                    scenario_id=row["scenario_id"],
                    headers=row["headers"],
                    facts=[_fact_from_dict(f) for f in row["facts"]],
                    reviewed_by=row.get("reviewed_by"),
                )
            )
    return scenarios


__all__ = ["PersonaFidelityScenario", "load_persona_fidelity_scenarios"]
