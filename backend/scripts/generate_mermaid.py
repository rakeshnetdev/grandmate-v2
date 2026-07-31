"""Generate Mermaid state diagrams for chat and multi-agent graphs."""

from __future__ import annotations

from pathlib import Path
from app.orchestration.graphs.factories import make_chat_graph, make_multi_agent_graph

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS_DIR = BACKEND_ROOT / "docs" / "diagrams"


def generate_diagrams() -> None:
    DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Chat Graph
    chat_graph = make_chat_graph()
    chat_mermaid = chat_graph.get_graph().draw_mermaid()
    chat_file = DIAGRAMS_DIR / "chat_graph.mermaid"
    chat_file.write_text(chat_mermaid, encoding="utf-8")
    print(f"Generated {chat_file}")

    # 2. Multi-Agent Graph
    ma_graph = make_multi_agent_graph()
    ma_mermaid = ma_graph.get_graph().draw_mermaid()
    ma_file = DIAGRAMS_DIR / "multi_agent_graph.mermaid"
    ma_file.write_text(ma_mermaid, encoding="utf-8")
    print(f"Generated {ma_file}")


if __name__ == "__main__":
    generate_diagrams()
