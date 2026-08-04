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

BASE_SYSTEM_PROMPT = (
    "You are a chess analysis assistant.\n"
    "Use only the provided FACTS.\n"
    "Do not invent moves, fact_ids, evaluations, motifs, or move numbers.\n"
    "Every claim must be grounded in the FACTS.\n"
    "Write concrete chess explanations, not generic advice."
)

PERSONA_GUIDES: dict[Persona, str] = {
    Persona.SELF_LEARNER: (
        "Audience: the player studying their own game.\n"
        "Tone: direct, neutral, practical.\n"
        "Explain why each move was good or bad using chess ideas like development, center, "
        "king safety, tactic, pin, fork, or tempo.\n"
        "Keep the report concise and useful for self-study."
    ),
    Persona.COACH: (
        "Audience: an expert coach preparing a lesson.\n"
        "Tone: technical, concise, peer-to-peer.\n"
        "Explain the strategic and tactical consequences clearly.\n"
        "Use stronger chess terminology and lesson-oriented phrasing.\n"
        "Keep the analysis dense and precise."
    ),
    Persona.KID: (
        "Audience: a young player, roughly 8-14 years old.\n"
        "Tone: encouraging, simple, short sentences.\n"
        "Explain what happened in plain chess language.\n"
        "For each mistake, say what White did and what that allowed Black to do.\n"
        "Keep one idea at a time.\n"
        "Give exactly one simple and actionable recommendation."
    ),
}

OUTPUT_CONTRACTS: dict[Persona, str] = {
    Persona.SELF_LEARNER: """
Respond with a single JSON object and nothing else.

Shape:
{
  "summary": "<1-2 sentence overview>",
  "findings": [
    {
      "fact_ids": ["<id>", "..."],
      "kind": "strength" or "mistake",
      "text": "<concrete chess explanation>"
    }
  ],
  "recommendations": ["<practical study advice>"]
}

Rules:
- Every finding must reference at least one real fact_id from FACTS.
- Every finding must have kind.
- Use only the facts given. Do not invent moves or motifs.
- Strength findings should be based on best/excellent facts.
- Mistake findings should focus on the most instructive errors, not every error.
- Each finding must explain the chess reason, not generic advice.
- Keep recommendations tied to the findings.
""".strip(),
    Persona.COACH: """
Respond with a single JSON object and nothing else.

Shape:
{
  "summary": "<1-2 sentence overview>",
  "findings": [
    {
      "fact_ids": ["<id>", "..."],
      "text": "<technical coaching explanation>"
    }
  ],
  "recommendations": ["<lesson-plan style coaching advice>"]
}

Rules:
- Every finding must reference at least one real fact_id from FACTS.
- Use only the facts given. Do not invent moves or motifs.
- Explain the tactical or strategic consequence of each critical moment.
- Write for an expert coach, not a beginner.
- Keep the report dense, precise, and lesson-useful.
- Keep recommendations specific to training priorities.
""".strip(),
    Persona.KID: """
Respond with a single JSON object and nothing else.

Shape:
{
  "summary": "<1-2 sentence overview>",
  "findings": [
    {
      "fact_ids": ["<id>", "..."],
      "kind": "strength" or "mistake",
      "text": "<simple kid-friendly explanation>"
    }
  ],
  "recommendations": ["<one simple and actionable recommendation>"]
}

Rules:
- Every finding must reference at least one real fact_id from FACTS.
- Every finding must have kind.
- Use only the facts given. Do not invent moves or motifs.
- Keep sentences short and easy to understand.
- Explain what White did and what happened because of it.
- Avoid vague phrases like "do better next time."
- Give exactly one simple and actionable recommendation.
""".strip(),
}


def build_messages(
    facts: list[Fact], persona: Persona, *, white: str, black: str, result: str
) -> list[Message]:
    system = f"{BASE_SYSTEM_PROMPT}\n\n{PERSONA_GUIDES[persona]}\n\n{OUTPUT_CONTRACTS[persona]}"
    facts_json = json.dumps([asdict(f) for f in facts], indent=2)
    user = (
        f"Game: {white} vs {black} ({result})\n\n"
        "FACTS (the only things you may reference):\n"
        f"{facts_json}"
    )
    return [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]


__all__ = ["build_messages"]
