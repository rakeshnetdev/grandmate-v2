"""The multi-agent supervisor graph: routing, the specialist handoff contract, the
coach/critic retry-then-fallback cycle, and the shared cross-turn cost ceilings
(Phase 13).

Same testing posture as `test_chat_graph.py`: `FakeLLMProvider` scripts every response,
no real network call, an in-memory checkpointer. The concern here is the graph's own
control flow — which specialists ran, in what order, and what reached the coach — not
whether a real model produces good routing decisions (that is
`evals/harness/agent_trajectory_eval.py`'s job).
"""

from __future__ import annotations

import json
import uuid

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MultiAgentSettings, Settings
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.patterns import OpeningIndex
from app.integrations.llm import build_embedding_provider
from app.integrations.llm.base import ToolCall
from app.orchestration.graphs.multi_agent import MultiAgentGraphDeps, build_multi_agent_graph
from app.orchestration.tools import ToolContext
from tests.fake_llm import FakeLLMProvider

pytestmark = pytest.mark.asyncio


def _deps(
    settings: Settings,
    session: AsyncSession,
    llm: FakeLLMProvider,
    *,
    multi_agent_settings: MultiAgentSettings | None = None,
) -> MultiAgentGraphDeps:
    return MultiAgentGraphDeps(
        llm=llm,
        llm_settings=settings.llm,
        multi_agent_settings=multi_agent_settings or settings.multi_agent,
        budget=LLMBudgetTracker(session, settings.llm),
        tool_context=ToolContext(
            session=session,
            profile_id=uuid.uuid4(),
            settings=settings,
            embedding_provider=build_embedding_provider(settings.llm, settings.retrieval),
            opening_index=OpeningIndex({}),
        ),
    )


async def test_supervisor_routes_to_neither_specialist_when_none_is_needed(
    settings: Settings, db_session: AsyncSession
) -> None:
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": false, "needs_analysis": false}',
            '{"answer": "Hi there!", "citations": []}',
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "hello!", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["trace"] == ["supervisor", "coach", "critic", "write_memory"]
    assert result["answer"] == "Hi there!"
    assert result["grounded"] is True
    assert result["retrieval_context"] == []
    assert result["analysis_context"] == []


async def test_supervisor_routes_to_retriever_only(
    settings: Settings, db_session: AsyncSession
) -> None:
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": true, "needs_analysis": false}',
            '{"done": true}',
            '{"answer": "General fact.", "citations": []}',
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "what is a fork?", "persona": "coach"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["trace"] == ["supervisor", "retriever", "coach", "critic", "write_memory"]
    assert result["analysis_context"] == []


async def test_supervisor_routes_to_chess_analyst_only_and_dispatches_its_tool(
    settings: Settings, db_session: AsyncSession
) -> None:
    """`lookup_opening` needs no seeded game to answer meaningfully against an empty
    index — same reason `test_chat_graph.py` picks it for its own tool-dispatch test."""
    tool_call = ToolCall(id="call-1", name="lookup_opening", arguments=json.dumps({"epd": "x"}))
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": false, "needs_analysis": true}',
            [tool_call],
            '{"done": true}',
            '{"answer": "It\'s not a known opening.", "citations": []}',
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "what opening is this?", "persona": "coach"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["trace"] == ["supervisor", "chess_analyst", "coach", "critic", "write_memory"]
    assert result["retrieval_context"] == []
    assert result["analysis_context"] == [
        {
            "tool": "lookup_opening",
            "arguments": json.dumps({"epd": "x"}),
            "result": {"result": None},
        }
    ]


async def test_supervisor_routes_to_both_specialists_in_order(
    settings: Settings, db_session: AsyncSession
) -> None:
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": true, "needs_analysis": true}',
            '{"done": true}',
            '{"done": true}',
            '{"answer": "ok", "citations": []}',
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "how did my opening theory hold up?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    # Order matters: retriever always precedes chess_analyst when both are needed —
    # the handoff contract the coach depends on to read gathered context in one place.
    assert result["trace"] == [
        "supervisor",
        "retriever",
        "chess_analyst",
        "coach",
        "critic",
        "write_memory",
    ]


async def test_an_ungrounded_draft_is_retried_once_then_falls_back(
    settings: Settings, db_session: AsyncSession
) -> None:
    """Mirrors `test_chat_graph.py`'s identical single-agent test — the critic here is
    the same `validate_answer` call, just reached through a different graph."""
    bad_citation = json.dumps(
        {
            "answer": "Bad answer.",
            "citations": [{"kind": "move", "game_id": str(uuid.uuid4()), "ply": 4, "san": "Nf3"}],
        }
    )
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": false, "needs_analysis": false}',
            bad_citation,
            bad_citation,
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "why was Nf3 good?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert llm.responses == []
    assert result["trace"] == [
        "supervisor",
        "coach",
        "critic",
        "coach",
        "critic",
        "write_memory",
    ]
    assert result["grounded"] is True
    assert result["answer"] != "Bad answer."
    assert result["citations"] == []


async def test_a_zero_step_ceiling_short_circuits_to_fallback_with_no_llm_call(
    settings: Settings, db_session: AsyncSession
) -> None:
    """The cost ceiling is checked *before* any node's LLM call, not after — with the
    ceiling already at zero, the graph must reach a grounded fallback answer having made
    no completion call at all. `FakeLLMProvider` with an empty response queue raises if
    anything tries to call it, so this also proves no call was attempted."""
    llm = FakeLLMProvider(responses=[])
    tiny_ceiling = MultiAgentSettings(
        multi_agent_max_steps=0, multi_agent_max_tool_calls=20, multi_agent_token_budget=60_000
    )
    graph = build_multi_agent_graph(
        _deps(settings, db_session, llm, multi_agent_settings=tiny_ceiling), MemorySaver()
    )

    result = await graph.ainvoke(
        {"question": "anything", "persona": "coach"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["trace"] == ["supervisor", "coach", "write_memory"]
    assert result["grounded"] is True
    assert llm.calls == []


async def test_a_spent_token_budget_stops_further_spend_mid_turn(
    settings: Settings, db_session: AsyncSession
) -> None:
    """A budget that only the supervisor's own call can afford — every node after it
    must see the ceiling already exceeded and skip its own LLM call, proving the ceiling
    is a shared, running total rather than a per-node allowance."""
    llm = FakeLLMProvider(
        responses=['{"needs_retrieval": true, "needs_analysis": false}'],
        prompt_tokens_per_call=10,
        completion_tokens_per_call=10,
    )
    tight_budget = MultiAgentSettings(
        multi_agent_max_steps=20, multi_agent_max_tool_calls=20, multi_agent_token_budget=5
    )
    graph = build_multi_agent_graph(
        _deps(settings, db_session, llm, multi_agent_settings=tight_budget), MemorySaver()
    )

    result = await graph.ainvoke(
        {"question": "what should I study next?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert len(llm.calls) == 1
    assert result["trace"] == ["supervisor", "retriever", "coach", "write_memory"]
    assert result["grounded"] is True


# --- Handoff-integrity regressions (the four defects that sank the Phase 13 comparison).
# Each of these fails on the pre-fix graph, and each maps to a measured symptom in
# `evals/runs/20260729T012314Z_agent_trajectory.json`.


async def test_the_chess_analyst_is_told_the_open_game_id(
    settings: Settings, db_session: AsyncSession
) -> None:
    """`get_game_analysis` and `list_critical_moments` both take a **required** `game_id`.
    The analyst's prompt used to carry none, so it had no id to pass and no way to get
    one — and answered questions about the user's own game with zero tool calls
    (`ag-my-opening`, `ag-critical-moment`: multi-agent tool_call_count 0 against the
    single agent's 1, relevancy 0.00 against 0.82/0.72)."""
    game_id = str(uuid.uuid4())
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": false, "needs_analysis": true}',
            '{"done": true}',
            '{"answer": "Your opening.", "citations": []}',
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    await graph.ainvoke(
        {
            "question": "what was my opening in this game?",
            "active_game_id": game_id,
            "persona": "self_learner",
        },
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    analyst_call = llm.calls[1]
    assert game_id in analyst_call.messages[0].content


async def test_a_general_chat_turn_reaches_the_coach_labelled_as_such(
    settings: Settings, db_session: AsyncSession
) -> None:
    """ "How does this coaching assistant work?" used to be routed to the retriever — the
    supervisor's `needs_retrieval` covers "coaching concepts", and a question about the
    coach reads straight into that. The retriever found nothing, the coach got an empty
    context indistinguishable from a failed search, and hedged.

    Two things are asserted together because either alone would pass while the feature is
    broken: the specialists are skipped, *and* the coach is told why they were.
    """
    llm = FakeLLMProvider(
        responses=[
            '{"is_general_chat": true, "needs_retrieval": true, "needs_analysis": false}',
            '{"answer": "I analyse your games and explain them.", "citations": []}',
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "how does this coaching assistant work?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["trace"] == ["supervisor", "coach", "critic", "write_memory"]
    coach_system_message = llm.calls[1].messages[0].content
    assert "This turn is not a chess question" in coach_system_message


async def test_a_budget_exhausted_turn_is_not_labelled_general_chat(
    settings: Settings, db_session: AsyncSession
) -> None:
    """The supervisor also skips the specialists when it cannot afford to classify. That
    reaches the coach as the same empty context, but for the opposite reason: the question
    may well have been a chess question that simply never got gathered for, so the coach
    must still say it has nothing rather than answer breezily."""
    # No scripted responses: `FakeLLMProvider` raises if asked for one, so this also
    # re-asserts that an exhausted ceiling makes zero LLM calls.
    llm = FakeLLMProvider(responses=[])
    graph = build_multi_agent_graph(
        _deps(
            settings,
            db_session,
            llm,
            multi_agent_settings=settings.multi_agent.model_copy(
                update={"multi_agent_max_steps": 0}
            ),
        ),
        MemorySaver(),
    )

    result = await graph.ainvoke(
        {"question": "why was move 12 bad?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["is_general_chat"] is False


async def test_specialists_receive_the_thread_history(
    settings: Settings, db_session: AsyncSession
) -> None:
    """A follow-up ("and why was that bad?") is unresolvable from the latest message
    alone. The single agent has always been given history; the specialists were not."""
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": true, "needs_analysis": false}',
            '{"done": true}',
            '{"answer": "Because it hangs a pawn.", "citations": []}',
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    await graph.ainvoke(
        {
            "question": "and why was that bad?",
            "persona": "self_learner",
            "messages": [
                {"role": "user", "content": "what was my worst move?"},
                {"role": "assistant", "content": "Move 12, Nxe4."},
            ],
        },
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    retriever_contents = [m.content for m in llm.calls[1].messages]
    assert "Move 12, Nxe4." in retriever_contents


async def test_the_coach_retry_still_contains_the_question(
    settings: Settings, db_session: AsyncSession
) -> None:
    """The retry used to *replace* the question with the violation feedback, so the
    second attempt had nothing to answer and hedged — a zero-citation hedge that then
    passed the critic trivially. `ag-fork-vs-pin` and `ag-pawn-structure` both produced
    exactly that ("I currently do not have sufficient information to provide a corrected
    response"), and both traced supervisor>coach>critic>coach>critic."""
    question = "why was Nf3 good?"
    bad_citation = json.dumps(
        {
            "answer": "Bad answer.",
            "citations": [{"kind": "move", "game_id": str(uuid.uuid4()), "ply": 4, "san": "Nf3"}],
        }
    )
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": false, "needs_analysis": false}',
            bad_citation,
            '{"answer": "Nf3 develops toward the centre.", "citations": []}',
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    await graph.ainvoke(
        {"question": question, "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    retry_contents = [m.content for m in llm.calls[2].messages]
    assert question in retry_contents, "the retry dropped the question"
    # The rejected draft is replayed so the correction has something to correct.
    assert bad_citation in retry_contents
    assert any("failed grounding checks" in (c or "") for c in retry_contents)


async def test_write_memory_runs_after_the_answer_is_final(
    settings: Settings, db_session: AsyncSession
) -> None:
    """`USE_MULTI_AGENT=true` used to silently disable the write half of Phase 11: this
    graph had no extraction node at all. With no `MemoryService` wired the node still
    runs and still no-ops, which is what every other test in this module relies on."""
    llm = FakeLLMProvider(
        responses=[
            '{"needs_retrieval": false, "needs_analysis": false}',
            '{"answer": "Hi there!", "citations": []}',
        ]
    )
    deps = _deps(settings, db_session, llm)
    assert deps.memory is None
    graph = build_multi_agent_graph(deps, MemorySaver())

    result = await graph.ainvoke(
        {"question": "hello!", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["trace"][-1] == "write_memory"
    # No MemoryService, so extraction is skipped entirely rather than costing a call.
    assert len(llm.calls) == 2
    assert result["answer"] == "Hi there!"
