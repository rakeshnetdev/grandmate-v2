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
from langgraph.store.memory import InMemoryStore
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import (
    ChatThread,
    KnowledgeBucket,
    KnowledgeChunk,
    KnowledgeDocument,
    Profile,
    ProfileKind,
    User,
)
from app.db.models.knowledge import EMBEDDING_DIMENSIONS
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.memory import MemoryService
from app.domain.patterns import OpeningIndex
from app.integrations.llm import build_embedding_provider
from app.integrations.llm.base import ToolCall
from app.orchestration.graphs.chat import ChatGraphDeps, build_chat_graph
from app.orchestration.tools import TOOL_DISPATCH, ToolContext
from tests.fake_llm import FakeLLMProvider

pytestmark = pytest.mark.asyncio

# Every completed turn runs a `write_memory` extraction call after its answer — this is
# the "nothing durable was said" response most tests script for it, since memory
# extraction itself is `test_memory_extraction.py`'s concern, not this file's.
_NO_MEMORIES = '{"memories": []}'


async def _make_profile(session: AsyncSession) -> Profile:
    """Only needed by tests that actually assert on a written `LongTermMemory` row —
    that table has a real foreign key to `profiles`, unlike every other tool this file
    exercises, so a bare `uuid.uuid4()` (what `_deps` uses by default) is not enough."""
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


def _deps(
    settings: Settings,
    session: AsyncSession,
    llm: FakeLLMProvider,
    *,
    profile_id: uuid.UUID | None = None,
) -> ChatGraphDeps:
    store = InMemoryStore()
    return ChatGraphDeps(
        llm=llm,
        llm_settings=settings.llm,
        agent_settings=settings.agents,
        budget=LLMBudgetTracker(session, settings.llm),
        tool_context=ToolContext(
            session=session,
            profile_id=profile_id or uuid.uuid4(),
            settings=settings,
            embedding_provider=build_embedding_provider(settings.llm, settings.retrieval),
            opening_index=OpeningIndex({}),
            store=store,
        ),
        memory=MemoryService(session, store, settings.memory),
    )


async def test_a_direct_answer_skips_tool_calling(
    settings: Settings, db_session: AsyncSession
) -> None:
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            '{"answer": "Direct answer.", "citations": []}',
            _NO_MEMORIES,
        ]
    )
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "what is a fork?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["answer"] == "Direct answer."
    assert result["grounded"] is True
    assert result["trace"] == ["classify_intent", "run_agent", "write_memory"]
    assert result["messages"][-2:] == [
        {"role": "user", "content": "what is a fork?"},
        {"role": "assistant", "content": "Direct answer.", "citations": [], "grounded": True},
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
            _NO_MEMORIES,
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
    # llm.calls[-1] is the trailing write_memory extraction call, not run_agent's.
    final_call_messages = llm.calls[-2].messages
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
            _NO_MEMORIES,
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
            _NO_MEMORIES,
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
    llm = FakeLLMProvider(
        responses=['{"intent": "explain"}', bad_citation, bad_citation, _NO_MEMORIES]
    )
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "why was Nf3 good?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    # Exactly two answer attempts were made (both scripted responses consumed) before
    # falling back to a deterministic answer, followed by one memory-extraction call —
    # not zero, not a third answer attempt.
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
            _NO_MEMORIES,
            '{"intent": "explain"}',
            '{"answer": "Second answer.", "citations": []}',
            _NO_MEMORIES,
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
        {"role": "assistant", "content": "First answer.", "citations": [], "grounded": True},
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": "Second answer.", "citations": [], "grounded": True},
    ]
    # The second turn's agent call (not its trailing write_memory call) carried the
    # first turn's exchange as context.
    second_agent_call_messages = llm.calls[-2].messages
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
            _NO_MEMORIES,
            '{"intent": "explain"}',
            '{"answer": "Second answer.", "citations": []}',
            _NO_MEMORIES,
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
        {"role": "assistant", "content": "Second answer.", "citations": [], "grounded": True},
    ]


async def test_write_memory_persists_a_qualifying_candidate_after_the_answer(
    settings: Settings, db_session: AsyncSession
) -> None:
    """End-to-end through the real graph, not just `MemoryService` in isolation
    (`test_memory_service.py`'s job) — proves `write_memory` is actually wired into the
    graph and actually calls it."""
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            '{"answer": "Sure, I will keep it brief.", "citations": []}',
            '{"memories": [{"kind": "preference", "content": "Prefers short answers", '
            '"confidence": 0.9}]}',
        ]
    )
    profile = await _make_profile(db_session)
    deps = _deps(settings, db_session, llm, profile_id=profile.id)
    thread = ChatThread(profile_id=profile.id)
    db_session.add(thread)
    await db_session.flush()

    result = await build_chat_graph(deps, MemorySaver()).ainvoke(
        {"question": "Please keep answers short.", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(thread.id)}},
    )

    assert result["trace"][-1] == "write_memory"
    written = await deps.memory.list_memories(deps.tool_context.profile_id)
    assert [m.content for m in written] == ["Prefers short answers"]
    assert written[0].source_thread_id == thread.id


async def test_write_memory_drops_a_candidate_below_the_confidence_floor(
    settings: Settings, db_session: AsyncSession
) -> None:
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            '{"answer": "Noted.", "citations": []}',
            '{"memories": [{"kind": "goal", "content": "maybe endgames", "confidence": 0.2}]}',
        ]
    )
    deps = _deps(settings, db_session, llm)

    await build_chat_graph(deps, MemorySaver()).ainvoke(
        {"question": "I guess I could look at endgames sometime?", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    written = await deps.memory.list_memories(deps.tool_context.profile_id)
    assert written == []


async def _seed_corpus_chunk(session: AsyncSession) -> KnowledgeChunk:
    document = KnowledgeDocument(
        bucket=KnowledgeBucket.OPENINGS,
        title="The French Defence",
        source="Wikipedia",
        source_url="https://en.wikipedia.org/wiki/French_Defence",
        licence="CC BY-SA 4.0",
        retrieved_at=utc_now(),
        content_hash=str(uuid.uuid4()),
    )
    session.add(document)
    await session.flush()
    chunk = KnowledgeChunk(
        document_id=document.id,
        bucket=KnowledgeBucket.OPENINGS,
        chunk_index=0,
        content="The French Defence begins 1.e4 e6.",
        token_count=9,
        chunk_metadata={},
        embedding=[0.0] * EMBEDDING_DIMENSIONS,
    )
    session.add(chunk)
    await session.flush()
    return chunk


async def test_a_general_knowledge_question_is_answered_while_a_game_is_open(
    settings: Settings, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 20's whole point, reproducing the reported failure.

    Asking "explain the French Defence" with an unrelated game open used to be
    unanswerable: the model had to cite the chess facts it stated, every citation kind
    demanded a game_id, so it cited the open game — whose opening was a different one —
    and the guardrail correctly rejected it. Two attempts later the turn degraded to the
    fallback, and the user got nothing.

    Now the retrieved chunk is itself citable, so the first attempt validates.
    """
    chunk = await _seed_corpus_chunk(db_session)

    async def _fake_search(ctx, *, bucket: str, query: str):  # type: ignore[no-untyped-def]
        return {
            "results": [
                {
                    "chunk_id": str(chunk.id),
                    "content": chunk.content,
                    "score": 0.9,
                    "retrieved_by": "dense",
                    "metadata": {},
                }
            ]
        }

    # Stubbed so the test exercises the graph and guardrail, not pgvector/embeddings —
    # retrieval itself is `test_retrieval_*`'s concern.
    monkeypatch.setitem(TOOL_DISPATCH, "search_knowledge", _fake_search)

    answer = json.dumps(
        {
            "answer": "The French Defence begins 1.e4 e6.",
            "citations": [{"kind": "knowledge", "chunk_id": str(chunk.id)}],
        }
    )
    llm = FakeLLMProvider(
        responses=[
            '{"intent": "explain"}',
            [
                ToolCall(
                    id="c1",
                    name="search_knowledge",
                    arguments='{"bucket": "openings", "query": "French Defence"}',
                )
            ],
            answer,
            _NO_MEMORIES,
        ]
    )
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {
            "question": "explain the French Defence",
            "persona": "self_learner",
            # An unrelated game is open — the condition that used to break this.
            "active_game_id": str(uuid.uuid4()),
        },
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    # Answered on the first attempt: no retry was scripted, and none was needed.
    assert llm.responses == []
    assert result["answer"] == "The French Defence begins 1.e4 e6."
    assert result["grounded"] is True
    assert result["citations"][0]["kind"] == "knowledge"
    # Enriched server-side from the document record, never model-written.
    assert result["citations"][0]["title"] == "The French Defence"


async def test_a_knowledge_citation_for_a_chunk_never_retrieved_is_rejected(
    settings: Settings, db_session: AsyncSession
) -> None:
    """The model cannot cite corpus material it did not actually receive this turn, even
    if that chunk really exists."""
    chunk = await _seed_corpus_chunk(db_session)
    fabricated = json.dumps(
        {
            "answer": "The French Defence begins 1.e4 e6.",
            "citations": [{"kind": "knowledge", "chunk_id": str(chunk.id)}],
        }
    )
    llm = FakeLLMProvider(responses=['{"intent": "explain"}', fabricated, fabricated, _NO_MEMORIES])
    graph = build_chat_graph(_deps(settings, db_session, llm), MemorySaver())

    result = await graph.ainvoke(
        {"question": "explain the French Defence", "persona": "self_learner"},
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert result["answer"] != "The French Defence begins 1.e4 e6."
    assert result["citations"] == []
