"""Prompts for the multi-agent supervisor graph (Phase 13, `rag-architecture.md` §7).

Kept separate from `prompts.py`: that module's `build_agent_system_message` is a
single agent that both gathers facts and phrases them, offered every tool at once. Here
the two responsibilities are split across different agents with different tool
visibility, so the prompt shapes genuinely differ rather than being the same text reused
— the supervisor classifies routing instead of intent, and the coach is explicitly told
it has no tools and must work only from context hand-delivered by upstream specialists.
"""

from __future__ import annotations

import json
from typing import Any

from app.db.models import Persona
from app.domain.chat.prompts import PERSONA_VOICE
from app.integrations.llm.base import Message

_SUPERVISOR_SYSTEM_PROMPT = (
    "You are the routing supervisor for a chess coaching assistant built from "
    "specialist agents. Decide which specialists the user's latest message needs:\n"
    "- needs_retrieval: true if answering requires general chess knowledge (rules, "
    "opening theory, tactics, or strategy explanations) not specific to one of the "
    "user's own games.\n"
    "- needs_analysis: true if answering requires the user's own game data (a specific "
    "game's moves/evaluations, critical moments, cross-game aggregates, or opening "
    "identification for one of their games).\n"
    "A question can need both, one, or neither (e.g. a greeting needs neither).\n"
    'Respond as JSON: {"needs_retrieval": <bool>, "needs_analysis": <bool>}.'
)


def build_supervisor_messages(question: str) -> list[Message]:
    """A minimal one-shot routing call — same reasoning as `build_intent_messages`:
    routing is a property of the latest message, not the whole thread."""
    return [
        Message(role="system", content=_SUPERVISOR_SYSTEM_PROMPT),
        Message(role="user", content=question),
    ]


def parse_supervisor_plan(raw_content: str) -> dict[str, bool]:
    """`(needs_retrieval, needs_analysis)`, defaulting to `(True, True)` on anything
    unparseable. Over-gathering costs latency and tokens; under-gathering costs a
    grounding failure the critic would then have to catch — the safer default direction
    when the classification itself is the thing that failed, distinct from the
    budget-exhausted case (`graphs/multi_agent.py`'s `_supervisor` node), which
    deliberately defaults the other way because there is no budget left to spend."""
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if not isinstance(parsed, dict):
        return {"needs_retrieval": True, "needs_analysis": True}
    return {
        "needs_retrieval": bool(parsed.get("needs_retrieval", True)),
        "needs_analysis": bool(parsed.get("needs_analysis", True)),
    }


_RETRIEVER_SYSTEM_PROMPT = """You are the retrieval specialist inside a chess coaching \
assistant. Your only job is to search the knowledge corpus and the user's analysed-game \
history for material relevant to their question — never answer the question yourself.

Call search_knowledge for general chess rules/openings/tactics/strategy, and \
search_analysis for the user's own past games and findings. Call as many searches as are \
genuinely useful, then stop calling tools once you have enough. When done, respond with \
JSON: {"done": true} — a coach agent downstream will phrase the actual answer from what \
you found."""

_CHESS_ANALYST_SYSTEM_PROMPT = """You are the chess-analysis specialist inside a chess \
coaching assistant. Your only job is to fetch canonical facts about the user's own games \
— never answer the question yourself.

Call get_game_analysis, list_critical_moments, get_profile_aggregate, or lookup_opening \
as needed to gather the facts the question requires. When done, respond with JSON: \
{"done": true} — a coach agent downstream will phrase the actual answer from what you \
found."""


def build_retriever_system_message() -> Message:
    return Message(role="system", content=_RETRIEVER_SYSTEM_PROMPT)


def build_chess_analyst_system_message() -> Message:
    return Message(role="system", content=_CHESS_ANALYST_SYSTEM_PROMPT)


_COACH_SYSTEM_PROMPT_TEMPLATE = """You are GrandMate's chess coaching assistant, the \
phrasing specialist in a multi-agent pipeline. You have no tools — you may state a chess \
fact only if it appears in the CONTEXT below, gathered for you by other specialists. If \
the context does not contain something you need, say so plainly rather than guessing.

{voice}

{context_note}

Gathered context this turn (JSON, one entry per tool call a specialist made):
{context_json}

Respond with a JSON object of exactly this shape:
{{"answer": "<the text to show the user>", "citations": [<zero or more citation objects>]}}

Add one citation object for every chess fact your answer states, using only a result \
that actually appears in the context above:
- a specific move: {{"kind": "move", "game_id": "<id>", "ply": <int>, "san": "<SAN>"}}
- a specific evaluation: {{"kind": "evaluation", "game_id": "<id>", "ply": <int>, \
"eval_cp": <int or null>, "mate_in": <int or null>}}
- a proposed variation: {{"kind": "variation", "fen": "<FEN>", "moves": ["<SAN>", ...]}}
- a game's opening: {{"kind": "opening", "game_id": "<id>", "eco": "<ECO code>", \
"opening_name": "<name>"}}

If the context is empty or insufficient, say so in "answer" rather than inventing a fact, \
and leave "citations" empty."""


def build_coach_system_message(
    persona: Persona, *, active_game_id: str | None, context: list[dict[str, Any]]
) -> Message:
    """Unlike Phase 10's `build_agent_system_message`, the coach's context is inlined
    into the prompt as data rather than discovered via tool calls — this *is* the
    handoff contract: the coach reads what specialists already found, it never fetches
    anything itself."""
    context_note = (
        f"The user currently has a game open (id: {active_game_id})."
        if active_game_id
        else "No specific game is currently open."
    )
    content = _COACH_SYSTEM_PROMPT_TEMPLATE.format(
        voice=PERSONA_VOICE[persona],
        context_note=context_note,
        context_json=json.dumps(context) if context else "[]",
    )
    return Message(role="system", content=content)


__all__ = [
    "build_chess_analyst_system_message",
    "build_coach_system_message",
    "build_retriever_system_message",
    "build_supervisor_messages",
    "parse_supervisor_plan",
]
