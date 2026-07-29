"""Training-plan fidelity evaluation harness (Phase 15, D-032).

Not in project-plan.md's evaluation-cadence table (that table stops adding new suites at
Phase 13 before the Phase 16 consolidation), but CLAUDE.md's general evaluation rule
still applies: this phase adds new LLM behaviour (`training_prompts.py`, reusing the
shared `critic.py`), so it gets its own small golden set and live-model run rather than
relying on Phase 9's persona-fidelity scores for a different prompt/output surface.

Structurally this is `persona_fidelity_eval.py` applied to training plans instead of game
reports, and it measures the same two guarantees for the same reason (rule 9: personas
never alter truth, only framing/depth/tone):

- **grounded_rate**: share of (scenario, persona) plans that passed the critic on the
  first or second attempt, rather than falling back. Informative, not gated — a cheap
  model occasionally failing a strict cap and falling back is the safety net working.
- **top_weakness_invariance_rate**: for each scenario, whether the single highest-ranked
  weakness (`training_selection.rank_weaknesses`'s ordering) is referenced by every
  persona whose own cap could have included it — the training-plan analogue of
  `persona_fidelity_eval.py`'s `fact_invariance_rate`.
- **kid_safety_rate**: share of kid-persona LLM responses with zero centipawn mentions on
  their first attempt.

**Needs a real `OPENAI_API_KEY`** — no database required (see
`training_fidelity_dataset.py`'s own docstring for why the dataset carries pre-built
facts rather than a real analytics snapshot and a real retrieved corpus).

Usage (from `backend/`):
    uv run python -m evals.harness.training_fidelity_eval
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import ReportSettings, Settings, get_settings
from app.db.models import Persona
from app.domain.reports.critic import validate_report
from app.domain.reports.facts import Fact
from app.domain.reports.training_fallback import build_fallback_training_plan
from app.domain.reports.training_prompts import build_training_messages
from app.domain.reports.training_selection import rank_weaknesses, select_training_facts
from app.integrations.llm.base import CompletionRequest
from app.integrations.llm.openai_provider import OpenAIChatProvider
from evals.harness.training_fidelity_dataset import (
    TrainingFidelityScenario,
    load_training_fidelity_scenarios,
)

DATASET_PATH = (
    Path(__file__).resolve().parents[1] / "datasets" / "golden" / "training_fidelity.jsonl"
)
DATASET_VERSION = "v1-2026-07-28"
HARNESS_VERSION = "phase-15-v1"
RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"

_MAX_ATTEMPTS = 2
_PERSONAS = [Persona.SELF_LEARNER, Persona.COACH, Persona.KID]
# The prompt only uses this to phrase "based on your last N games" — no scenario
# scoring depends on its value, so a fixed representative window is enough.
_WINDOW_SIZE = 10


@dataclass(frozen=True)
class GenerationResult:
    grounded: bool
    content: dict[str, Any]
    kid_first_attempt_safe: bool | None


@dataclass(frozen=True)
class PersonaResult:
    grounded: bool
    top_weakness_included: bool
    kid_first_attempt_safe: bool | None


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    personas: dict[str, PersonaResult]


async def _generate(
    llm: OpenAIChatProvider,
    persona: Persona,
    settings: ReportSettings,
    selected: list[Fact],
) -> GenerationResult:
    """One (scenario, persona) generation — mirrors `TrainingService._generate_content`'s
    attempt loop without the DB-backed budget check, out of scope for what this harness
    measures (covered instead by `test_training_service.py`)."""
    kid_first_attempt_safe: bool | None = None

    for attempt in range(_MAX_ATTEMPTS):
        messages = build_training_messages(selected, persona, window_size=_WINDOW_SIZE)
        response = await llm.complete(
            CompletionRequest(messages=messages, response_format="json_object")
        )
        try:
            parsed = json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            parsed = None

        violations = (
            ["not valid JSON"]
            if not isinstance(parsed, dict)
            else validate_report(parsed, selected, persona, settings)
        )
        if persona == Persona.KID and attempt == 0:
            kid_first_attempt_safe = not any("centipawn" in v for v in violations)

        if not violations and isinstance(parsed, dict):
            return GenerationResult(
                grounded=True, content=parsed, kid_first_attempt_safe=kid_first_attempt_safe
            )

    return GenerationResult(
        grounded=False,
        content=build_fallback_training_plan(selected, persona),
        kid_first_attempt_safe=kid_first_attempt_safe,
    )


def _top_weakness_id(facts: list[Fact]) -> str | None:
    ranked = rank_weaknesses([f for f in facts if f.kind == "recurring_weakness"])
    return ranked[0].id if ranked else None


def _fact_ids_in(content: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for finding in content.get("findings", []):
        ids.update(finding.get("fact_ids", []))
    return ids


async def _score_scenario(
    llm: OpenAIChatProvider, scenario: TrainingFidelityScenario, settings: Settings
) -> ScenarioResult:
    top_weakness_id = _top_weakness_id(scenario.facts)
    by_persona: dict[str, PersonaResult] = {}
    for persona in _PERSONAS:
        selected = select_training_facts(scenario.facts, persona, settings.reports)
        result = await _generate(llm, persona, settings.reports, selected)
        fact_ids = _fact_ids_in(result.content)
        by_persona[persona.value] = PersonaResult(
            grounded=result.grounded,
            top_weakness_included=(top_weakness_id is None) or (top_weakness_id in fact_ids),
            kid_first_attempt_safe=result.kid_first_attempt_safe,
        )
    return ScenarioResult(scenario_id=scenario.scenario_id, personas=by_persona)


async def run() -> dict[str, Any]:
    settings = get_settings()
    scenarios = load_training_fidelity_scenarios(DATASET_PATH)
    reviewed_count = sum(1 for s in scenarios if s.reviewed_by)
    if reviewed_count == 0:
        print(
            "WARNING: no golden scenario has `reviewed_by` set yet. Per "
            "evaluation-strategy.md's golden-vs-synthetic rule, these scores are "
            "informative only until a human spot-checks the set."
        )

    llm = OpenAIChatProvider(settings.llm)
    try:
        per_scenario = [await _score_scenario(llm, scenario, settings) for scenario in scenarios]
    finally:
        await llm.aclose()

    all_persona_results = [p for s in per_scenario for p in s.personas.values()]
    total = len(all_persona_results)
    grounded_count = sum(1 for p in all_persona_results if p.grounded)
    invariance_checks = [p.top_weakness_included for p in all_persona_results]
    kid_safety_checks = [
        s.personas["kid"].kid_first_attempt_safe
        for s in per_scenario
        if s.personas["kid"].kid_first_attempt_safe is not None
    ]

    record: dict[str, Any] = {
        "dataset_path": str(DATASET_PATH),
        "dataset_version": DATASET_VERSION,
        "harness_version": HARNESS_VERSION,
        "model": settings.llm.llm_model,
        "reviewed_scenario_count": reviewed_count,
        "total_scenario_count": len(scenarios),
        "timestamp": datetime.now(UTC).isoformat(),
        "results": {
            "grounded_rate": grounded_count / total if total else None,
            "top_weakness_invariance_rate": (
                sum(invariance_checks) / len(invariance_checks) if invariance_checks else None
            ),
            "kid_safety_rate": (
                sum(kid_safety_checks) / len(kid_safety_checks) if kid_safety_checks else None
            ),
            "n_scenarios": len(per_scenario),
        },
        "per_scenario": [
            {
                "scenario_id": s.scenario_id,
                "personas": {k: asdict(v) for k, v in s.personas.items()},
            }
            for s in per_scenario
        ],
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_training_fidelity.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Run recorded: {run_path}")
    return record


def main() -> None:
    record = asyncio.run(run())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
