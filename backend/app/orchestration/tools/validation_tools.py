"""Legal-move validation (Phase 10, ADR-0008 §"the tool set").

Exists specifically because models invent plausible-looking illegal moves — cheap,
deterministic, and it catches a whole class of embarrassing errors before they reach a
user (`rag-architecture.md` §4). This is also the tool the grounding guardrail
(`orchestration/graphs/chat.py`) calls directly, not just something offered to the model.
"""

from __future__ import annotations

from typing import Any

import chess

from app.integrations.llm.base import ToolSpec

VALIDATE_LINE = ToolSpec(
    name="validate_line",
    description=(
        "Check whether a sequence of moves, in Standard Algebraic Notation, is legal "
        "from a given starting position. Use this before asserting a variation is a "
        "player's best or intended alternative."
    ),
    parameters={
        "type": "object",
        "properties": {
            "fen": {"type": "string", "description": "The starting position, in FEN."},
            "moves": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The moves to check, in SAN, played in order from `fen`.",
            },
        },
        "required": ["fen", "moves"],
    },
)


def validate_line(*, fen: str, moves: list[str]) -> dict[str, Any]:
    """Synchronous and pure — no session or profile context needed, unlike every other
    tool here, which is why it takes no `ToolContext` (the agent loop dispatches it the
    same way regardless)."""
    try:
        board = chess.Board(fen)
    except ValueError:
        return {"legal": False, "illegal_at": None, "reason": f"{fen!r} is not a valid FEN"}

    for index, move in enumerate(moves):
        try:
            board.push_san(move)
        except ValueError as exc:
            return {"legal": False, "illegal_at": index, "reason": str(exc)}

    return {"legal": True, "illegal_at": None, "reason": None}


__all__ = ["VALIDATE_LINE", "validate_line"]
