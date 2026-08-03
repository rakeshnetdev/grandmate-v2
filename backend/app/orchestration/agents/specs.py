"""Agent roster and tool bindings (Phase 13, `rag-architecture.md` §7, D-016).

The roster and each agent's tool subset were fixed at Phase 0's design stage, not
re-decided here — this module is the executable form of that table, nothing more:

- Supervisor: intent/routing classification, assembly — no tools.
- Retriever: corpus search and reranking — `search_knowledge`, `search_analysis`,
  `recall_memory`.
- Chess analyst: analysis interpretation — `get_game_analysis`, `list_critical_moments`,
  `get_profile_aggregate`, `lookup_opening`.
- Coach: persona-appropriate phrasing and recommendations — no tools.
- Critic: verifies the draft against deterministic truth — `validate_line` and
  `get_game_analysis`, reached via `validate_answer` (reused unchanged from Phase 10;
  see `graphs/multi_agent.py`).

**Why Coach and Supervisor get no tools.** This is the handoff contract Phase 13's plan
calls for: specialists gather facts, the coach only phrases them. A coach that could call
`get_game_analysis` itself would blur "who is responsible for grounding" back into one
agent — exactly the entanglement splitting drafting from verification is supposed to
avoid (`rag-architecture.md` §7's rationale for a separate critic applies just as much to
separating fact-gathering from phrasing).

Filtering `TOOL_DISPATCH`/`TOOL_SPECS` (not maintaining a second copy) is `claude.md` rule
13 applied one level down: the specialist tool subsets are *views* over the one registry
Phase 10 already built, never a second definition of what a tool does.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.llm.base import ToolSpec
from app.orchestration.tools.analysis_tools import (
    GET_GAME_ANALYSIS,
    GET_PROFILE_AGGREGATE,
    LIST_CRITICAL_MOMENTS,
    LOOKUP_OPENING,
)
from app.orchestration.tools.knowledge_tools import SEARCH_ANALYSIS, SEARCH_KNOWLEDGE
from app.orchestration.tools.memory_tools import RECALL_MEMORY
from app.orchestration.tools.registry import TOOL_DISPATCH, ToolFn


@dataclass(frozen=True)
class AgentSpec:
    """One specialist's identity: a name for tracing/tests, and the tools it may call.

    `tool_specs` is what the LLM provider sees offered; `tool_dispatch` is the matching
    name-keyed subset of `TOOL_DISPATCH` the graph resolves a call against. The two are
    always built together (`_subset` below) so they can never drift apart into "the model
    was offered a tool the dispatcher doesn't recognise."
    """

    name: str
    tool_specs: tuple[ToolSpec, ...]
    tool_dispatch: dict[str, ToolFn]


def _subset(*specs: ToolSpec) -> tuple[tuple[ToolSpec, ...], dict[str, ToolFn]]:
    dispatch = {spec.name: TOOL_DISPATCH[spec.name] for spec in specs}
    return specs, dispatch


# `recall_memory` sits with the Retriever for the same reason `search_analysis` does:
# grouping by retrieval *mechanism* rather than subject matter. It was previously
# assigned to no agent at all, which meant flipping `USE_MULTI_AGENT` silently dropped
# half of Phase 11 — the single agent has offered this tool since Phase 11 and the
# multi-agent path could not reach it from any node.
_retriever_specs, _retriever_dispatch = _subset(SEARCH_KNOWLEDGE, SEARCH_ANALYSIS, RECALL_MEMORY)
_chess_analyst_specs, _chess_analyst_dispatch = _subset(
    GET_GAME_ANALYSIS, LIST_CRITICAL_MOMENTS, GET_PROFILE_AGGREGATE, LOOKUP_OPENING
)

SUPERVISOR = AgentSpec(name="supervisor", tool_specs=(), tool_dispatch={})
RETRIEVER = AgentSpec(
    name="retriever", tool_specs=_retriever_specs, tool_dispatch=_retriever_dispatch
)
CHESS_ANALYST = AgentSpec(
    name="chess_analyst", tool_specs=_chess_analyst_specs, tool_dispatch=_chess_analyst_dispatch
)
COACH = AgentSpec(name="coach", tool_specs=(), tool_dispatch={})
# The critic calls no tools of its own — it verifies via `validate_answer`, which reaches
# `validate_line` and the analysis tables directly. Recorded here as `()` rather than
# omitted so the roster stays a complete, one-look reference of "who can call what."
CRITIC = AgentSpec(name="critic", tool_specs=(), tool_dispatch={})

__all__ = ["CHESS_ANALYST", "COACH", "CRITIC", "RETRIEVER", "SUPERVISOR", "AgentSpec"]
