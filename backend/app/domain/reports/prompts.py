"""Builds the LLM prompt for one persona's report (Phase 9, D-023, `persona-matrix.md`).

Kept strictly downstream of `facts.py`: this module only ever sees `Fact` objects and a
persona, never a `GameAnalysis` or python-chess object — the separation rule 8 of
`claude.md` requires between prompt construction and chess computation.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from app.db.models import Persona
from app.domain.reports.facts import Fact
from app.integrations.llm.base import Message

_SELF_LEARNER_FORMAT = (
    "This is an initial game review. Content requirements:\n"
    "- `summary`: 1-2 sentences on how the game actually went overall.\n"
    "- `findings` with `\"kind\": \"strength\"`: up to 2, only for facts whose "
    "classification is \"best\" — name the specific move and say why it worked using its "
    "own `motif` field (e.g. a fork, a pin). One sentence each.\n"
    "- `findings` with `\"kind\": \"mistake\"`: the 3 MOST INSTRUCTIVE errors only, not "
    "every one in FACTS — pick the ones most worth learning from. Each must name the ply "
    "and move, what it broke or missed, and the better move (a mistake fact's own "
    "`best_move_san`, if it has one). One sentence each.\n"
    "- `recommendations`: up to 2, each tied to one of the mistakes above by name, not "
    "generic advice.\n\n"
    "Style rules:\n"
    "- Every sentence must reference a real move, ply, or theme from FACTS. If you have "
    "nothing specific for a slot, omit it rather than padding.\n"
    "- Use the exact words \"blunder\", \"mistake\", \"inaccuracy\" for their matching "
    "classification, and \"best\" or \"excellent\" for a strength finding — this is how "
    "the interface highlights them, so do not paraphrase these.\n"
    "- Refer to players as \"White\", \"Black\", or by name. Never \"you\" or \"your\".\n"
    "- No engine numbers: no centipawn loss, evaluation, or depth. Translate them into "
    "chess ideas instead — a pin, a fork, a weak king, a lost center.\n"
    "- Bullets over paragraphs. Never more than 2 sentences in a row for one finding or "
    "recommendation.\n"
    "- Keep the whole response (summary + findings + recommendations combined) under "
    "250 words.\n"
    "- There is no rules/legality fact type. Never mention chess rules or legality."
)

_SYSTEM_PROMPTS: dict[Persona, str] = {
    Persona.SELF_LEARNER: (
        "You are a chess coach writing a report for the player about their own game, "
        "for them to read alone. Audience: an adult, chess-literate player studying "
        "their own game. Name tactical motifs and briefly explain them. Tone: direct "
        "and neutral. Frame mistakes as costing the advantage, not as a personal "
        "failing. Recommendations should be drills and study themes, not a lesson "
        f"plan.\n\n{_SELF_LEARNER_FORMAT}"
    ),
    Persona.COACH: (
        "You are writing a report for a coach preparing a lesson about their student's "
        "game. Audience: an adult, chess-expert coach. Show centipawn values and "
        "mention principal variation lines where given. Name tactical motifs without "
        "re-explaining them — assume expert knowledge. Go into high depth, including "
        "alternative lines where the facts support it. Tone: concise, technical, "
        "peer-to-peer. Refer to the player in the third person as 'the student'. "
        "Recommendations should read as lesson-plan structure and student-specific "
        "talking points."
    ),
    Persona.KID: (
        "You are writing a report for a young player, roughly 8-14 years old, about "
        "their own game. Use simple sentences and short paragraphs. Never show raw "
        "centipawn numbers or the word 'centipawn' — describe a bad move as 'a big "
        "mistake' or similar plain language instead. Name tactical motifs with a "
        "one-line plain explanation. Cover one idea at a time. Tone: encouraging, "
        "never harsh — never call the player's play 'bad' or blame them; frame a "
        "mistake as a learning chance, e.g. 'here's a chance to grab a free piece next "
        "time!'. Give exactly one concrete, achievable recommendation, not a list. Do "
        "not mention engine lines or move sequences beyond the game itself."
    ),
}

_OUTPUT_CONTRACT = (
    "Respond with a single JSON object and nothing else, matching exactly this shape:\n"
    '{"summary": "<1-2 sentence overview>", '
    '"findings": [{"fact_ids": ["<id>", ...], "text": "<prose>"}, ...], '
    '"recommendations": ["<prose>", ...]}\n\n'
    "Hard rules:\n"
    "- Every fact_id you use MUST come from the FACTS list below, copied exactly. "
    "Never invent a fact_id, a move, an evaluation, or a motif that is not in FACTS.\n"
    "- Every finding must reference at least one real fact_id.\n"
    "- Do not include any fact_id that is not in the FACTS list below.\n"
    "- Do not add commentary outside the JSON object."
)

# The "kind" field must live in the JSON shape itself, not just be described in prose
# above it — an earlier version only described it in _SELF_LEARNER_FORMAT and every
# field measured against real self-learner generations omitted "kind" anyway, because
# this concrete template is what the model actually pattern-matches its output against.
_OUTPUT_CONTRACT_SELF_LEARNER = (
    "Respond with a single JSON object and nothing else, matching exactly this shape:\n"
    '{"summary": "<1-2 sentence overview>", '
    '"findings": [{"fact_ids": ["<id>", ...], "text": "<prose>", '
    '"kind": "strength" or "mistake"}, ...], '
    '"recommendations": ["<prose>", ...]}\n\n'
    "Hard rules:\n"
    "- Every fact_id you use MUST come from the FACTS list below, copied exactly. "
    "Never invent a fact_id, a move, an evaluation, or a motif that is not in FACTS.\n"
    "- Every finding must reference at least one real fact_id.\n"
    "- Do not include any fact_id that is not in the FACTS list below.\n"
    '- Every finding\'s "kind" is REQUIRED and must be exactly "strength" or "mistake" '
    "— never omit it.\n"
    "- Do not add commentary outside the JSON object."
)


def build_messages(
    facts: list[Fact], persona: Persona, *, white: str, black: str, result: str
) -> list[Message]:
    """The full message list for one persona's report generation call."""
    contract = (
        _OUTPUT_CONTRACT_SELF_LEARNER if persona == Persona.SELF_LEARNER else _OUTPUT_CONTRACT
    )
    system = f"{_SYSTEM_PROMPTS[persona]}\n\n{contract}"
    facts_json = json.dumps([asdict(f) for f in facts], indent=2)
    user = (
        f"Game: {white} vs {black} ({result})\n\n"
        f"FACTS (the only things you may reference):\n{facts_json}"
    )
    return [Message(role="system", content=system), Message(role="user", content=user)]


__all__ = ["build_messages"]
