"""Zero-argument graph factories for LangGraph Studio (ADR-0017)."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from app.core.config import get_settings
from app.domain.patterns import load_opening_index
from app.integrations.llm import build_embedding_provider, build_llm_provider
from app.orchestration.dependencies import build_chat_graph_deps, build_multi_agent_graph_deps
from app.orchestration.graphs.chat import build_chat_graph
from app.orchestration.graphs.multi_agent import build_multi_agent_graph


def make_chat_graph() -> Any:
    """Factory to build and compile the Chat Graph for LangGraph Studio."""
    settings = get_settings()

    # Mock DB session for compilation safety; InMemoryStore for state store
    session = MagicMock(spec=AsyncSession)
    store = InMemoryStore()

    llm = build_llm_provider(settings.llm)
    embedding_provider = build_embedding_provider(settings.llm, settings.retrieval)

    try:
        opening_index = load_opening_index(settings.patterns)
    except Exception:
        opening_index = MagicMock()

    profile_id = uuid.uuid4()

    deps = build_chat_graph_deps(
        settings=settings,
        session=session,
        llm=llm,
        embedding_provider=embedding_provider,
        opening_index=opening_index,
        store=store,
        profile_id=profile_id,
    )

    checkpointer = MemorySaver()
    return build_chat_graph(deps, checkpointer)


def make_multi_agent_graph() -> Any:
    """Factory to build and compile the Multi-Agent Graph for LangGraph Studio."""
    settings = get_settings()

    session = MagicMock(spec=AsyncSession)
    store = InMemoryStore()

    llm = build_llm_provider(settings.llm)
    embedding_provider = build_embedding_provider(settings.llm, settings.retrieval)

    try:
        opening_index = load_opening_index(settings.patterns)
    except Exception:
        opening_index = MagicMock()

    profile_id = uuid.uuid4()

    deps = build_multi_agent_graph_deps(
        settings=settings,
        session=session,
        llm=llm,
        embedding_provider=embedding_provider,
        opening_index=opening_index,
        store=store,
        profile_id=profile_id,
    )

    checkpointer = MemorySaver()
    return build_multi_agent_graph(deps, checkpointer)


__all__ = ["make_chat_graph", "make_multi_agent_graph"]
