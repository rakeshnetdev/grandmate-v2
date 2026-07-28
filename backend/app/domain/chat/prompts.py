"""Chat prompts: intent classification and the agent system message (Phase 10).

Kept separate from `domain/reports/prompts.py`: report generation is a single-shot
structured-JSON call over a fixed fact set, while chat is a multi-turn, tool-calling
conversation — different shape and different rules, so a shared module would only end up
branching internally rather than actually sharing anything.

Intent routing is an LLM classification call, not a keyword heuristic like Phase 7's
bucket router (`domain/retrieval/router.py`) — user phrasing for intent is open-ended
natural language, exactly the kind of judgment call worth handing to the model rather
than pattern-matching.
"""

from __future__ import annotations

import json

from app.db.models import Persona
from app.integrations.llm.base import Message

INTENTS = ("explain", "compare", "summarise", "train_next")
_DEFAULT_INTENT = "explain"

_INTENT_SYSTEM_PROMPT = (
    "You are an intent classifier for a chess coaching assistant. Classify the user's "
    "latest message into exactly one of: explain, compare, summarise, train_next.\n"
    "- explain: why a move, position, or concept is good or bad\n"
    "- compare: compare two games, moves, lines, or periods of play\n"
    "- summarise: an overview of a game or a stretch of recent play\n"
    "- train_next: what to study or practise next\n"
    'Respond as JSON: {"intent": "<one of the four>"}. If uncertain, choose "explain".'
)


def build_intent_messages(question: str) -> list[Message]:
    """A minimal one-shot classification call — no conversation history needed, since
    intent is a property of the latest message, not the thread."""
    return [
        Message(role="system", content=_INTENT_SYSTEM_PROMPT),
        Message(role="user", content=question),
    ]


def parse_intent(raw_content: str) -> str:
    """The classified intent, or `_DEFAULT_INTENT` on anything unparseable or
    off-taxonomy. A misclassified intent only affects which tools the agent reaches for
    first, not correctness — degrading to a safe default rather than erroring is the
    right failure mode for a step this low-stakes."""
    try:
        parsed = json.loads(raw_content)
        intent = parsed.get("intent") if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        intent = None
    return intent if intent in INTENTS else _DEFAULT_INTENT


# Tone rules per persona-matrix.md, adapted for a conversational surface rather than a
# generated report — same underlying voice contract as `domain/reports/prompts.py`'s
# per-persona system prompts, restated here because chat's system message also has to
# carry tool-use and grounding instructions a report prompt never needs.
_PERSONA_VOICE: dict[Persona, str] = {
    Persona.SELF_LEARNER: (
        "Speak directly to the player, second person. Centipawn values and engine "
        "terminology are fine when they clarify a point."
    ),
    Persona.COACH: (
        "Speak to a coach reviewing a student's game, third person ('the student'). "
        "Be technical and precise; principal variations and concrete lines are welcome."
    ),
    Persona.KID: (
        "Speak to a young player, simply and encouragingly. Never state a centipawn or "
        "other numeric evaluation value. One clear idea at a time."
    ),
}

_AGENT_SYSTEM_PROMPT_TEMPLATE = """You are GrandMate's chess coaching assistant.

{voice}

Ground every chess claim in a tool result. Never assert that a move was played, a \
position's evaluation, or a game's outcome from memory or guesswork — call a tool to \
check first. If you propose an alternative line, call validate_line before asserting it \
is legal.

{context}

When you are ready to answer (not calling any more tools), respond with a JSON object \
of exactly this shape:
{{"answer": "<the text to show the user>", "citations": [<zero or more citation objects>]}}

Add one citation object for every chess fact your answer states, using a tool result you \
already received this turn — never a fact you have not actually seen returned by a tool:
- a specific move: {{"kind": "move", "game_id": "<id>", "ply": <int>, "san": "<SAN>"}}
- a specific evaluation: {{"kind": "evaluation", "game_id": "<id>", "ply": <int>, \
"eval_cp": <int or null>, "mate_in": <int or null>}}
- a proposed variation: {{"kind": "variation", "fen": "<FEN>", "moves": ["<SAN>", ...]}}
- a game's opening: {{"kind": "opening", "game_id": "<id>", "eco": "<ECO code>", \
"opening_name": "<name>"}}

If you cannot ground an answer in the available tools, say so plainly in "answer" rather \
than guessing, and leave "citations" empty."""


def build_agent_system_message(persona: Persona, *, active_game_id: str | None) -> Message:
    """The system message that opens every agent turn. Re-sent every call rather than
    relying on the checkpointer to remember it — persona or active game can change
    between turns in the same thread, and a stale system message would silently keep
    instructing the old voice or the old game."""
    context = (
        f"The user currently has a game open (id: {active_game_id}). Prefer tools scoped "
        "to that game when the question is about 'this game' or 'my game'."
        if active_game_id
        else "No specific game is currently open. Use profile-wide or general-knowledge "
        "tools unless the user names a specific game."
    )
    content = _AGENT_SYSTEM_PROMPT_TEMPLATE.format(voice=_PERSONA_VOICE[persona], context=context)
    return Message(role="system", content=content)


__all__ = ["INTENTS", "build_agent_system_message", "build_intent_messages", "parse_intent"]
