"""Phase 13's exit-criterion harness (`rag-architecture.md` §7, `project-plan.md` Phase
13, D-029): does the multi-agent supervisor graph beat the Phase 10 single-agent
baseline, or does the simpler architecture stay?

Runs every scenario through **both** `build_chat_graph` (Phase 10) and
`build_multi_agent_graph` (Phase 13) against the same seeded game, scored identically —
same RAGAS metrics, same dataset, same model — so the comparison is apples to apples.
Also scores the multi-agent path's own routing decision (`needs_retrieval`/
`needs_analysis`) against each scenario's `expected_needs_*`, the tool-choice-accuracy
metric `evaluation-strategy.md`'s Phase 13 row calls for.

**Needs a real `OPENAI_API_KEY`** and a reachable Postgres, same reason
`single_game_chat_eval.py` lives outside `tests/` — run on demand, not part of
`uv run pytest`:

    uv run python -m evals.harness.agent_trajectory_eval
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# `domain.chat.__init__` -> `domain.chat.service` -> `orchestration.graphs.chat` ->
# `domain.chat.fallback`/`guardrail`/`prompts` is a real circular import; every existing
# entry point happens to resolve it by touching something in `domain.chat` before
# `orchestration.graphs.chat` (e.g. `single_game_chat_eval.py`'s `domain.chat.prompts`
# import). This module has no organic reason to import `domain.chat` directly, so it
# does so explicitly, purely for that ordering.
import app.domain.chat  # noqa: F401
from app.core.config import Settings, get_settings
from app.db.models import (
    ChatThread,
    Game,
    GameAnalysis,
    GameColor,
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
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.patterns import load_opening_index
from app.integrations.llm.openai_provider import OpenAIChatProvider, OpenAIEmbeddingProvider
from app.orchestration.checkpointer import open_checkpointer
from app.orchestration.dependencies import build_chat_graph_deps, build_multi_agent_graph_deps
from app.orchestration.graphs.chat import build_chat_graph
from app.orchestration.graphs.multi_agent import build_multi_agent_graph
from app.orchestration.store import open_store
from evals.harness.agent_trajectory_dataset import (
    AgentTrajectoryScenario,
    load_agent_trajectory_scenarios,
    replay_moves,
)
from evals.harness.ragas_compat import ensure_ragas_importable

# See ragas_compat.py: must run before any `import ragas`, as its own statement.
ensure_ragas_importable()

from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # noqa: E402
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms import LangchainLLMWrapper  # noqa: E402
from ragas.metrics import Faithfulness, ResponseRelevancy  # noqa: E402

_HARNESS_DIR = Path(__file__).resolve().parent
DATASET_PATH = _HARNESS_DIR.parent / "datasets" / "synthetic" / "agent_trajectory.jsonl"
RUNS_DIR = _HARNESS_DIR.parent / "runs"
DATASET_VERSION = "v2-2026-08-03-synthetic"
HARNESS_VERSION = "phase-13-v1"


@dataclass(frozen=True)
class PathResult:
    answer: str
    grounded: bool
    tool_call_count: int
    # Which tools actually fired, not just how many. A path that answers from zero tool
    # calls and a path that answers from the wrong tool both look like a low count;
    # only the names distinguish "never gathered" from "gathered the wrong thing".
    tool_names: list[str]
    faithfulness: float | None
    response_relevancy: float | None


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    routing_category: str
    routing_correct: bool
    multi_agent_trace: list[str]
    single_agent: PathResult
    multi_agent: PathResult


async def _seed_history(
    session: AsyncSession, profile_id: uuid.UUID, scenario: AgentTrajectoryScenario
) -> None:
    """Seed the profile's prior games, so cross-game questions have something to answer.

    Only a `Game` row and a `GameAnalysis.summary` per game: the analytics path reads the
    summary and the result/colour, never the plies (see `analytics/metrics.py`), so
    replaying moves here would cost thousands of lines of fixture that nothing reads.
    """
    for entry in scenario.history:
        game = Game(
            profile_id=profile_id,
            source=GameSource.UPLOAD,
            content_hash=str(uuid.uuid4()),
            headers={"White": "Alice", "Black": "Bob", "Result": entry.result},
            raw_pgn_path="pgn/eval-history.pgn",
            focus_color=GameColor(entry.focus_color),
            played_at=datetime.now(UTC) - timedelta(days=entry.days_ago),
            canonicalized_at=datetime.now(UTC),
        )
        session.add(game)
        await session.flush()
        session.add(
            GameAnalysis(
                game_id=game.id,
                analysis_version="eval-v1",
                engine_depth=12,
                summary=entry.summary(),
            )
        )
    await session.flush()


async def _seed_game(session: AsyncSession, scenario: AgentTrajectoryScenario) -> Game:
    """Same shape as `single_game_chat_eval.py`'s `_seed_game` — real DB rows the tools
    actually query, not fixtures the tool layer bypasses."""
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Eval fixture")
    session.add(profile)
    await session.flush()

    await _seed_history(session, profile.id, scenario)

    game = Game(
        profile_id=profile.id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers=scenario.headers,
        raw_pgn_path="pgn/eval-fixture.pgn",
        # `load_analyzed_games` filters on `canonicalized_at IS NOT NULL`, so a game
        # without it is invisible to every cross-game tool. Unset here until now, which
        # made `get_profile_aggregate` return an empty snapshot in *every* recorded run
        # on *both* paths — `ag-accuracy-trend` scored 0.00 throughout because both
        # agents were correctly reporting that they had no games to aggregate.
        focus_color=GameColor.WHITE,
        played_at=datetime.now(UTC),
        canonicalized_at=datetime.now(UTC),
    )
    session.add(game)
    await session.flush()

    replayed = replay_moves(scenario.moves)
    for move in replayed:
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

    # A real summary, not `{}`. Now that the active game is visible to `load_analyzed_games`
    # it is counted by the cross-game aggregates too, and an empty summary reads there as
    # a game played at 0.0 accuracy with no moves — dragging down every trend the history
    # was seeded to establish. Derived from this scenario's own evaluations by the same
    # rule `AnalysisService._summarize` uses, so the active game and the history entries
    # are measured the same way.
    active_counts = Counter(e.classification for e in scenario.evaluations)
    active_total = len(scenario.evaluations)
    active_good = active_counts.get("best", 0) + active_counts.get("good", 0)
    analysis = GameAnalysis(
        game_id=game.id,
        analysis_version="eval-v1",
        engine_depth=12,
        summary={
            "total_moves": active_total,
            "counts": dict(active_counts),
            "accuracy": round(100 * active_good / active_total, 1) if active_total else 0.0,
            "critical_moments": sum(1 for e in scenario.evaluations if e.is_critical_moment),
        },
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
                epd=replayed[scenario.opening.matched_ply].epd_after,
                matched_ply=scenario.opening.matched_ply,
            )
        )

    await session.flush()
    return game


async def _ragas_score(
    question: str,
    answer: str,
    context: list[dict[str, Any]],
    faithfulness_metric: Faithfulness,
    relevancy_metric: ResponseRelevancy,
    label: str,
) -> tuple[float | None, float | None]:
    retrieved_contexts = [json.dumps(item) for item in context] or [""]
    faithfulness_sample = SingleTurnSample(
        user_input=question, response=answer, retrieved_contexts=retrieved_contexts
    )
    relevancy_sample = SingleTurnSample(user_input=question, response=answer)

    faithfulness_score: float | None = None
    relevancy_score: float | None = None
    try:
        faithfulness_score = await faithfulness_metric.single_turn_ascore(faithfulness_sample)
    except Exception as exc:
        print(f"WARNING: faithfulness scoring failed for {label}: {exc}")
    try:
        relevancy_score = await relevancy_metric.single_turn_ascore(relevancy_sample)
    except Exception as exc:
        print(f"WARNING: response relevancy scoring failed for {label}: {exc}")
    return faithfulness_score, relevancy_score


async def _score_scenario(
    session: AsyncSession,
    scenario: AgentTrajectoryScenario,
    settings: Settings,
    llm: OpenAIChatProvider,
    embedding_provider: OpenAIEmbeddingProvider,
    opening_index: Any,
    faithfulness_metric: Faithfulness,
    relevancy_metric: ResponseRelevancy,
) -> ScenarioResult:
    game = await _seed_game(session, scenario)

    # Real `chat_threads` rows, one per path, rather than a bare `uuid4()` as the graph's
    # thread id. `write_memory` persists `long_term_memory.source_thread_id` as an FK, so
    # an invented id raises `ForeignKeyViolationError` the moment extraction actually
    # yields a memory — intermittently, since most turns yield none. That is a fixture
    # defect, not a product one (in production the thread always exists), but it is the
    # kind that fails one replicate in three and looks like flakiness.
    single_thread = ChatThread(profile_id=game.profile_id, active_game_id=game.id)
    multi_thread = ChatThread(profile_id=game.profile_id, active_game_id=game.id)
    session.add_all([single_thread, multi_thread])
    await session.flush()

    # Both paths are built through the shared dependency builders (`dependencies.py`,
    # rule 13) rather than assembled by hand here. Assembling them separately is what let
    # the two drift: the multi-agent `ToolContext` was constructed without `store`, so
    # any store-backed tool silently degraded on one side of a comparison whose entire
    # purpose is that both sides are otherwise identical.
    async with (
        open_checkpointer(settings.database) as checkpointer,
        open_store(settings.database) as store,
    ):
        # -- Phase 10 single-agent baseline ------------------------------------------
        single_deps = build_chat_graph_deps(
            settings=settings,
            session=session,
            llm=llm,
            embedding_provider=embedding_provider,
            opening_index=opening_index,
            store=store,
            profile_id=game.profile_id,
        )
        single_result = await build_chat_graph(single_deps, checkpointer).ainvoke(
            {
                "question": scenario.question,
                "active_game_id": str(game.id),
                "persona": Persona.SELF_LEARNER.value,
            },
            config={"configurable": {"thread_id": str(single_thread.id)}},
        )

        # -- Phase 13 multi-agent supervisor graph -----------------------------------
        multi_deps = build_multi_agent_graph_deps(
            settings=settings,
            session=session,
            llm=llm,
            embedding_provider=embedding_provider,
            opening_index=opening_index,
            store=store,
            profile_id=game.profile_id,
        )
        multi_result = await build_multi_agent_graph(multi_deps, MemorySaver()).ainvoke(
            {
                "question": scenario.question,
                "active_game_id": str(game.id),
                "persona": Persona.SELF_LEARNER.value,
            },
            config={"configurable": {"thread_id": str(multi_thread.id)}},
        )

    single_context = single_result.get("context", [])
    single_faithfulness, single_relevancy = await _ragas_score(
        scenario.question,
        single_result["answer"],
        single_context,
        faithfulness_metric,
        relevancy_metric,
        f"{scenario.scenario_id}/single-agent",
    )
    single_path = PathResult(
        answer=single_result["answer"],
        grounded=bool(single_result["grounded"]),
        tool_call_count=len(single_context),
        tool_names=[str(item.get("tool")) for item in single_context],
        faithfulness=single_faithfulness,
        response_relevancy=single_relevancy,
    )

    multi_context = [
        *multi_result.get("retrieval_context", []),
        *multi_result.get("analysis_context", []),
    ]
    multi_faithfulness, multi_relevancy = await _ragas_score(
        scenario.question,
        multi_result["answer"],
        multi_context,
        faithfulness_metric,
        relevancy_metric,
        f"{scenario.scenario_id}/multi-agent",
    )
    multi_path = PathResult(
        answer=multi_result["answer"],
        grounded=bool(multi_result["grounded"]),
        tool_call_count=len(multi_context),
        tool_names=[str(item.get("tool")) for item in multi_context],
        faithfulness=multi_faithfulness,
        response_relevancy=multi_relevancy,
    )

    routing_correct = (
        bool(multi_result.get("needs_retrieval")) == scenario.expected_needs_retrieval
        and bool(multi_result.get("needs_analysis")) == scenario.expected_needs_analysis
    )

    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        routing_category=scenario.routing_category,
        routing_correct=routing_correct,
        multi_agent_trace=multi_result.get("trace", []),
        single_agent=single_path,
        multi_agent=multi_path,
    )


# Measured, not guessed: the two clean full runs recorded on 2026-08-02 spent roughly
# 150k tokens each across 12 scenarios x 2 paths x (agent calls + RAGAS judging). The
# margin over that is deliberate — starting a run that dies at scenario 9 wastes
# everything spent up to scenario 9.
_MIN_TOKENS_TO_START = 250_000


async def _remaining_daily_tokens(session: AsyncSession, settings: Settings) -> int | None:
    """Headroom left under today's ceiling, or `None` when no ceiling is configured."""
    ceiling = settings.llm.llm_daily_token_ceiling
    if ceiling is None:
        return None
    tracker = LLMBudgetTracker(session, settings.llm)
    return ceiling - await tracker.today_usage()


def _json_safe(value: Any) -> Any:
    """Last-resort coercion for scalars a scoring library hands back in its own numeric
    types. Anything with `.item()` (every NumPy scalar) becomes its Python equivalent;
    everything else degrades to `repr` rather than raising."""
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except (TypeError, ValueError):
            pass
    return repr(value)


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _path_summary(results: list[ScenarioResult], which: str) -> dict[str, Any]:
    paths = [getattr(r, which) for r in results]
    faithfulness = [p.faithfulness for p in paths if p.faithfulness is not None]
    relevancy = [p.response_relevancy for p in paths if p.response_relevancy is not None]
    return {
        "faithfulness": _avg(faithfulness),
        "response_relevancy": _avg(relevancy),
        "grounded_rate": _avg([1.0 if p.grounded else 0.0 for p in paths]),
        "avg_tool_call_count": _avg([float(p.tool_call_count) for p in paths]),
    }


async def run() -> dict[str, Any]:
    settings = get_settings()
    scenarios = load_agent_trajectory_scenarios(DATASET_PATH)

    reviewed_count = sum(1 for s in scenarios if s.reviewed_by)
    if reviewed_count == 0:
        print(
            "WARNING: no agent-trajectory scenario has `reviewed_by` set yet. Per "
            "evaluation-strategy.md's golden-vs-synthetic rule (D-029), these scores "
            "are directional only until a human spot-checks the set."
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

    # Pre-flight: the daily token ceiling is checked by *both* graphs before every LLM
    # call, so exhausting it mid-run does not fail anything — each path quietly degrades
    # to its deterministic fallback and keeps scoring. The run then reports a confident
    # architecture verdict built partly on answers no model ever produced. That happened:
    # a run finished with 500,970 of a 500,000 ceiling spent, and the scenarios after the
    # crossover degraded on both sides. Refusing to start is the only honest option —
    # a comparison that silently measures the budget guard is worse than no comparison.
    async with session_scope(session_factory) as preflight_session:
        remaining = await _remaining_daily_tokens(preflight_session, settings)
    if remaining is not None and remaining < _MIN_TOKENS_TO_START:
        await llm.aclose()
        await embedding_provider.aclose()
        await engine.dispose()
        raise RuntimeError(
            f"Refusing to start: only {remaining} tokens left under today's "
            f"LLM_DAILY_TOKEN_CEILING ({settings.llm.llm_daily_token_ceiling}), and this "
            f"run needs roughly {_MIN_TOKENS_TO_START}. Raise the ceiling or wait for the "
            "daily reset — a partially budget-starved run produces a verdict about the "
            "budget guard, not about the architectures."
        )

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

    async with session_scope(session_factory) as postflight_session:
        remaining_after = await _remaining_daily_tokens(postflight_session, settings)

    single_summary = _path_summary(results, "single_agent")
    multi_summary = _path_summary(results, "multi_agent")
    routing_accuracy = _avg([1.0 if r.routing_correct else 0.0 for r in results])

    # The exit criterion (rag-architecture.md §7): multi-agent must clear single-agent
    # on both RAGAS metrics to be called a win. With n=12 and RAGAS's known judge
    # variance (see D-025 on Phase 10's own 0.70-vs-0.85 run), this is a directional
    # signal, not a statistically powered comparison — the phase report says so
    # explicitly rather than overclaiming a verdict this dataset size cannot support.
    # `bool(...)` is load-bearing, not decoration. RAGAS scores come back as `np.float64`,
    # which *is* a `float` subclass and so serialises fine — but comparing two of them
    # yields `np.bool_`, which is not a `bool` subclass, and under NumPy 2 reports its
    # type name as plain "bool". A completed run (every scenario scored, real API spend)
    # died at `json.dumps` on this one value with a message that reads like a lie.
    multi_wins = bool(
        single_summary["faithfulness"] is not None
        and multi_summary["faithfulness"] is not None
        and multi_summary["faithfulness"] >= single_summary["faithfulness"]
        and single_summary["response_relevancy"] is not None
        and multi_summary["response_relevancy"] is not None
        and multi_summary["response_relevancy"] >= single_summary["response_relevancy"]
    )

    record: dict[str, Any] = {
        "dataset_path": str(DATASET_PATH),
        "dataset_version": DATASET_VERSION,
        "harness_version": HARNESS_VERSION,
        "model": settings.llm.llm_model,
        "reviewed_scenario_count": reviewed_count,
        # Recorded so a reader can always tell whether a run had room to finish honestly.
        # `tokens_spent_by_run` is the delta across the run; a `daily_budget_remaining`
        # at or below zero means later scenarios degraded to fallbacks on both paths and
        # the aggregate scores below describe the budget guard, not the architectures.
        "daily_budget_remaining_before": remaining,
        "daily_budget_remaining_after": remaining_after,
        "tokens_spent_by_run": (
            remaining - remaining_after
            if remaining is not None and remaining_after is not None
            else None
        ),
        "total_scenario_count": len(scenarios),
        "timestamp": datetime.now(UTC).isoformat(),
        "results": {
            "single_agent": single_summary,
            "multi_agent": multi_summary,
            "routing_accuracy": routing_accuracy,
        },
        "exit_criterion": {
            "rule": "multi-agent must match or beat single-agent on both faithfulness "
            "and response_relevancy to be adopted; otherwise the Phase 10 baseline "
            "stays (rag-architecture.md §7)",
            "multi_agent_wins": multi_wins,
            "directional_only": True,
        },
        "per_scenario": [
            {
                "scenario_id": r.scenario_id,
                "routing_category": r.routing_category,
                "routing_correct": r.routing_correct,
                "multi_agent_trace": r.multi_agent_trace,
                "single_agent": vars(r.single_agent),
                "multi_agent": vars(r.multi_agent),
            }
            for r in results
        ],
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_agent_trajectory.json"
    # `default=` rather than trusting every value to be a builtin: an unserialisable
    # scalar arriving from a scoring library must not be able to throw away a finished
    # run's results at the last statement. Recording something slightly lossy beats
    # recording nothing after every scenario has already been paid for.
    run_path.write_text(json.dumps(record, indent=2, default=_json_safe), encoding="utf-8")
    print(f"Run recorded: {run_path}")
    return record


def main() -> None:
    record = asyncio.run(run())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()


__all__ = ["run"]
