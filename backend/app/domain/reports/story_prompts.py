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

_SYSTEM_PROMPT = (
    "You are a chess coach writing the complete story of one game for the player to "
    "read alone — the whole game, not just their own mistakes. Audience: an adult, "
    "chess-literate player. Name both players by color (White/Black) or name; never "
    'say "you" or "your" — which color the player was is given in the game context '
    "below, but describe both sides' play.\n\n"
    "Sections, via `findings[].kind`:\n"
    '- `"opening"`: exactly 1 finding. Name the opening (the `opening` fact, if '
    "present) and how it actually went for both sides — real book theory, a quick "
    "deviation, an early inaccuracy — grounded in the `phase-opening` fact's per-side "
    "move-quality counts and any early move/motif facts. 2-3 sentences.\n"
    '- `"middlegame"`: up to 2 findings, only if a `phase-middlegame` fact exists in '
    "FACTS. The key moments for both sides — tactics landed or missed, whose position "
    "got better and why — grounded in the `phase-middlegame` fact and any move/motif "
    "facts in that ply range. 1-2 sentences each.\n"
    '- `"endgame"`: up to 1 finding, only if a `phase-endgame` fact exists in FACTS — '
    "omit this section entirely if it does not (many games never reach one). How the "
    "endgame was navigated by both sides. 1-2 sentences.\n"
    '- `"lesson"`: up to 3 findings, concrete takeaways for the player\'s own side '
    "specifically, each tied to a real fact named in an earlier section.\n\n"
    "Style:\n"
    "- Every sentence must reference a real fact from FACTS. If a phase has nothing "
    "specific to say, omit that finding rather than padding it out.\n"
    '- Use the exact words "blunder", "mistake", "inaccuracy", "best", '
    '"excellent" for their matching classification when naming a specific move — this '
    "is how the interface highlights them, so do not paraphrase these.\n"
    "- No engine numbers: no centipawn loss, evaluation, or depth. Translate them into "
    "chess ideas instead — a pin, a fork, a weak king, a lost center, a won endgame.\n"
    "- Keep the whole response (summary + all findings + recommendations combined) "
    "under 500 words — a fuller story than a quick report, but still not an essay.\n"
    "- `summary`: 1-2 sentences on the overall result and roughly how it was decided.\n"
    "- `recommendations`: 0-2 concrete next steps, only if there is something specific "
    "worth adding beyond what the lesson findings already said."
)

_OUTPUT_CONTRACT = (
    "Respond with a single JSON object and nothing else, matching exactly this shape:\n"
    '{"summary": "<1-2 sentence overall result>", '
    '"findings": [{"fact_ids": ["<id>", ...], "text": "<prose>", '
    '"kind": "opening" or "middlegame" or "endgame" or "lesson"}, ...], '
    '"recommendations": ["<prose>", ...]}\n\n'
    "Hard rules:\n"
    "- Every fact_id you use MUST come from the FACTS list below, copied exactly. "
    "Never invent a fact_id, a move, an evaluation, or a motif that is not in FACTS.\n"
    "- Every finding must reference at least one real fact_id.\n"
    '- Every finding\'s "kind" is REQUIRED and must be exactly one of "opening", '
    '"middlegame", "endgame", "lesson" — never omit it.\n'
    "- Do not include any fact_id that is not in the FACTS list below.\n"
    "- Do not add commentary outside the JSON object."
)


def build_story_messages(
    facts: list[Fact], *, white: str, black: str, result: str, focus_color: str | None
) -> list[Message]:
    """The full message list for the game-story generation call."""
    system = f"{_SYSTEM_PROMPT}\n\n{_OUTPUT_CONTRACT}"
    facts_json = json.dumps([asdict(f) for f in facts], indent=2)
    focus_note = (
        f"The player this story is being written for played {focus_color}."
        if focus_color is not None
        else "Which side the player is is not known for this game — describe both sides neutrally."
    )
    user = (
        f"Game: {white} vs {black} ({result})\n{focus_note}\n\n"
        f"FACTS (the only things you may reference):\n{facts_json}"
    )
    return [Message(role="system", content=system), Message(role="user", content=user)]


__all__ = ["build_story_messages"]
