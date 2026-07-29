"""Builds the LLM prompt for one persona's training plan (Phase 15, D-032).

Same downstream-of-facts discipline `prompts.py` documents for game reports (rule 8 of
`claude.md`): this module only ever sees `Fact` objects and a persona, never
`WeaknessStats` or a `RetrievedChunk` directly. The output contract is identical to game
reports' — `{"summary", "findings", "recommendations"}` with fact_id citations — so the
existing grounding critic (`critic.py::validate_report`) needs no changes to check a
training plan too.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from app.db.models import Persona
from app.domain.reports.facts import Fact
from app.integrations.llm.base import Message

_SYSTEM_PROMPTS: dict[Persona, str] = {
    Persona.SELF_LEARNER: (
        "You are a chess coach writing a training plan for the player, based on "
        "patterns across their recent games — not one specific game. Audience: an "
        "adult, chess-literate player. Each weakness fact names a recurring motif or "
        "theme and how often it showed up; each knowledge_chunk fact is real study "
        "material about that exact weakness. Recommend concrete drills and study "
        "themes grounded in the knowledge_chunk content, not generic advice. Tone: "
        "direct, encouraging, focused on what to practise next."
    ),
    Persona.COACH: (
        "You are writing a training plan for a coach to hand to their student, based "
        "on patterns across the student's recent games. Audience: an adult, "
        "chess-expert coach. Name motifs/themes without re-explaining them — assume "
        "expert knowledge. Recommendations should read as assignable drills and "
        "session talking points, grounded in the knowledge_chunk study material "
        "provided. Refer to the player in the third person as 'the student'."
    ),
    Persona.KID: (
        "You are writing a training plan for a young player, roughly 8-14 years old, "
        "based on patterns across their recent games. Use simple sentences. Never "
        "show raw centipawn numbers or the word 'centipawn'. Pick the single most "
        "important weakness and give exactly one concrete, achievable thing to "
        "practise, grounded in the knowledge_chunk material for that weakness. Tone: "
        "encouraging, never harsh — frame it as an exciting thing to get better at, "
        "not a flaw."
    ),
}

_OUTPUT_CONTRACT = (
    "Respond with a single JSON object and nothing else, matching exactly this shape:\n"
    '{"summary": "<1-2 sentence overview of the recurring pattern(s)>", '
    '"findings": [{"fact_ids": ["<id>", ...], "text": "<prose>"}, ...], '
    '"recommendations": ["<prose>", ...]}\n\n'
    "Hard rules:\n"
    "- Every fact_id you use MUST come from the FACTS list below, copied exactly. "
    "Never invent a fact_id, a weakness, or a piece of study content not in FACTS.\n"
    "- Every finding must reference at least one real fact_id — ideally the "
    "recurring_weakness fact it is about, plus any knowledge_chunk facts backing the "
    "specific drill or study point you recommend for it.\n"
    "- Do not include any fact_id that is not in the FACTS list below.\n"
    "- If a weakness has no knowledge_chunk facts, you may still name it as a finding, "
    "but keep the recommendation general rather than inventing study material for it.\n"
    "- Do not add commentary outside the JSON object."
)


def build_training_messages(
    facts: list[Fact], persona: Persona, *, window_size: int
) -> list[Message]:
    """The full message list for one persona's training-plan generation call."""
    system = f"{_SYSTEM_PROMPTS[persona]}\n\n{_OUTPUT_CONTRACT}"
    facts_json = json.dumps([asdict(f) for f in facts], indent=2)
    user = (
        f"Based on the player's last {window_size} analysed games.\n\n"
        f"FACTS (the only things you may reference):\n{facts_json}"
    )
    return [Message(role="system", content=system), Message(role="user", content=user)]


__all__ = ["build_training_messages"]
