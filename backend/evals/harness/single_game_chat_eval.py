"""RAGAS answer-quality evaluation harness (Phase 10, `evaluation-strategy.md`).

Runs the golden single-game-chat dataset through the **real** chat graph — the same
`build_chat_graph`/`ChatGraphDeps` `ChatService` uses, a real `gpt-4o-mini` completion,
real tool dispatch, and the real grounding guardrail, exactly as a user's message would
be handled — and scores each answer with RAGAS's Faithfulness and Response Relevancy.

Each scenario seeds its own throwaway `Profile`/`Game`/`GameMove`/`GameAnalysis`/
`MoveEvaluation` rows (and `OpeningMatch`, where the scenario has one) from data the
dataset module derives mechanically via `python-chess` — see
`single_game_chat_dataset.py`'s docstring for why moves are stored as SAN and replayed
rather than hand-typed as FEN. Real DB rows, not fixtures the tools bypass, are what let
this harness measure the same code path a user's message actually takes.

**Needs a real `OPENAI_API_KEY`** and a reachable Postgres — this is why it lives outside
`app/` and outside the hermetic `tests/` suite, run on demand rather than as part of
`uv run pytest`.

Usage (from `backend/`):
    uv run python -m evals.harness.single_game_chat_eval
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    Game,
    GameAnalysis,
    GameMove,
    GameSource,
    MoveClassification,
    MoveEvaluation,
    OpeningMatch,
    Persona,
    Profile,
    ProfileKind,
    User,
)
from app.db.session import create_engine, create_session_factory, session_scope
from app.domain.chat.prompts import INTENTS
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.memory import MemoryService
from app.domain.patterns import load_opening_index
from app.integrations.llm.openai_provider import OpenAIChatProvider, OpenAIEmbeddingProvider
from app.orchestration.checkpointer import open_checkpointer
from app.orchestration.graphs.chat import ChatGraphDeps, build_chat_graph
from app.orchestration.store import open_store
from app.orchestration.tools import ToolContext
from evals.harness.ragas_compat import ensure_ragas_importable
from evals.harness.single_game_chat_dataset import (
    SingleGameChatScenario,
    load_single_game_chat_scenarios,
    replay_moves,
)

# See ragas_compat.py: must run before any `import ragas`, as its own statement.
ensure_ragas_importable()

from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # noqa: E402
from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms import LangchainLLMWrapper  # noqa: E402
from ragas.metrics import Faithfulness, ResponseRelevancy  # noqa: E402

_HARNESS_DIR = Path(__file__).resolve().parent
DATASET_PATH = _HARNESS_DIR.parent / "datasets" / "golden" / "single_game_chat.jsonl"
RUNS_DIR = _HARNESS_DIR.parent / "runs"
DATASET_VERSION = "v1-2026-07-28"
HARNESS_VERSION = "phase-10-v1"


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    intent_valid: bool
    grounded: bool
    tool_call_count: int
    faithfulness: float | None
    response_relevancy: float | None
    # Recorded so a human reviewing a low score (this run's `reviewed_by` pass, or
    # anyone reading the run file later) can see *what was actually said* without
    # re-running the harness against a real model to find out.
    answer: str


async def _seed_game(session: AsyncSession, scenario: SingleGameChatScenario) -> Game:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Eval fixture")
    session.add(profile)
    await session.flush()

    game = Game(
        profile_id=profile.id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers=scenario.headers,
        raw_pgn_path="pgn/eval-fixture.pgn",
    )
    session.add(game)
    await session.flush()

    for move in replay_moves(scenario.moves):
        session.add(
            GameMove(
                game_id=game.id,
                ply=move.ply,
                san=move.san,
                uci=move.uci,
                fen_before=move.fen_before,
                fen_after=move.fen_after,
                epd_after=move.epd_after,
            )
        )

    analysis = GameAnalysis(
        game_id=game.id, analysis_version="eval-v1", engine_depth=12, summary={}
    )
    session.add(analysis)
    await session.flush()
    for evaluation in scenario.evaluations:
        session.add(
            MoveEvaluation(
                game_analysis_id=analysis.id,
                ply=evaluation.ply,
                eval_cp=evaluation.eval_cp,
                mate_in=evaluation.mate_in,
                best_move_uci=None,
                classification=MoveClassification(evaluation.classification),
                eval_swing_cp=evaluation.eval_swing_cp,
                is_critical_moment=evaluation.is_critical_moment,
            )
        )

    if scenario.opening is not None:
        session.add(
            OpeningMatch(
                game_id=game.id,
                eco=scenario.opening.eco,
                opening_name=scenario.opening.opening_name,
                epd=replay_moves(scenario.moves)[scenario.opening.matched_ply].epd_after,
                matched_ply=scenario.opening.matched_ply,
            )
        )

    await session.flush()
    return game


async def _score_scenario(
    session: AsyncSession,
    scenario: SingleGameChatScenario,
    settings: Settings,
    llm: OpenAIChatProvider,
    embedding_provider: OpenAIEmbeddingProvider,
    opening_index: Any,
    faithfulness_metric: Faithfulness,
    relevancy_metric: ResponseRelevancy,
) -> ScenarioResult:
    game = await _seed_game(session, scenario)

    async with (
        open_checkpointer(settings.database) as checkpointer,
        open_store(settings.database) as store,
    ):
        deps = ChatGraphDeps(
            llm=llm,
            llm_settings=settings.llm,
            agent_settings=settings.agents,
            budget=LLMBudgetTracker(session, settings.llm),
            tool_context=ToolContext(
                session=session,
                profile_id=game.profile_id,
                settings=settings,
                embedding_provider=embedding_provider,
                opening_index=opening_index,
                store=store,
            ),
            memory=MemoryService(session, store, settings.memory),
        )
        graph = build_chat_graph(deps, checkpointer)
        result = await graph.ainvoke(
            {
                "question": scenario.question,
                "active_game_id": str(game.id),
                "persona": Persona.SELF_LEARNER.value,
            },
            config={"configurable": {"thread_id": str(uuid.uuid4())}},
        )

    answer = result["answer"]
    tool_results = result.get("context", [])
    retrieved_contexts = [json.dumps(item) for item in tool_results] or [""]

    faithfulness_sample = SingleTurnSample(
        user_input=scenario.question, response=answer, retrieved_contexts=retrieved_contexts
    )
    relevancy_sample = SingleTurnSample(user_input=scenario.question, response=answer)

    faithfulness_score: float | None = None
    relevancy_score: float | None = None
    try:
        faithfulness_score = await faithfulness_metric.single_turn_ascore(faithfulness_sample)
    except Exception as exc:
        print(f"WARNING: faithfulness scoring failed for {scenario.scenario_id}: {exc}")
    try:
        relevancy_score = await relevancy_metric.single_turn_ascore(relevancy_sample)
    except Exception as exc:
        print(f"WARNING: response relevancy scoring failed for {scenario.scenario_id}: {exc}")

    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        intent_valid=result.get("intent") in INTENTS,
        grounded=bool(result["grounded"]),
        tool_call_count=len(tool_results),
        faithfulness=faithfulness_score,
        response_relevancy=relevancy_score,
        answer=answer,
    )


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


async def run() -> dict[str, Any]:
    settings = get_settings()
    scenarios = load_single_game_chat_scenarios(DATASET_PATH)

    reviewed_count = sum(1 for s in scenarios if s.reviewed_by)
    if reviewed_count == 0:
        print(
            "WARNING: no golden scenario has `reviewed_by` set yet. Per "
            "evaluation-strategy.md's golden-vs-synthetic rule, these scores are "
            "informative only until a human spot-checks the set."
        )

    api_key = settings.llm.openai_api_key.get_secret_value()
    ragas_llm = LangchainLLMWrapper(ChatOpenAI(model=settings.llm.llm_model, api_key=api_key))
    ragas_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model=settings.retrieval.embed_model, openai_api_key=api_key)
    )
    faithfulness_metric = Faithfulness(llm=ragas_llm)
    relevancy_metric = ResponseRelevancy(llm=ragas_llm, embeddings=ragas_embeddings)

    llm = OpenAIChatProvider(settings.llm)
    embedding_provider = OpenAIEmbeddingProvider(settings.llm, settings.retrieval)
    opening_index = load_opening_index(settings.patterns)
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    results: list[ScenarioResult] = []
    try:
        for scenario in scenarios:
            async with session_scope(session_factory) as session:
                results.append(
                    await _score_scenario(
                        session,
                        scenario,
                        settings,
                        llm,
                        embedding_provider,
                        opening_index,
                        faithfulness_metric,
                        relevancy_metric,
                    )
                )
    finally:
        await llm.aclose()
        await embedding_provider.aclose()
        await engine.dispose()

    faithfulness_scores = [r.faithfulness for r in results if r.faithfulness is not None]
    relevancy_scores = [r.response_relevancy for r in results if r.response_relevancy is not None]

    record: dict[str, Any] = {
        "dataset_path": str(DATASET_PATH),
        "dataset_version": DATASET_VERSION,
        "harness_version": HARNESS_VERSION,
        "model": settings.llm.llm_model,
        "reviewed_scenario_count": reviewed_count,
        "total_scenario_count": len(scenarios),
        "timestamp": datetime.now(UTC).isoformat(),
        "thresholds": {
            "faithfulness": settings.evaluation.ragas_faithfulness_threshold,
        },
        "results": {
            "faithfulness": _avg(faithfulness_scores),
            "response_relevancy": _avg(relevancy_scores),
            "intent_valid_rate": _avg([1.0 if r.intent_valid else 0.0 for r in results]),
            "grounded_rate": _avg([1.0 if r.grounded else 0.0 for r in results]),
            "n_scenarios": len(results),
        },
        "per_scenario": [
            {
                "scenario_id": r.scenario_id,
                "intent_valid": r.intent_valid,
                "grounded": r.grounded,
                "tool_call_count": r.tool_call_count,
                "faithfulness": r.faithfulness,
                "response_relevancy": r.response_relevancy,
                "answer": r.answer,
            }
            for r in results
        ],
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_single_game_chat.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Run recorded: {run_path}")
    return record


def main() -> None:
    record = asyncio.run(run())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()


__all__ = ["run"]
