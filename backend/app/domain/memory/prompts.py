"""Memory-extraction prompt and parsing (Phase 11, ADR-0005, D-013).

A separate, small LLM call after each chat turn — same pattern as
`domain/chat/prompts.py`'s intent classifier — rather than folding extraction into the
agent's own answer-generation call. Keeping it separate means a bug or drift in
extraction can never affect what the user is actually told, and the extraction prompt
can be tuned (what counts as "durable") without touching the answer-generation contract
at all.
"""

from __future__ import annotations

import json

from app.integrations.llm.base import Message

_SYSTEM_PROMPT = """You extract durable, cross-session facts about a chess player from \
one chat exchange — never from anything the assistant itself said unprompted.

Only extract something if the player's own message plainly states it. Do not infer, \
guess, or extract anything from small talk, a single passing remark, or the assistant's \
answer. When in doubt, extract nothing — an empty list is the correct, common answer, \
not a failure.

Three kinds only:
- "preference": how the player wants to be coached (e.g. "always show me the engine \
line", "keep it short").
- "goal": what the player is currently working toward (e.g. "I want to get better at \
endgames this month").
- "recurring_finding": a pattern about the player's own play that the conversation \
confirmed as recurring, not a one-off (e.g. "I keep hanging pieces in time trouble").

Respond as JSON: {"memories": [{"kind": "...", "content": "<one plain sentence, third \
person, e.g. 'Wants to focus on endgame technique'>", "confidence": <0.0-1.0>}]}. \
Confidence reflects how explicitly and durably the player stated it — a passing \
"maybe I should work on that" is low confidence; "my goal this month is X" is high. \
Return {"memories": []} when nothing durable was said."""


def build_extraction_messages(question: str, answer: str) -> list[Message]:
    """One exchange, not the whole thread — extraction judges what *this* turn added,
    the same one-turn-at-a-time scope the write step itself runs at."""
    return [
        Message(role="system", content=_SYSTEM_PROMPT),
        Message(
            role="user",
            content=f"Player said: {question!r}\nAssistant answered: {answer!r}",
        ),
    ]


_VALID_KINDS = {"preference", "goal", "recurring_finding"}


def parse_candidate_memories(raw_content: str) -> list[dict[str, object]]:
    """Candidates as plain dicts (`kind`, `content`, `confidence`) — never raises;
    anything malformed is dropped rather than failing the whole chat turn over a
    best-effort side channel."""
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, dict):
        return []
    memories = parsed.get("memories")
    if not isinstance(memories, list):
        return []

    candidates: list[dict[str, object]] = []
    for entry in memories:
        if not isinstance(entry, dict):
            continue
        kind, content, confidence = entry.get("kind"), entry.get("content"), entry.get("confidence")
        if kind not in _VALID_KINDS:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        if not isinstance(confidence, int | float):
            continue
        candidates.append(
            {"kind": kind, "content": content.strip(), "confidence": float(confidence)}
        )
    return candidates


__all__ = ["build_extraction_messages", "parse_candidate_memories"]
