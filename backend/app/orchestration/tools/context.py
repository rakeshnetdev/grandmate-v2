"""Per-turn context every chat tool runs with (Phase 10, +store at Phase 11).

`profile_id` is bound here, not accepted as a tool argument anywhere in this package —
the same isolation shape `AnalysisRetriever.search` already established at Phase 7
(`claude.md` rule 14): a tool's JSON schema, the contract the model actually sees, never
offers a `profile_id` parameter, so there is no way for the model to ask for another
profile's data even by mistake.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from langgraph.store.base import BaseStore
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.patterns import OpeningIndex
from app.integrations.llm.base import EmbeddingProvider


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool implementation needs, bound once per chat turn."""

    session: AsyncSession
    profile_id: uuid.UUID
    settings: Settings
    embedding_provider: EmbeddingProvider
    opening_index: OpeningIndex
    # Phase 11: the long-term memory store, read by `recall_memory`. Optional so every
    # existing Phase 10 tool test that builds a `ToolContext` without memory in scope
    # keeps working unchanged — a tool that never touches memory has no reason to
    # require it.
    store: BaseStore | None = None


__all__ = ["ToolContext"]
