"""Prompts for the multi-agent supervisor graph (Phase 13, `rag-architecture.md` §7).

Kept separate from `prompts.py`: that module's `build_agent_system_message` is a
single agent that both gathers facts and phrases them, offered every tool at once. Here
the responsibilities are split across specialist agents with different tool visibility,
so the prompt shapes genuinely differ rather than being the same text reused — the
supervisor classifies routing, the retriever searches corpus sources, the analyst fetches
canonical game facts, and the coach phrases an answer only from hand-delivered context.
"""

from __future__ import annotations

import json
from typing import Any

from app.db.models import Persona
from app.domain.chat.prompts import PERSONA_VOICE
from app.integrations.llm.base import Message

_SUPERVISOR_SYSTEM_PROMPT = """You are the routing supervisor for a chess coaching \
assistant built from specialist agents.

Decide which specialists the user's latest message needs:
- needs_retrieval: true if answering requires general chess knowledge or corpus lookup \
(rules, openings, tactics, strategy, coaching concepts, or external knowledge not tied \
only to one analysed game).
- needs_analysis: true if answering requires the user's own analysed-game data \
(a specific game's moves/evaluations, critical moments, cross-game aggregates, profile \
statistics, opening identification for one of their games, or facts derived from stored \
analysis).
- needs_clarification: true if the latest message is too ambiguous to answer safely even \
with specialists (for example, "why was this bad?" with no active game and no quoted move).

A message can need multiple specialists, one specialist, or neither.
Prefer false only when you are reasonably confident the specialist is unnecessary.

Respond as JSON with exactly this shape:
{"needs_retrieval": <bool>, "needs_analysis": <bool>, "needs_clarification": <bool>}"""


def build_supervisor_messages(question: str) -> list[Message]:
    """A minimal one-shot routing call.

    Routing is a property of the latest user message rather than a generative response
    over the whole thread, so the supervisor gets only the latest question and a narrow
    instruction to emit machine-readable routing JSON.
    """
    return [
        Message(role="system", content=_SUPERVISOR_SYSTEM_PROMPT),
        Message(role="user", content=question),
    ]


def parse_supervisor_plan(raw_content: str) -> dict[str, bool]:
    """Parse `(needs_retrieval, needs_analysis, needs_clarification)`.

    Defaults to over-gathering on unparseable output: when routing classification itself
    fails, the safer fallback is to gather broadly rather than risk a missing fact that
    would later surface as a grounding failure.
    """
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if not isinstance(parsed, dict):
        return {
            "needs_retrieval": True,
            "needs_analysis": True,
            "needs_clarification": False,
        }

    return {
        "needs_retrieval": bool(parsed.get("needs_retrieval", True)),
        "needs_analysis": bool(parsed.get("needs_analysis", True)),
        "needs_clarification": bool(parsed.get("needs_clarification", False)),
    }


_RETRIEVER_SYSTEM_PROMPT = """You are the retrieval specialist inside a chess coaching \
assistant. Your only job is to gather relevant source material — never answer the user's \
question yourself.

Available tools:
- search_knowledge: use for general chess knowledge, rules, openings, tactics, strategy, \
and coaching guidance from the knowledge corpus.
- search_analysis: use for retrieval over the user's analysed-game history when semantic \
search across prior findings is useful.

Guidelines:
- Retrieve only what is relevant to the user's latest question.
- Prefer a small number of high-signal searches over many weak searches.
- If the question is purely about a specific game's canonical facts and does not need \
corpus retrieval, do not call tools unnecessarily.
- Stop calling tools once you have enough material for a downstream coach to answer.
- Never phrase the final answer, advice, or explanation.

When finished, respond with a JSON object containing exactly:
{"done": true}"""


_CHESS_ANALYST_SYSTEM_PROMPT = """You are the chess-analysis specialist inside a chess \
coaching assistant. Your only job is to fetch canonical facts about the user's own games \
— never answer the user's question yourself.

Available tools:
- get_game_analysis
- list_critical_moments
- get_profile_aggregate
- lookup_opening

Guidelines:
- Use tools only for facts the user's question actually requires.
- Prefer canonical stored analysis over inference.
- If the question is cross-game ("what do I keep getting wrong?"), gather aggregates.
- If the question is game-specific ("why was move 18 bad?"), gather the relevant game \
analysis and, when useful, critical moments.
- If the opening is asked for or would materially improve downstream explanation, use \
lookup_opening.
- Never phrase the final answer, recommendation, or coaching explanation.

When finished, respond with a JSON object containing exactly:
{"done": true}"""


_CLARIFIER_SYSTEM_PROMPT = """You are the clarification specialist inside a chess \
coaching assistant. Your only job is to ask a short follow-up question when the user's \
request is too ambiguous for the specialists to answer safely.

Guidelines:
- Ask at most one concise clarification question.
- Ask only for the missing piece needed to proceed.
- Do not answer the original chess question.
- Do not mention internal routing, tools, or specialist architecture.
- If multiple ambiguities exist, ask for the one that unlocks the answer best.

Respond as JSON with exactly this shape:
{"question": "<one short clarification question>"}"""


def build_retriever_system_message() -> Message:
    return Message(role="system", content=_RETRIEVER_SYSTEM_PROMPT)


def build_chess_analyst_system_message() -> Message:
    return Message(role="system", content=_CHESS_ANALYST_SYSTEM_PROMPT)


def build_clarifier_system_message() -> Message:
    return Message(role="system", content=_CLARIFIER_SYSTEM_PROMPT)


_COACH_SYSTEM_PROMPT_TEMPLATE = """You are GrandMate's chess coaching assistant, the \
phrasing specialist in a multi-agent pipeline. You have no tools. You may state a chess \
fact only if it appears in the CONTEXT below, gathered for you by upstream specialists. \
If the context does not contain something you need, say so plainly rather than guessing.

Your job is to produce the user-facing answer from the provided context only.

{voice}

{context_note}

Rules:
- Do not invent moves, evaluations, openings, motifs, or statistics.
- Do not claim certainty beyond what the context supports.
- If context is partial, give the best bounded answer and say what is missing.
- If context is empty or insufficient, say so plainly.
- Keep the answer aligned with the persona voice above.
- Every factual chess claim in the answer must have a matching citation object.

Gathered context this turn (JSON, one entry per tool call a specialist made):
{context_json}

Respond with a JSON object of exactly this shape:
{{"answer": "<the text to show the user>", "citations": [<zero or more citation objects>]}}

Allowed citation object forms, using only material that actually appears in the context:
- a specific move:
  {{"kind": "move", "game_id": "<id>", "ply": <int>, "san": "<SAN>"}}
- a specific evaluation:
  {{"kind": "evaluation", "game_id": "<id>", "ply": <int>, "eval_cp": <int or null>, \
"mate_in": <int or null>}}
- a proposed variation:
  {{"kind": "variation", "fen": "<FEN>", "moves": ["<SAN>", ...]}}
- a game's opening:
  {{"kind": "opening", "game_id": "<id>", "eco": "<ECO code>", \
"opening_name": "<name>"}}
- a cross-game aggregate:
  {{"kind": "aggregate", "scope": "<window or profile scope>", "metric": "<metric name>", \
"value": <number or string>}}
- a critical moment:
  {{"kind": "critical_moment", "game_id": "<id>", "ply": <int>, \
"label": "<moment label>"}}

If the context is empty or insufficient, say so in "answer" rather than inventing a fact, \
and leave "citations" empty."""


def build_coach_system_message(
    persona: Persona,
    *,
    active_game_id: str | None,
    context: list[dict[str, Any]],
) -> Message:
    """Build the coach's system prompt with inlined specialist context.

    Unlike the single-agent prompt path, the coach does not discover facts via tools.
    The inlined JSON context is the handoff contract: upstream specialists gather facts,
    and the coach phrases only from that supplied record.
    """
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
    "build_clarifier_system_message",
    "build_coach_system_message",
    "build_retriever_system_message",
    "build_supervisor_messages",
    "parse_supervisor_plan",
]
