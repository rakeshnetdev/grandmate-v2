"""Tone/persona-fidelity evaluation harness (Phase 16, `evaluation-strategy.md`).

Reuses `persona_fidelity_eval.py`'s exact generation path (`_generate`: attempt, critic,
retry, fallback against the real golden persona-fidelity scenarios) rather than
regenerating content through a second, parallel pipeline — the grounding behaviour is
already that harness's job; this one adds a second, tone-focused judgment on top of the
*same* generated text via `tone_judge.judge_tone`.

Deliberately scoped to a slice of the golden set (`_SCENARIO_LIMIT`), not all 30 rows:
this harness already spends one real generation call per (scenario, persona) plus one
real judge call per successful generation — running the full set would roughly double
the already-real spend `persona_fidelity_eval.py` incurs on the same scenarios, for a
metric that (per this module's own docstring) doesn't need the full breadth Faithfulness
grounding does — tone/register is a property of the persona, not the specific scenario
content, so far fewer examples are needed to get a meaningful read.

**Needs a real `OPENAI_API_KEY`** — no database required, same as `persona_fidelity_eval.py`.

Usage (from `backend/`):
    uv run python -m evals.harness.tone_fidelity_eval
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.db.models import Persona
from app.domain.reports.selection import select_for_persona
from app.integrations.llm.openai_provider import OpenAIChatProvider
from evals.harness.persona_fidelity_dataset import (
    PersonaFidelityScenario,
    load_persona_fidelity_scenarios,
)
from evals.harness.persona_fidelity_eval import DATASET_PATH, _generate
from evals.harness.tone_judge import ToneJudgeResult, judge_tone

DATASET_VERSION = "v1-2026-07-28"
HARNESS_VERSION = "phase-16-v1"
RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"

_PERSONAS = [Persona.SELF_LEARNER, Persona.COACH, Persona.KID]
# See the module docstring for why this is a deliberate slice, not the full golden set.
_SCENARIO_LIMIT = 10


@dataclass(frozen=True)
class ScenarioToneResult:
    scenario_id: str
    persona: str
    grounded: bool
    tone: ToneJudgeResult | None


async def _score_one(
    llm: OpenAIChatProvider,
    scenario: PersonaFidelityScenario,
    persona: Persona,
    settings: Settings,
) -> ScenarioToneResult:
    selected = select_for_persona(scenario.facts, persona, settings.reports)
    generation = await _generate(llm, scenario, persona, settings.reports, selected)
    # Tone is only meaningful to judge on content that actually reached a reader — a
    # fallback report's wording is fixed, deterministic prose already covered by
    # `test_reports_fallback.py`'s own persona-voice assertions, not something an LLM
    # judge call would tell us anything new about.
    tone = await judge_tone(llm, persona, generation.content) if generation.grounded else None
    return ScenarioToneResult(
        scenario_id=scenario.scenario_id,
        persona=persona.value,
        grounded=generation.grounded,
        tone=tone,
    )


async def run() -> dict[str, Any]:
    settings = get_settings()
    scenarios = load_persona_fidelity_scenarios(DATASET_PATH)[:_SCENARIO_LIMIT]
    reviewed_count = sum(1 for s in scenarios if s.reviewed_by)
    if reviewed_count == 0:
        print(
            "WARNING: no golden scenario has `reviewed_by` set yet. Per "
            "evaluation-strategy.md's golden-vs-synthetic rule, these scores are "
            "informative only until a human spot-checks the set."
        )

    llm = OpenAIChatProvider(settings.llm)
    try:
        results = [
            await _score_one(llm, scenario, persona, settings)
            for scenario in scenarios
            for persona in _PERSONAS
        ]
    finally:
        await llm.aclose()

    judged = [r for r in results if r.tone is not None]
    by_persona: dict[str, list[ScenarioToneResult]] = {}
    for r in judged:
        by_persona.setdefault(r.persona, []).append(r)

    def _rate(rows: list[ScenarioToneResult]) -> float | None:
        if not rows:
            return None
        return sum(1 for r in rows if r.tone and r.tone.passed) / len(rows)

    record: dict[str, Any] = {
        "dataset_path": str(DATASET_PATH),
        "dataset_version": DATASET_VERSION,
        "harness_version": HARNESS_VERSION,
        "model": settings.llm.llm_model,
        "reviewed_scenario_count": reviewed_count,
        "total_scenario_count": len(scenarios),
        "timestamp": datetime.now(UTC).isoformat(),
        "results": {
            "tone_fidelity_rate": _rate(judged),
            **{
                f"{persona}.tone_fidelity_rate": _rate(rows) for persona, rows in by_persona.items()
            },
            "n_judged": len(judged),
            "n_generated": len(results),
        },
        "per_scenario": [
            {
                "scenario_id": r.scenario_id,
                "persona": r.persona,
                "grounded": r.grounded,
                "tone": asdict(r.tone) if r.tone else None,
            }
            for r in results
        ],
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_tone_fidelity.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Run recorded: {run_path}")
    return record


def main() -> None:
    record = asyncio.run(run())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()


__all__ = ["run"]
