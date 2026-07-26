"""LangGraph integration skeleton.

Phase 1 deliverable: prove the LangGraph wiring compiles and executes, and establish the
state shape that Phase 10's chat graph will grow from. There is no LLM call here — the
nodes are deterministic — because the point is to validate the orchestration dependency,
not to build the agent early.

Phase 10 replaces the placeholder nodes with real intent routing, retrieval tools, and a
checkpointer. The state fields below are the ones the chat graph is expected to need, so
they are declared now rather than discovered later.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from app.core.devinsight import SpanKind, get_recorder


def _append(existing: list[str], incoming: list[str]) -> list[str]:
    """Reducer that accumulates across node executions rather than overwriting."""
    return [*existing, *incoming]


class GraphState(TypedDict, total=False):
    """Shared state passed between graph nodes.

    ``trace`` accumulates a record of which nodes ran. That is deliberately part of the
    state rather than a logging side effect: Phase 13's multi-agent evaluation scores
    trajectories, and a trajectory you cannot inspect cannot be scored.
    """

    # Inbound
    question: str
    profile_id: str | None
    active_game_id: str | None
    persona: str

    # Accumulated during execution
    trace: Annotated[list[str], _append]
    context: list[dict[str, Any]]
    answer: str | None


def _classify_intent(state: GraphState) -> GraphState:
    """Placeholder for Phase 10 intent routing.

    Real implementation classifies into explain / compare / summarise / train-next and
    routes to different tool sets. For now it only records that it ran.
    """
    # Node instrumentation is written unconditionally — the recorder is a no-op object
    # when developer insight is disabled, so there is nothing to guard (ADR-0013).
    with get_recorder().span(SpanKind.GRAPH_NODE, "classify_intent") as span:
        if span:
            span.set(persona=state.get("persona"))
        return {"trace": ["classify_intent"]}


def _gather_context(state: GraphState) -> GraphState:
    """Placeholder for Phase 10 retrieval.

    Real implementation calls the retrieval tools the agent selects (ADR-0008). Returns
    empty context here so downstream nodes see the right shape.
    """
    with get_recorder().span(SpanKind.GRAPH_NODE, "gather_context") as span:
        context: list[dict[str, Any]] = []
        if span:
            span.set(context_items=len(context))
        return {"trace": ["gather_context"], "context": context}


def _compose_answer(state: GraphState) -> GraphState:
    """Placeholder for Phase 10 answer composition.

    Real implementation calls the LLM provider and then the grounding guardrail. The
    deterministic echo here keeps the skeleton testable with exact assertions.
    """
    with get_recorder().span(SpanKind.GRAPH_NODE, "compose_answer") as span:
        question = state.get("question", "")
        if span:
            # Named `question_text` rather than `question` so it is NOT caught by the
            # sensitive-attribute redaction — this is the skeleton's own echo, not user
            # content. Real user text at Phase 10 will be named to trip redaction.
            span.set(question_length=len(question))
        return {
            "trace": ["compose_answer"],
            "answer": f"[skeleton] received: {question}",
        }


def build_skeleton_graph() -> Any:
    """Compile the placeholder graph.

    Returns the compiled graph rather than the builder so callers cannot mutate it after
    construction.
    """
    builder = StateGraph(GraphState)

    builder.add_node("classify_intent", _classify_intent)
    builder.add_node("gather_context", _gather_context)
    builder.add_node("compose_answer", _compose_answer)

    builder.set_entry_point("classify_intent")
    builder.add_edge("classify_intent", "gather_context")
    builder.add_edge("gather_context", "compose_answer")
    builder.add_edge("compose_answer", END)

    return builder.compile()


__all__ = ["GraphState", "build_skeleton_graph"]
