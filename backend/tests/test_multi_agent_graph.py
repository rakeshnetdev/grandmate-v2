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

    assert result["trace"] == ["supervisor", "coach", "critic"]
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

    assert result["trace"] == ["supervisor", "retriever", "coach", "critic"]
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
            "{\"answer\": \"It's not a known opening.\", \"citations\": []}",
        ]
    )
    graph = build_multi_agent_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "what opening is this?", "persona": "coach"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["trace"] == ["supervisor", "chess_analyst", "coach", "critic"]
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
    assert result["trace"] == ["supervisor", "retriever", "chess_analyst", "coach", "critic"]


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
    assert result["trace"] == ["supervisor", "coach", "critic", "coach", "critic"]
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

    assert result["trace"] == ["supervisor", "coach"]
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
    assert result["trace"] == ["supervisor", "retriever", "coach"]
    assert result["grounded"] is True
