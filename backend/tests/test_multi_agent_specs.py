"""Agent roster and tool-subset correctness (Phase 13, `rag-architecture.md` §7).

These are the "routing correctness" checks at the cheapest possible level: no graph, no
LLM, just confirming the roster matches the design table and that `tool_specs`/
`tool_dispatch` can never drift apart (`AgentSpec` is built from one call to `_subset`).
"""

from __future__ import annotations

from app.orchestration.agents import CHESS_ANALYST, COACH, CRITIC, RETRIEVER, SUPERVISOR


def test_supervisor_coach_and_critic_have_no_tools() -> None:
    for spec in (SUPERVISOR, COACH, CRITIC):
        assert spec.tool_specs == ()
        assert spec.tool_dispatch == {}


def test_retriever_is_scoped_to_the_search_tools_only() -> None:
    names = {tool.name for tool in RETRIEVER.tool_specs}
    assert names == {"search_knowledge", "search_analysis"}
    assert set(RETRIEVER.tool_dispatch) == names


def test_chess_analyst_is_scoped_to_the_analysis_tools_only() -> None:
    names = {tool.name for tool in CHESS_ANALYST.tool_specs}
    assert names == {
        "get_game_analysis",
        "list_critical_moments",
        "get_profile_aggregate",
        "lookup_opening",
    }
    assert set(CHESS_ANALYST.tool_dispatch) == names


def test_every_tool_dispatch_entry_is_actually_callable() -> None:
    """Guards against `_subset` ever being built from a `ToolSpec` whose name has no
    matching entry in the shared `TOOL_DISPATCH` registry — that would be a tool the
    model can be offered but whose call can never actually be dispatched."""
    for spec in (RETRIEVER, CHESS_ANALYST):
        for tool in spec.tool_specs:
            assert callable(spec.tool_dispatch[tool.name])
