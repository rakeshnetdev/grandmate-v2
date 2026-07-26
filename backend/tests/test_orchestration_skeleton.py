"""LangGraph wiring tests.

Phase 1 proves the orchestration dependency compiles and runs. Phase 10 replaces the
placeholder nodes; these tests are expected to be rewritten then, not carried forward.
"""

from __future__ import annotations

from app.orchestration.graphs.skeleton import GraphState, build_skeleton_graph


def test_graph_compiles() -> None:
    assert build_skeleton_graph() is not None


def test_graph_executes_all_nodes_in_order() -> None:
    """The trace accumulator is what Phase 13 scores trajectories from."""
    graph = build_skeleton_graph()

    state: GraphState = {"question": "why was 23...Nxe4 bad?", "persona": "self_learner"}
    result = graph.invoke(state)

    assert result["trace"] == ["classify_intent", "gather_context", "compose_answer"]


def test_graph_carries_input_through_to_the_answer() -> None:
    graph = build_skeleton_graph()

    result = graph.invoke({"question": "test question", "persona": "coach"})

    assert result["answer"] == "[skeleton] received: test question"
    assert result["context"] == []


def test_graph_preserves_inbound_context_fields() -> None:
    graph = build_skeleton_graph()

    result = graph.invoke(
        {"question": "q", "persona": "kid", "profile_id": "p-1", "active_game_id": "g-1"}
    )

    assert result["profile_id"] == "p-1"
    assert result["active_game_id"] == "g-1"
    assert result["persona"] == "kid"
