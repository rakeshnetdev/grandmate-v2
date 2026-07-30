"""Builds the LLM prompt for the full game-story report (Phase 16b).

Self-learner only, per the owner's scope decision. Reuses the same fact_id-grounded JSON
contract shape `prompts.py` established for the "game" findings-format report — a
different `kind` vocabulary (opening/middlegame/endgame/lesson instead of strength/
mistake), so the existing critic mechanism and frontend section-grouping pattern both
generalize (see `critic.py`) without new machinery.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from app.domain.reports.facts import Fact
from app.integrations.llm.base import Message

BASE_SYSTEM_PROMPT = (
    "You are a chess coach writing the complete story of one game for the player to read alone.\n"
    "Use only the provided FACTS.\n"
    "Do not invent moves, fact_ids, evaluations, motifs, or move numbers.\n"
    "Every claim must be grounded in the FACTS.\n"
    "Write a coherent story of how the game unfolded, then end with practical lessons."
)

STORY_GUIDE = (
    "Audience: an adult, chess-literate player.\n"
    "Describe both sides' play, not just one player.\n"
    "Name both players by color (White/Black) or name.\n"
    'Never say "you" or "your".\n'
    "Use concrete chess language: opening development, tempo, tactics, king safety, initiative, conversion, and endgame technique.\n"
    "If a phase has nothing specific to say, omit that finding rather than padding it."
)

OUTPUT_CONTRACT = """
Respond with a single JSON object and nothing else.

Shape:
{
  "summary": "<1-2 sentence overall result>",
  "findings": [
    {
      "fact_ids": ["<id>", "..."],
      "kind": "opening" or "middlegame" or "endgame" or "lesson",
      "text": "<prose>"
    }
  ],
  "recommendations": ["<prose>"]
}

Rules:
- Every fact_id you use MUST come from the FACTS list below, copied exactly.
- Every finding must reference at least one real fact_id.
- Every finding's kind is REQUIRED and must be exactly one of "opening", "middlegame", "endgame", "lesson".
- Use only the facts given. Do not invent a move, evaluation, motif, or phase that is not in FACTS.
- The opening finding should describe the opening name if present and how the opening actually went.
- Middlegame findings should explain the key turning points and tactical/strategic shifts.
- Endgame findings should only appear if the facts include an endgame phase.
- Lesson findings should give concrete takeaways for the player's own side specifically, tied to earlier facts.
- Keep the whole response concise and readable.
""".strip()


def build_story_messages(
    facts: list[Fact], *, white: str, black: str, result: str, focus_color: str | None
) -> list[Message]:
    system = f"{BASE_SYSTEM_PROMPT}\n\n{STORY_GUIDE}\n\n{OUTPUT_CONTRACT}"
    facts_json = json.dumps([asdict(f) for f in facts], indent=2)
    focus_note = (
        f"The player this story is being written for played {focus_color}."
        if focus_color is not None
        else "Which side the player is is not known for this game — describe both sides neutrally."
    )
    user = (
        f"Game: {white} vs {black} ({result})\n"
        f"{focus_note}\n\n"
        "FACTS (the only things you may reference):\n"
        f"{facts_json}"
    )
    return [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]


__all__ = ["build_story_messages"]
