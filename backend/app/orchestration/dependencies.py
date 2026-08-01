"""Shared graph dependency construction (ADR-0017, Rule 13)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from langgraph.store.base import BaseStore
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.memory import MemoryService
from app.domain.patterns import OpeningIndex
from app.integrations.llm.base import EmbeddingProvider, LLMProvider
from app.orchestration.tools import ToolContext

if TYPE_CHECKING:
    from app.orchestration.graphs.chat import ChatGraphDeps
    from app.orchestration.graphs.multi_agent import MultiAgentGraphDeps


def build_chat_graph_deps(
    settings: Settings,
    session: AsyncSession,
    llm: LLMProvider,
    embedding_provider: EmbeddingProvider,
    opening_index: OpeningIndex,
    store: BaseStore,
    profile_id: uuid.UUID,
) -> ChatGraphDeps:
    """Shared wiring path for ChatGraph dependencies (ADR-0017, Rule 13)."""
    from app.orchestration.graphs.chat import ChatGraphDeps

    return ChatGraphDeps(
        llm=llm,
        llm_settings=settings.llm,
        agent_settings=settings.agents,
        budget=LLMBudgetTracker(session, settings.llm),
        tool_context=ToolContext(
            session=session,
            profile_id=profile_id,
            settings=settings,
            embedding_provider=embedding_provider,
            opening_index=opening_index,
            store=store,
        ),
        memory=MemoryService(session, store, settings.memory),
    )


def build_multi_agent_graph_deps(
    settings: Settings,
    session: AsyncSession,
    llm: LLMProvider,
    embedding_provider: EmbeddingProvider,
    opening_index: OpeningIndex,
    store: BaseStore,
    profile_id: uuid.UUID,
) -> MultiAgentGraphDeps:
    """Shared wiring path for MultiAgentGraph dependencies (ADR-0017, Rule 13)."""
    from app.orchestration.graphs.multi_agent import MultiAgentGraphDeps

    return MultiAgentGraphDeps(
        llm=llm,
        llm_settings=settings.llm,
        multi_agent_settings=settings.multi_agent,
        budget=LLMBudgetTracker(session, settings.llm),
        tool_context=ToolContext(
            session=session,
            profile_id=profile_id,
            settings=settings,
            embedding_provider=embedding_provider,
            opening_index=opening_index,
            store=store,
        ),
    )


__all__ = ["build_chat_graph_deps", "build_multi_agent_graph_deps"]
