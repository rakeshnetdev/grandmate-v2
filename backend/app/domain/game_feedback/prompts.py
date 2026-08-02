"""Builds the LLM prompt for the pattern-feedback report (Phase 19, D-037).

Self-learner only, like the game story: this report exists to tell a player about their
own habits, and there is no coach or kid framing of "here is what you keep doing" that
does not first need its own product decision about how blunt to be with a child.

The instructions below carry one unusual burden. Every other report describes a single
game, where overstating a claim makes it wrong about one position. This one describes a
*trend*, where overstating a claim makes it wrong about the player — telling someone
they have fixed a weakness they have merely avoided once is worse than saying nothing.
The `sustained` flag is what separates the two, and the contract makes the model's wording
follow it rather than leaving the distinction to tone.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from app.domain.reports.facts import Fact
from app.integrations.llm.base import Message

BASE_SYSTEM_PROMPT = (
    "You are a chess coach reviewing one game against the player's own recent history.\n"
    "Use only the provided FACTS.\n"
    "Do not invent moves, fact_ids, statistics, weaknesses, or trends.\n"
    "Every claim must be grounded in the FACTS."
)

FEEDBACK_GUIDE = """
Audience: an adult, chess-literate player reading about their own play.
Write in the second person — this is about the reader's own games.

The reader is ALREADY LOOKING AT THE NUMBERS. Directly above your text, the screen shows a
table of this game's accuracy, blunder rate and critical moments beside the player's own
averages, and a list of every recurring habit with the moves it happened on. Restating any
of that is wasted words.

So do not quote figures. No percentages, no counts, no "X of your last Y games", no move
numbers. If a sentence's only content is a number, delete it. Say instead what the numbers
MEAN: whether this was a good game by this player's standards, what the recurring habit is
actually costing them, and what it looks like over the board.

Do not list every habit — the list is already on screen. Take the one or two that actually
hurt this player and explain them properly. One well-explained habit beats five named.

Be direct about what recurred. Be careful about what improved:
  - a weakness with "sustained": true may be described as a real improvement or a habit broken;
  - a weakness with "sustained": false is ONLY absent from this one game. Say exactly that.
    Never call it fixed, corrected, solved, or improved.
Do not pad. If nothing repeated, say so in one line rather than inventing a pattern.
""".strip()

OUTPUT_CONTRACT = """
Respond with a single JSON object and nothing else.

Shape:
{
  "summary": "<1-2 sentences, no figures: how this game went by this player's own standards>",
  "findings": [
    {
      "fact_ids": ["<id>", "..."],
      "kind": "repeated" or "improved" or "verdict",
      "text": "<prose>"
    }
  ],
  "recommendations": ["<prose>"]
}

Rules:
- Every fact_id you use MUST come from the FACTS list below, copied exactly.
- Every finding must reference at least one real fact_id.
- Every finding's kind is REQUIRED and must be exactly one of "repeated", "improved", "verdict".
- A "repeated" finding must cite a fact of kind "repeat".
- An "improved" finding must cite a fact of kind "improvement".
- A "verdict" finding must cite a fact of kind "verdict" or "baseline".
- Cite the facts you are drawing on, but do NOT reproduce their numbers in your prose.
- At most one "verdict" finding: say in plain words how this game went for this player,
  not one sentence per metric.
- At most two "repeated" findings, however many repeat facts you are given.
- Recommendations should follow from what actually repeated in this game, and should be
  something the player can do at the board — not "improve your accuracy".
- Keep the whole response concise.
""".strip()


def build_feedback_messages(
    facts: list[Fact], *, white: str, black: str, result: str, baseline_games: int
) -> list[Message]:
    system = f"{BASE_SYSTEM_PROMPT}\n\n{FEEDBACK_GUIDE}\n\n{OUTPUT_CONTRACT}"
    facts_json = json.dumps([asdict(f) for f in facts], indent=2)
    user = (
        f"Game: {white} vs {black} ({result})\n"
        f"Compared against the player's previous {baseline_games} analyzed games.\n\n"
        "FACTS (the only things you may reference):\n"
        f"{facts_json}"
    )
    return [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]


__all__ = ["build_feedback_messages"]
