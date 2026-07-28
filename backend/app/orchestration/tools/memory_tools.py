"""Long-term memory recall (Phase 11, ADR-0005, ADR-0008 §"agentic retrieval").

Retrieval, not a fixed context-injection step — consistent with every other capability
in this project (rule 12): the agent decides *whether* a question needs remembered
context, rather than every turn's prompt being padded with it regardless of relevance.
Reads the LangGraph store `MemoryService` writes to, never the audited Postgres mirror —
that table exists for the audit UI, not for the agent (see `orchestration/store.py`'s
docstring for the full write/read split).
"""

from __future__ import annotations

from typing import Any

from app.db.models import MemoryKind
from app.integrations.llm.base import ToolSpec
from app.orchestration.tools.context import ToolContext

RECALL_MEMORY = ToolSpec(
    name="recall_memory",
    description=(
        "Recall durable facts remembered about this player from past conversations: "
        "stated preferences, current goals, and confirmed recurring patterns in their "
        "play. Use this when a question depends on knowing the player, not just the "
        "current game or corpus."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
)


async def recall_memory(ctx: ToolContext) -> dict[str, Any]:
    if ctx.store is None:
        return {"memories": []}

    memories: list[dict[str, Any]] = []
    for kind in MemoryKind:
        items = await ctx.store.asearch((str(ctx.profile_id), kind.value))
        memories.extend({"kind": kind.value, **item.value} for item in items)
    return {"memories": memories}


__all__ = ["RECALL_MEMORY", "recall_memory"]
