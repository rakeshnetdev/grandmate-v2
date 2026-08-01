"""Chat orchestration (Phase 10; +long-term memory Phase 11).

Thin by design: thread bookkeeping (`chat_threads`, the identity/listing row) lives
here; the actual agent — intent routing, tool calling, the grounding guardrail, memory
extraction — lives in `orchestration/graphs/chat.py`. This service's job is wiring the
two together with the request-scoped resources the graph needs (the DB session, a fresh
checkpointer and store, a tool context and memory service bound to the caller's profile)
and nothing more.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.observability import get_tracing_context
from app.db.base import utc_now
from app.db.models import ChatThread, Persona
from app.domain.chat.queries import get_owned_thread, list_threads_for_profile
from app.domain.patterns import OpeningIndex
from app.integrations.llm.base import EmbeddingProvider, LLMProvider
from app.orchestration.checkpointer import open_checkpointer
from app.orchestration.dependencies import build_chat_graph_deps
from app.orchestration.graphs.chat import build_chat_graph
from app.orchestration.store import open_store

logger = structlog.get_logger(__name__)

# A thread with no title yet is titled from the first message it receives, truncated —
# a full question is often too long for a thread-list row.
_TITLE_MAX_LENGTH = 80


@dataclass(frozen=True)
class ChatTurnResult:
    thread: ChatThread
    answer: str
    citations: list[dict[str, Any]]
    grounded: bool


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        opening_index: OpeningIndex,
    ) -> None:
        self._session = session
        self._settings = settings
        self._llm = llm_provider
        self._embedding_provider = embedding_provider
        self._opening_index = opening_index

    async def create_thread(
        self, profile_id: uuid.UUID, *, active_game_id: uuid.UUID | None
    ) -> ChatThread:
        thread = ChatThread(profile_id=profile_id, active_game_id=active_game_id)
        self._session.add(thread)
        await self._session.flush()
        return thread

    async def list_threads(self, profile_id: uuid.UUID) -> list[ChatThread]:
        return await list_threads_for_profile(self._session, profile_id)

    async def send_message(
        self, profile_id: uuid.UUID, thread_id: uuid.UUID, persona: Persona, question: str
    ) -> ChatTurnResult | None:
        """`None` if `thread_id` does not exist or belongs to another profile — the
        route maps that to a 404, same as every other profile-scoped resource."""
        thread = await get_owned_thread(self._session, thread_id, profile_id)
        if thread is None:
            return None

        async with (
            open_checkpointer(self._settings.database) as checkpointer,
            open_store(self._settings.database) as store,
        ):
            if self._settings.agents.use_multi_agent:
                logger.info("routing_to_multi_agent_graph", use_multi_agent=True)
                from app.orchestration.dependencies import build_multi_agent_graph_deps
                from app.orchestration.graphs.multi_agent import build_multi_agent_graph

                multi_agent_deps = build_multi_agent_graph_deps(
                    settings=self._settings,
                    session=self._session,
                    llm=self._llm,
                    embedding_provider=self._embedding_provider,
                    opening_index=self._opening_index,
                    store=store,
                    profile_id=profile_id,
                )
                graph = build_multi_agent_graph(multi_agent_deps, checkpointer)
            else:
                logger.info("routing_to_single_agent_graph", use_multi_agent=False)
                single_agent_deps = build_chat_graph_deps(
                    settings=self._settings,
                    session=self._session,
                    llm=self._llm,
                    embedding_provider=self._embedding_provider,
                    opening_index=self._opening_index,
                    store=store,
                    profile_id=profile_id,
                )
                graph = build_chat_graph(single_agent_deps, checkpointer)
            with get_tracing_context(self._settings):
                result = await graph.ainvoke(
                    {
                        "question": question,
                        "profile_id": str(profile_id),
                        "thread_id": str(thread.id),
                        "active_game_id": (
                            str(thread.active_game_id) if thread.active_game_id else None
                        ),
                        "persona": persona.value,
                    },
                    config={"configurable": {"thread_id": str(thread.id)}},
                )

        if thread.title is None:
            thread.title = question[:_TITLE_MAX_LENGTH]
        # Bumped explicitly rather than relying on `TimestampMixin`'s `onupdate`: once a
        # thread already has a title, a later message may leave every other column on
        # this row unchanged, and SQLAlchemy only applies `onupdate` when the row is
        # actually included in an UPDATE — an untouched row emits none at all, which
        # would silently freeze "most recently active thread first" ordering after the
        # first message.
        thread.updated_at = utc_now()
        await self._session.flush()

        return ChatTurnResult(
            thread=thread,
            answer=result["answer"],
            citations=result.get("citations", []),
            grounded=bool(result["grounded"]),
        )

    async def get_history(
        self, profile_id: uuid.UUID, thread_id: uuid.UUID
    ) -> list[dict[str, Any]] | None:
        """The clean user/assistant transcript for a thread, or `None` if it does not
        exist or is not owned by `profile_id`. Reads the checkpointer's stored state
        directly rather than re-invoking the graph — a history fetch should never make an
        LLM call. Assistant entries carry their own `citations`/`grounded` (Phase 16a),
        persisted in the same dict by `orchestration/graphs/chat.py`'s `_run_agent`."""
        thread = await get_owned_thread(self._session, thread_id, profile_id)
        if thread is None:
            return None

        async with open_checkpointer(self._settings.database) as checkpointer:
            snapshot = await checkpointer.aget_tuple(
                {"configurable": {"thread_id": str(thread.id)}}
            )
        if snapshot is None:
            return []
        messages: list[dict[str, Any]] = snapshot.checkpoint["channel_values"].get("messages", [])
        return messages


__all__ = ["ChatService", "ChatTurnResult"]
