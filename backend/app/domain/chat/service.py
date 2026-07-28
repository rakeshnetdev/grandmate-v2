"""Chat orchestration (Phase 10).

Thin by design: thread bookkeeping (`chat_threads`, the identity/listing row) lives
here; the actual agent — intent routing, tool calling, the grounding guardrail — lives in
`orchestration/graphs/chat.py`. This service's job is wiring the two together with the
request-scoped resources the graph needs (the DB session, a fresh checkpointer, a tool
context bound to the caller's profile) and nothing more.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import ChatThread, Persona
from app.domain.chat.queries import get_owned_thread, list_threads_for_profile
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.patterns import OpeningIndex
from app.integrations.llm.base import EmbeddingProvider, LLMProvider
from app.orchestration.checkpointer import open_checkpointer
from app.orchestration.graphs.chat import ChatGraphDeps, build_chat_graph
from app.orchestration.tools import ToolContext

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

        deps = ChatGraphDeps(
            llm=self._llm,
            llm_settings=self._settings.llm,
            agent_settings=self._settings.agents,
            budget=LLMBudgetTracker(self._session, self._settings.llm),
            tool_context=ToolContext(
                session=self._session,
                profile_id=profile_id,
                settings=self._settings,
                embedding_provider=self._embedding_provider,
                opening_index=self._opening_index,
            ),
        )

        async with open_checkpointer(self._settings.database) as checkpointer:
            graph = build_chat_graph(deps, checkpointer)
            result = await graph.ainvoke(
                {
                    "question": question,
                    "profile_id": str(profile_id),
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
    ) -> list[dict[str, str]] | None:
        """The clean user/assistant transcript for a thread, or `None` if it does not
        exist or is not owned by `profile_id`. Reads the checkpointer's stored state
        directly rather than re-invoking the graph — a history fetch should never make an
        LLM call."""
        thread = await get_owned_thread(self._session, thread_id, profile_id)
        if thread is None:
            return None

        async with open_checkpointer(self._settings.database) as checkpointer:
            snapshot = await checkpointer.aget_tuple(
                {"configurable": {"thread_id": str(thread.id)}}
            )
        if snapshot is None:
            return []
        messages: list[dict[str, str]] = snapshot.checkpoint["channel_values"].get("messages", [])
        return messages


__all__ = ["ChatService", "ChatTurnResult"]
