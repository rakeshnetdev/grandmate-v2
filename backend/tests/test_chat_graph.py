"""The chat graph: intent routing, the tool-calling loop, the grounding guardrail's
retry-then-fallback path, and thread continuity via the checkpointer (Phase 10).

Every test uses `FakeLLMProvider` (no real network call) and an in-memory
`MemorySaver` checkpointer — `AsyncPostgresSaver` itself is exercised indirectly through
the chat routes/service tests, which is where "is it actually Postgres-backed" matters;
here the concern is the graph's own control flow, which is identical regardless of which
checkpointer backs it.
"""

from __future__ import annotations

import json
import uuid

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.patterns import OpeningIndex
from app.integrations.llm import build_embedding_provider
from app.integrations.llm.base import ToolCall
from app.orchestration.graphs.chat import ChatGraphDeps, build_chat_graph
from app.orchestration.tools import ToolContext
from tests.fake_llm import FakeLLMProvider

pytestmark = pytest.mark.asyncio


def _deps(settings: Settings, session: AsyncSession, llm: FakeLLMProvider) -> ChatGraphDeps:
    return ChatGraphDeps(
        llm=llm,
        llm_settings=settings.llm,
        agent_settings=settings.agents,
        budget=LLMBudgetTracker(session, settings.llm),
        tool_context=ToolContext(
            session=session,
            profile_id=uuid.uuid4(),
            settings=settings,
            embedding_provider=build_embedding_provider(settings.llm, settings.retrieval),
            opening_index=OpeningIndex({}),
        ),
    )


async def test_a_direct_answer_skips_tool_calling(
    settings: Settings, db_session: AsyncSession
) -> None:
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            '{"answer": "Direct answer.", "citations": []}',
        ]
    )
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "what is a fork?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["answer"] == "Direct answer."
    assert result["grounded"] is True
    assert result["trace"] == ["classify_intent", "run_agent"]
    assert result["messages"][-2:] == [
        {"role": "user", "content": "what is a fork?"},
        {"role": "assistant", "content": "Direct answer."},
    ]


async def test_a_tool_call_is_dispatched_and_fed_back(
    settings: Settings, db_session: AsyncSession
) -> None:
    """`lookup_opening` needs no DB row to answer meaningfully against an empty index —
    `{"result": None}` is itself proof the tool ran and its result reached the model."""
    tool_call = ToolCall(id="call-1", name="lookup_opening", arguments=json.dumps({"epd": "x"}))
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            [tool_call],
            '{"answer": "It is not a known opening.", "citations": []}',
        ]
    )
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "what opening is this?", "persona": "coach"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["grounded"] is True
    assert result["context"] == [
        {
            "tool": "lookup_opening",
            "arguments": json.dumps({"epd": "x"}),
            "result": {"result": None},
        }
    ]
    # The tool result was fed back to the model as a "tool" message before its next call.
    final_call_messages = llm.calls[-1].messages
    tool_messages = [m for m in final_call_messages if m.role == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0].content is not None
    assert json.loads(tool_messages[0].content) == {"result": None}


async def test_an_unknown_tool_call_becomes_an_error_result_not_a_crash(
    settings: Settings, db_session: AsyncSession
) -> None:
    tool_call = ToolCall(id="call-1", name="not_a_real_tool", arguments="{}")
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            [tool_call],
            '{"answer": "ok", "citations": []}',
        ]
    )
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "q", "persona": "coach"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["context"][0]["result"] == {"error": "unknown tool 'not_a_real_tool'"}


async def test_a_stray_profile_id_argument_is_rejected_not_accepted(
    settings: Settings, db_session: AsyncSession
) -> None:
    """Rule 14: a tool's JSON schema never offers `profile_id`, and every implementation
    reads it from the bound `ToolContext` instead — so a model that tries to smuggle one
    in as an extra argument hits a `TypeError`, not a cross-profile read."""
    tool_call = ToolCall(
        id="call-1",
        name="lookup_opening",
        arguments=json.dumps({"epd": "x", "profile_id": str(uuid.uuid4())}),
    )
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            [tool_call],
            '{"answer": "ok", "citations": []}',
        ]
    )
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "q", "persona": "coach"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert "invalid arguments" in result["context"][0]["result"]["error"]


async def test_an_ungrounded_answer_is_retried_once_then_falls_back(
    settings: Settings, db_session: AsyncSession
) -> None:
    """A citation referencing a game that does not exist can never validate — proves the
    retry-then-fallback path without needing a seeded game."""
    bad_citation = json.dumps(
        {
            "answer": "Bad answer.",
            "citations": [{"kind": "move", "game_id": str(uuid.uuid4()), "ply": 4, "san": "Nf3"}],
        }
    )
    llm = FakeLLMProvider(responses=['{"intent": "explain"}', bad_citation, bad_citation])
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "why was Nf3 good?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    # Exactly two answer attempts were made (both scripted responses consumed) before
    # falling back — not zero, not a third.
    assert llm.responses == []
    assert result["grounded"] is True
    assert result["answer"] != "Bad answer."
    assert result["citations"] == []


async def test_thread_continuity_carries_prior_turns_into_the_next_llm_call(
    settings: Settings, db_session: AsyncSession
) -> None:
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            '{"answer": "First answer.", "citations": []}',
            '{"intent": "explain"}',
            '{"answer": "Second answer.", "citations": []}',
        ]
    )
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())
    thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    await graph.ainvoke({"question": "first question", "persona": "coach"}, config=thread_config)
    result = await graph.ainvoke(
        {"question": "second question", "persona": "coach"}, config=thread_config
    )

    assert result["messages"] == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "First answer."},
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": "Second answer."},
    ]
    # The second turn's agent call carried the first turn's exchange as context.
    second_agent_call_messages = llm.calls[-1].messages
    contents = [m.content for m in second_agent_call_messages]
    assert "first question" in contents
    assert "First answer." in contents


async def test_a_different_thread_id_starts_with_no_history(
    settings: Settings, db_session: AsyncSession
) -> None:
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            '{"answer": "First answer.", "citations": []}',
            '{"intent": "explain"}',
            '{"answer": "Second answer.", "citations": []}',
        ]
    )
    checkpointer = MemorySaver()
    deps = _deps(settings, db_session, llm)

    await build_chat_graph(deps, checkpointer).ainvoke(
        {"question": "q1", "persona": "coach"},
        config={"configurable": {"thread_id": "thread-a"}},
    )
    result = await build_chat_graph(deps, checkpointer).ainvoke(
        {"question": "q2", "persona": "coach"},
        config={"configurable": {"thread_id": "thread-b"}},
    )

    assert result["messages"] == [
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "Second answer."},
    ]
