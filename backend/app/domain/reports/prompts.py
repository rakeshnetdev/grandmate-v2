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

_SYSTEM_PROMPTS: dict[Persona, str] = {
    Persona.SELF_LEARNER: (
        "You are a chess coach writing a report for the player about their own game, "
        "for them to read alone. Audience: an adult, chess-literate player studying "
        "their own game. Show centipawn values. Name tactical motifs and briefly "
        "explain them. Tone: direct and neutral. Frame mistakes as costing the "
        "advantage, not as a personal failing. Recommendations should be drills and "
        "study themes, not a lesson plan."
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


def build_messages(
    facts: list[Fact], persona: Persona, *, white: str, black: str, result: str
) -> list[Message]:
    """The full message list for one persona's report generation call."""
    system = f"{_SYSTEM_PROMPTS[persona]}\n\n{_OUTPUT_CONTRACT}"
    facts_json = json.dumps([asdict(f) for f in facts], indent=2)
    user = (
        f"Game: {white} vs {black} ({result})\n\n"
        f"FACTS (the only things you may reference):\n{facts_json}"
    )
    return [Message(role="system", content=system), Message(role="user", content=user)]


__all__ = ["build_messages"]
