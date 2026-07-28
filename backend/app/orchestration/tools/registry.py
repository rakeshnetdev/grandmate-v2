"""The tool registry: what the chat agent may call, and how a call dispatches
(Phase 10, ADR-0010).

One list of `ToolSpec`s to hand the LLM provider, one name-keyed dispatch table to
resolve a model's tool call back to an implementation. Phase 12's MCP server is expected
to import `TOOL_DISPATCH` directly rather than growing its own — that is the entire point
of `claude.md` rule 13.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.integrations.llm.base import ToolSpec
from app.orchestration.tools.analysis_tools import (
    GET_GAME_ANALYSIS,
    GET_PROFILE_AGGREGATE,
    LIST_CRITICAL_MOMENTS,
    LOOKUP_OPENING,
    get_game_analysis,
    get_profile_aggregate,
    list_critical_moments,
    lookup_opening,
)
from app.orchestration.tools.context import ToolContext
from app.orchestration.tools.knowledge_tools import (
    SEARCH_ANALYSIS,
    SEARCH_KNOWLEDGE,
    search_analysis,
    search_knowledge,
)
from app.orchestration.tools.memory_tools import RECALL_MEMORY, recall_memory
from app.orchestration.tools.validation_tools import VALIDATE_LINE, validate_line

ToolFn = Callable[..., Awaitable[dict[str, Any]]]


async def _call_validate_line(_ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    """Adapter only: `validate_line` itself is a pure function needing no per-turn
    context, but every entry in `TOOL_DISPATCH` shares one calling convention so the
    agent loop does not need to special-case it."""
    return validate_line(**kwargs)


TOOL_SPECS: list[ToolSpec] = [
    SEARCH_KNOWLEDGE,
    SEARCH_ANALYSIS,
    GET_GAME_ANALYSIS,
    LIST_CRITICAL_MOMENTS,
    GET_PROFILE_AGGREGATE,
    LOOKUP_OPENING,
    VALIDATE_LINE,
    RECALL_MEMORY,
]

TOOL_DISPATCH: dict[str, ToolFn] = {
    SEARCH_KNOWLEDGE.name: search_knowledge,
    SEARCH_ANALYSIS.name: search_analysis,
    GET_GAME_ANALYSIS.name: get_game_analysis,
    LIST_CRITICAL_MOMENTS.name: list_critical_moments,
    GET_PROFILE_AGGREGATE.name: get_profile_aggregate,
    LOOKUP_OPENING.name: lookup_opening,
    VALIDATE_LINE.name: _call_validate_line,
    RECALL_MEMORY.name: recall_memory,
}

__all__ = ["TOOL_DISPATCH", "TOOL_SPECS", "ToolFn"]
