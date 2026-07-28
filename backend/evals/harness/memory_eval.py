"""Memory-quality evaluation harness (Phase 11, `evaluation-strategy.md`).

Deterministic metrics — `evaluation-strategy.md`'s Phase 11 cadence row names
"Retention precision, staleness, cross-profile isolation" as `Deterministic`, unlike
Phase 10's LLM-judged answer quality — scored two ways:

1. **Retention precision/specificity**: the golden dataset's real (question, answer)
   exchanges run through the real extraction LLM call (`build_extraction_messages` +
   a real `gpt-4o-mini` completion), checked against whether the right kind of memory
   was extracted when it should have been, and nothing was extracted when it should not
   have been. This is the one LLM-judgment-dependent part of this harness — everything
   else here is pure code correctness, verified against a real Postgres database and a
   real `AsyncPostgresStore`, not the in-memory fakes `test_memory_service.py` uses.
2. **Staleness**: restating the same preference twice must leave exactly one active
   entry, not two — proves supersession actually resolves staleness rather than merely
   being exercised against a fake store in a unit test.
3. **Cross-profile isolation**: one profile's memories must never appear in another
   profile's recall.

**Needs a real `OPENAI_API_KEY`** (retention scoring) and a reachable Postgres
(staleness/isolation) — this is why it lives outside `app/` and outside the hermetic
`tests/` suite, run on demand rather than as part of `uv run pytest`.

Usage (from `backend/`):
    uv run python -m evals.harness.memory_eval
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.db.models import Profile, ProfileKind, User
from app.db.session import create_engine, create_session_factory, session_scope
from app.domain.memory import MemoryService, get_active_memories
from app.domain.memory.prompts import build_extraction_messages, parse_candidate_memories
from app.integrations.llm.base import CompletionRequest
from app.integrations.llm.openai_provider import OpenAIChatProvider
from app.orchestration.store import open_store
from evals.harness.memory_dataset import MemoryRetentionScenario, load_memory_retention_scenarios

_HARNESS_DIR = Path(__file__).resolve().parent
DATASET_PATH = _HARNESS_DIR.parent / "datasets" / "golden" / "memory_retention.jsonl"
RUNS_DIR = _HARNESS_DIR.parent / "runs"
DATASET_VERSION = "v1-2026-07-28"
HARNESS_VERSION = "phase-11-v1"


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    should_remember: bool
    correct: bool
    extracted_kind: str | None


async def _score_retention(
    llm: OpenAIChatProvider, scenario: MemoryRetentionScenario, confidence_floor: float
) -> ScenarioResult:
    response = await llm.complete(
        CompletionRequest(
            messages=build_extraction_messages(scenario.question, scenario.answer),
            response_format="json_object",
        )
    )
    candidates = parse_candidate_memories(response.content)
    qualifying = [c for c in candidates if float(c["confidence"]) >= confidence_floor]  # type: ignore[arg-type]

    if not scenario.should_remember:
        return ScenarioResult(scenario.scenario_id, False, len(qualifying) == 0, None)

    match = next(
        (
            c
            for c in qualifying
            if c["kind"] == scenario.expected_kind
            and scenario.expected_content_contains is not None
            and scenario.expected_content_contains.lower() in str(c["content"]).lower()
        ),
        None,
    )
    extracted_kind = str(qualifying[0]["kind"]) if qualifying else None
    return ScenarioResult(scenario.scenario_id, True, match is not None, extracted_kind)


async def _check_staleness_and_isolation(settings: Settings) -> dict[str, bool]:
    """Restates the same preference twice and confirms exactly one entry stays active;
    writes to profile A and confirms profile B recalls nothing — the real-infra
    counterpart to `test_memory_service.py`'s in-memory-store unit tests."""
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)
    try:
        async with session_scope(session_factory) as session:
            user_a, user_b = User(), User()
            session.add_all([user_a, user_b])
            await session.flush()
            profile_a = Profile(owner_user_id=user_a.id, kind=ProfileKind.SELF, display_name="A")
            profile_b = Profile(owner_user_id=user_b.id, kind=ProfileKind.SELF, display_name="B")
            session.add_all([profile_a, profile_b])
            await session.flush()

            async with open_store(settings.database) as store:
                service = MemoryService(session, store, settings.memory)
                await service.write_candidate_memories(
                    profile_a.id,
                    [
                        {
                            "kind": "preference",
                            "content": "Likes long explanations",
                            "confidence": 0.9,
                        }
                    ],
                    source_thread_id=None,
                )
                await service.write_candidate_memories(
                    profile_a.id,
                    [{"kind": "preference", "content": "Prefers short answers", "confidence": 0.9}],
                    source_thread_id=None,
                )
                active_a = await get_active_memories(session, profile_a.id)
                active_b = await get_active_memories(session, profile_b.id)

            return {
                "staleness_resolved": len(active_a) == 1,
                "cross_profile_isolated": len(active_b) == 0,
            }
    finally:
        await engine.dispose()


async def run() -> dict[str, Any]:
    settings = get_settings()
    scenarios = load_memory_retention_scenarios(DATASET_PATH)

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
            await _score_retention(llm, scenario, settings.memory.memory_write_confidence_floor)
            for scenario in scenarios
        ]
    finally:
        await llm.aclose()

    structural = await _check_staleness_and_isolation(settings)

    positives = [r for r in results if r.should_remember]
    negatives = [r for r in results if not r.should_remember]

    record: dict[str, Any] = {
        "dataset_path": str(DATASET_PATH),
        "dataset_version": DATASET_VERSION,
        "harness_version": HARNESS_VERSION,
        "model": settings.llm.llm_model,
        "reviewed_scenario_count": reviewed_count,
        "total_scenario_count": len(scenarios),
        "timestamp": datetime.now(UTC).isoformat(),
        "results": {
            "retention_true_positive_rate": (
                sum(1 for r in positives if r.correct) / len(positives) if positives else None
            ),
            "retention_true_negative_rate": (
                sum(1 for r in negatives if r.correct) / len(negatives) if negatives else None
            ),
            "staleness_resolved": structural["staleness_resolved"],
            "cross_profile_isolated": structural["cross_profile_isolated"],
        },
        "per_scenario": [
            {
                "scenario_id": r.scenario_id,
                "should_remember": r.should_remember,
                "correct": r.correct,
                "extracted_kind": r.extracted_kind,
            }
            for r in results
        ],
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_memory_quality.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Run recorded: {run_path}")
    return record


def main() -> None:
    record = asyncio.run(run())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()


__all__ = ["run"]
