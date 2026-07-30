"""Builds the LLM prompt for one persona's training analysis (Phase 15, D-032).

Same downstream-of-facts discipline `prompts.py` documents for game reports (rule 8 of
`claude.md`): this module only ever sees `Fact` objects and a persona, never
`WeaknessStats` or a `RetrievedChunk` directly. The output contract is identical to game
reports' — `{"summary", "findings", "recommendations"}` with fact_id citations — so the
existing grounding critic (`critic.py::validate_report`) needs no changes to check a
training analysis too.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from app.db.models import Persona
from app.domain.reports.facts import Fact
from app.integrations.llm.base import Message

BASE_SYSTEM_PROMPT = (
    "You are a chess coach writing a training analysis based on many recent games.\n"
    "Use only the provided FACTS.\n"
    "Do not invent moves, fact_ids, openings, weaknesses, motifs, or study material.\n"
    "Every claim must be grounded in the FACTS.\n"
    "Write concrete chess explanations, not generic advice."
)

PERSONA_GUIDES: dict[Persona, str] = {
    Persona.SELF_LEARNER: (
        "Audience: an adult, chess-literate player studying their own recent games.\n"
        "Tone: direct, encouraging, practical.\n"
        "Focus on recurring weaknesses, opening patterns, and what to practise next.\n"
        "Explain chess ideas clearly using plain language."
    ),
    Persona.COACH: (
        "Audience: an expert coach preparing a student training report.\n"
        "Tone: concise, technical, peer-to-peer.\n"
        "Focus on recurring motifs, opening patterns, and assignable training priorities.\n"
        "Use coach-friendly language and lesson framing."
    ),
    Persona.KID: (
        "Audience: a young player, roughly 8-14 years old.\n"
        "Tone: simple, kind, encouraging.\n"
        "Focus on the biggest repeated pattern and one clear thing to practise.\n"
        "Keep sentences short and easy to understand."
    ),
}

OUTPUT_CONTRACT = """
Respond with a single JSON object and nothing else.

Shape:
{
  "summary": "<1-2 sentence overview of the recurring pattern(s)>",
  "findings": [
    {
      "fact_ids": ["<id>", "..."],
      "kind": "strength" or "mistake" or "opening" or "trend",
      "text": "<prose>"
    }
  ],
  "recommendations": ["<prose>"]
}

Rules:
- Every fact_id you use MUST come from the FACTS list below, copied exactly.
- Every finding must reference at least one real fact_id.
- Use only the facts given. Do not invent weaknesses or study material that is not in FACTS.
- Summary should describe the overall pattern across the games.
- Findings should focus on recurring themes, openings, tactical motifs, and repeated errors.
- Recommendations should be concrete and tied to the findings.
- Do not add commentary outside the JSON object.
""".strip()


def build_training_analysis_messages(
    facts: list[Fact],
    persona: Persona,
    *,
    player_name: str,
    window_size: int,
) -> list[Message]:
    system = f"{BASE_SYSTEM_PROMPT}\n\n{PERSONA_GUIDES[persona]}\n\n{OUTPUT_CONTRACT}"
    facts_json = json.dumps([asdict(f) for f in facts], indent=2)

    user = (
        f"Analyze the player's last {window_size} analysed games.\n"
        f"Player: {player_name}\n\n"
        "FACTS (the only things you may reference):\n"
        f"{facts_json}"
    )

    return [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]


__all__ = ["build_training_analysis_messages"]
