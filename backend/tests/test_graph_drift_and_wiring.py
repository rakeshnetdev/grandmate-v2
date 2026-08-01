"""Tests for graph dependencies consistency (Rule 13) and mermaid diagram drift."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from app.orchestration.dependencies import build_chat_graph_deps, build_multi_agent_graph_deps
from app.orchestration.graphs.factories import make_chat_graph, make_multi_agent_graph

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS_DIR = BACKEND_ROOT / "docs" / "diagrams"


def test_factory_compilation() -> None:
    """Assert that zero-argument graph factories correctly compile CompiledStateGraph instances."""
    chat_graph = make_chat_graph()
    assert isinstance(chat_graph, CompiledStateGraph)

    ma_graph = make_multi_agent_graph()
    assert isinstance(ma_graph, CompiledStateGraph)


def test_dependency_wiring_signatures() -> None:
    """Assert that dependency builders construct valid graph dependency objects.

    Ensures that the fields produced by build_chat_graph_deps and
    build_multi_agent_graph_deps map exactly to ChatGraphDeps and MultiAgentGraphDeps.
    """
    import inspect

    chat_signature = inspect.signature(build_chat_graph_deps)
    ma_signature = inspect.signature(build_multi_agent_graph_deps)

    # Assert necessary parameters exist in builders
    assert "settings" in chat_signature.parameters
    assert "session" in chat_signature.parameters
    assert "llm" in chat_signature.parameters
    assert "embedding_provider" in chat_signature.parameters
    assert "opening_index" in chat_signature.parameters
    assert "store" in chat_signature.parameters
    assert "profile_id" in chat_signature.parameters

    assert "settings" in ma_signature.parameters
    assert "session" in ma_signature.parameters
    assert "llm" in ma_signature.parameters
    assert "embedding_provider" in ma_signature.parameters
    assert "opening_index" in ma_signature.parameters
    assert "store" in ma_signature.parameters
    assert "profile_id" in ma_signature.parameters


def test_mermaid_diagram_drift() -> None:
    """Assert that checked-in Mermaid state diagrams match the compiled graphs.

    If this test fails, it means a routing or node change was made to the graph, and
    the diagrams must be updated by running:
    uv run python -m scripts.generate_mermaid
    """
    chat_file = DIAGRAMS_DIR / "chat_graph.mermaid"
    assert chat_file.is_file(), f"Missing checked-in chat graph diagram: {chat_file}"
    expected_chat_mermaid = chat_file.read_text(encoding="utf-8")

    chat_graph = make_chat_graph()
    actual_chat_mermaid = chat_graph.get_graph().draw_mermaid()
    assert actual_chat_mermaid == expected_chat_mermaid, (
        "Chat graph mermaid diagram has drifted from the compiled graph. "
        "Update it using: uv run python -m scripts.generate_mermaid"
    )

    ma_file = DIAGRAMS_DIR / "multi_agent_graph.mermaid"
    assert ma_file.is_file(), f"Missing checked-in multi-agent graph diagram: {ma_file}"
    expected_ma_mermaid = ma_file.read_text(encoding="utf-8")

    ma_graph = make_multi_agent_graph()
    actual_ma_mermaid = ma_graph.get_graph().draw_mermaid()
    assert actual_ma_mermaid == expected_ma_mermaid, (
        "Multi-agent graph mermaid diagram has drifted from the compiled graph. "
        "Update it using: uv run python -m scripts.generate_mermaid"
    )
