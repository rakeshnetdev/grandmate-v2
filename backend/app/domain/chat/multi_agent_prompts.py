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
- is_general_chat: true if the message is not a chess question at all — a greeting, \
thanks, a sign-off, small talk, a question about you (what you are, what you can do, how \
you work), or a question about this conversation (what you said earlier, repeat that). \
These are answerable from your own role and the messages already in the thread, so no \
specialist can add anything.
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

A message that opens with a pleasantry but goes on to ask something about chess is a \
chess question, not general chat: classify it on what it asks for, never on how it opens.
"How does this coaching assistant work?" is about you, so it is general chat — asking \
about a *coach* is not the same as asking about *coaching concepts*.

Respond as JSON with exactly this shape:
{"is_general_chat": <bool>, "needs_retrieval": <bool>, "needs_analysis": <bool>, \
"needs_clarification": <bool>}"""


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
    """Parse `(is_general_chat, needs_retrieval, needs_analysis, needs_clarification)`.

    Defaults to over-gathering on unparseable output: when routing classification itself
    fails, the safer fallback is to gather broadly rather than risk a missing fact that
    would later surface as a grounding failure. `is_general_chat` therefore defaults to
    `False` while the two specialist flags default to `True` — the asymmetry is the point.
    A wrongly-general turn skips gathering entirely and answers a real chess question with
    no facts; a wrongly-specialist turn only wastes a call.

    `is_general_chat` is authoritative when set, because the two are not independent
    judgements: a model that classifies "thanks, see you tomorrow" as general chat and
    *also* leaves `needs_retrieval` true is contradicting itself, and honouring both would
    send a sign-off to the retriever. Suppressing here rather than at the router keeps that
    invariant next to the parse that produces it, so every caller sees a coherent plan.
    """
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if not isinstance(parsed, dict):
        return {
            "is_general_chat": False,
            "needs_retrieval": True,
            "needs_analysis": True,
            "needs_clarification": False,
        }

    is_general_chat = bool(parsed.get("is_general_chat", False))
    return {
        "is_general_chat": is_general_chat,
        "needs_retrieval": not is_general_chat and bool(parsed.get("needs_retrieval", True)),
        "needs_analysis": not is_general_chat and bool(parsed.get("needs_analysis", True)),
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
- recall_memory: use when answering depends on durable facts remembered about this \
player — stated preferences, goals, confirmed recurring patterns — rather than on the \
current game or the corpus.

Guidelines:
- Retrieve only what is relevant to the user's latest question.
- Prefer a small number of high-signal searches over many weak searches.
- If the question is purely about a specific game's canonical facts and does not need \
corpus retrieval, do not call tools unnecessarily.
- Stop calling tools once you have enough material for a downstream coach to answer.
- Never phrase the final answer, advice, or explanation.

When finished, respond with a JSON object containing exactly:
{"done": true}"""


_CHESS_ANALYST_SYSTEM_PROMPT_TEMPLATE = """You are the chess-analysis specialist inside \
a chess coaching assistant. Your only job is to fetch canonical facts about the user's \
own games — never answer the user's question yourself.

Available tools:
- get_game_analysis
- list_critical_moments
- get_profile_aggregate
- lookup_opening

{context_note}

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
{{"done": true}}"""


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
    """No open-game context by design: neither of the retriever's tools takes a game id
    (`search_knowledge` is global, `search_analysis` is profile-scoped at the retriever
    interface), so naming the open game here could only bias it toward that game's
    material on a general question — the exact failure Phase 20 fixed elsewhere."""
    return Message(role="system", content=_RETRIEVER_SYSTEM_PROMPT)


def build_chess_analyst_system_message(*, active_game_id: str | None) -> Message:
    """The analyst's two most-used tools, `get_game_analysis` and `list_critical_moments`,
    both take a **required** `game_id`. Without the open game's id in its prompt this
    agent had no id to pass and no way to obtain one, so it answered questions about the
    user's own game with zero tool calls — the single agent never had this problem
    because `build_agent_system_message` has carried `active_game_id` since Phase 10.

    Framed as available context rather than as the subject of the turn, for the reason
    Phase 20 recorded: "prefer tools scoped to that game" is enough to make a general
    chess question get answered from whatever game happens to be open.
    """
    context_note = (
        f"The user has a game open (id: {active_game_id}). Pass exactly that id as the "
        "`game_id` argument when the question is about that game — 'this game', 'my "
        "game', a move in it. A general chess question is not about it: gather nothing "
        "rather than fetching that game's facts."
        if active_game_id
        else "No specific game is currently open. Only profile-wide tools "
        "(get_profile_aggregate) can be used unless the user names a specific game."
    )
    return Message(
        role="system",
        content=_CHESS_ANALYST_SYSTEM_PROMPT_TEMPLATE.format(context_note=context_note),
    )


def build_clarifier_system_message() -> Message:
    return Message(role="system", content=_CLARIFIER_SYSTEM_PROMPT)


_COACH_SYSTEM_PROMPT_TEMPLATE = """You are GrandMate's chess coaching assistant. To the \
user you are simply their chess coach: never describe yourself as one agent in a \
pipeline, and never mention specialists, routing, or "gathered context" in your answer. \
You have no tools. You may state a chess fact only if it appears in the CONTEXT below. \
If the context does not contain something you need, say so plainly rather than guessing.

Your job is to produce the user-facing answer.

{voice}

{context_note}

{turn_note}

Rules:
- Do not invent moves, evaluations, openings, motifs, or statistics.
- Do not claim certainty beyond what the context supports.
- If context is partial, give the best bounded answer and say what is missing.
- If context is empty or insufficient for a chess claim, say so plainly.
- Address every part of a multi-part question, but only from the context. Answer the \
parts the context covers; for a part it does not cover, say plainly that you do not have \
the material for it. Never silently drop a sub-question, and never fill one in from your \
own knowledge — an unanswered part named as unanswered is correct, an unsourced \
definition is not.
- Keep the answer aligned with the persona voice above.
- Every factual chess claim in the answer must have a matching citation object.

Gathered context this turn (JSON, one entry per tool call a specialist made):
{context_json}

Respond with a JSON object of exactly this shape:
{{"answer": "<the text to show the user>", "citations": [<zero or more citation objects>]}}

Allowed citation object forms, using only material that actually appears in the context.
These five are the *only* kinds that exist — the critic rejects any other `kind` outright,
so a claim you cannot express as one of these must be stated without a citation rather
than cited under an invented kind:
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
- general chess knowledge retrieved this turn (Phase 20):
  {{"kind": "knowledge", "chunk_id": "<the chunk_id from the retrieved context>"}}

Use "knowledge" for anything drawn from retrieved corpus material rather than from one of \
the user's own games. The game-scoped kinds are about a specific game the user played, so \
never attach a game_id to a general claim.

If the context is empty or insufficient for a *chess* claim, say so in "answer" rather \
than inventing a fact, and leave "citations" empty. Never invent a citation to satisfy \
the format — an answer that states no chess fact correctly carries no citations at all, \
and that is the expected shape for a question about the conversation or about you."""


# Told to the coach when the supervisor classified the turn as general chat. Empty
# context is the *expected* shape here, not a gathering failure, and saying so removes an
# ambiguity the coach previously had to resolve by re-reading the question itself.
_GENERAL_CHAT_TURN_NOTE = """This turn is not a chess question. It is a greeting, a \
sign-off, small talk, a question about you, or a question about this conversation — so no \
specialist gathered anything, and the empty context below is expected rather than a \
failure to find material.

Answer it directly and in the persona voice, from your role as described above and from \
the messages already in this thread. Do not cite anything: there is nothing to cite and \
nothing needs citing. Do not mention missing context, and do not refuse — "I don't have \
any context available" is a wrong answer to a question like this."""

# Told to the coach on a chess turn. The two carve-outs are kept as a safety net: if the
# supervisor misclassifies a genuine "how do you work?" as a chess question, the coach can
# still answer it rather than hedging. That hedge is not merely a low score — RAGAS
# `response_relevancy` scores a noncommittal answer a hard 0.000 — and it used to leak the
# pipeline's internals ("context gathered from upstream specialists") into user-facing text.
#
# The ordering rule below is load-bearing. An earlier wording ("if it is empty, they found
# nothing: say so plainly") was obeyed too eagerly on *partial* context: the coach opened
# with "I don't have specific information on whether your opening was played correctly"
# and then answered the rest perfectly. `ag-opening-plan` scored 0.00 relevancy in three
# consecutive replicates on an answer whose substance was unchanged, because the leading
# disclaimer is what the noncommittal classifier reads. Leading with the gap is also just
# bad coaching, so the rule is worth keeping on its own terms rather than as judge-pleasing.
_CHESS_TURN_NOTE = """The context below is everything the specialists found this turn. If \
it is empty, they found nothing: say so plainly rather than guessing at a chess fact.

Partial context is not empty context. Lead with what the context does support, in full, \
and put whatever it does not cover at the end — never open with a disclaimer about what \
you are missing, and never let one missing part turn the whole answer into a refusal.

Two kinds of question are still answerable with no context at all, and empty context is \
not a reason to refuse either:
- Questions about this conversation — what you said earlier, repeating or rephrasing a \
previous answer — are answerable from the messages already in this thread.
- Questions about you — what you can do, how you help, what you are for, plus greetings \
and sign-offs — are answerable from your role as described above.
Answer both kinds directly, in the persona voice, with no citations. They are not chess \
claims."""


def build_coach_system_message(
    persona: Persona,
    *,
    active_game_id: str | None,
    context: list[dict[str, Any]],
    is_general_chat: bool = False,
) -> Message:
    """Build the coach's system prompt with inlined specialist context.

    Unlike the single-agent prompt path, the coach does not discover facts via tools.
    The inlined JSON context is the handoff contract: upstream specialists gather facts,
    and the coach phrases chess claims only from that supplied record.

    `is_general_chat` closes the one ambiguity that contract left open. An empty `context`
    used to mean two opposite things — "no specialist ran, because nothing needed
    gathering" and "a specialist ran and found nothing" — which call for opposite answers
    (answer directly vs. say plainly you lack the material). The coach had to re-derive
    which case it was in by reading the question, a judgement the supervisor already made
    one node earlier and then discarded. It is now passed through instead.

    Defaults to `False` so a caller that has not been updated gets the chess-turn prompt,
    which still carries both non-chess carve-outs and so degrades to the previous
    behaviour rather than to a hedge.
    """
    context_note = (
        f"The user has a game open (id: {active_game_id}). A general chess question is "
        "not a question about that game, and must not be answered from it."
        if active_game_id
        else "No specific game is currently open."
    )
    content = _COACH_SYSTEM_PROMPT_TEMPLATE.format(
        voice=PERSONA_VOICE[persona],
        context_note=context_note,
        turn_note=_GENERAL_CHAT_TURN_NOTE if is_general_chat else _CHESS_TURN_NOTE,
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
