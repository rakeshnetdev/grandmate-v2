"""Deterministic, LLM-free chat fallback (Phase 10).

Mirrors `domain/reports/fallback.py`'s reasoning exactly: when the grounding guardrail
still rejects the model's answer after one retry, degrade to something that makes zero
unverified claims rather than deliver ungrounded text. Every field this emits was already
returned verbatim by a tool this turn — nothing here is generated.
"""

from __future__ import annotations

from typing import Any

_NOTHING_FOUND = (
    "I couldn't put together a reliably grounded answer to that just now. Could you "
    "rephrase, or point me at a specific game or move?"
)

_SOMETHING_FOUND = (
    "I found some relevant information but couldn't confirm a fully grounded answer to "
    "your question. Here is what the underlying analysis actually shows:"
)


def build_fallback_answer(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    """`tool_results` is whatever the agent loop's tool calls actually returned this
    turn (`GraphState.context`) — surfaced as-is so the user gets something real instead
    of nothing, without this function asserting anything of its own."""
    if not tool_results:
        return {"answer": _NOTHING_FOUND, "citations": []}
    return {"answer": _SOMETHING_FOUND, "citations": [], "raw_findings": tool_results}


__all__ = ["build_fallback_answer"]
