"""LLM-as-judge rubric for persona tone fidelity (Phase 16, `evaluation-strategy.md`).

Distinct from — and deliberately layered on top of, not replacing — `critic.py`'s
structural grounding checks. The critic answers "did this text reference only real
facts"; nothing before this module ever asked "does this text actually *sound* like the
persona it claims to be." Rule 9 (`claude.md`) requires personas differ only in framing,
depth, and tone, never in truth — the critic already guards truth; this guards framing
and tone, the half of that rule with no scored metric until now.

A second, judge-scoped LLM call per generation, not a heuristic regex the way the
critic's kid-safety centipawn check is — tone and register are exactly the kind of
judgment a keyword search cannot reliably make (`persona-matrix.md`'s "direct,
second-person" vs. "technical, third-person" distinction is about register, not any
single detectable token).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.db.models import Persona
from app.integrations.llm.base import CompletionRequest, LLMProvider, Message

_RUBRIC: dict[Persona, str] = {
    Persona.SELF_LEARNER: (
        "Rubric for the self-learner persona (persona-matrix.md): the text should "
        "address the player directly in second person ('you'/'your'), in a direct, "
        "encouraging tone. Centipawn values and engine terminology are acceptable."
    ),
    Persona.COACH: (
        "Rubric for the coach persona (persona-matrix.md): the text should refer to "
        "the player in third person as 'the student', use precise, technical chess "
        "language, and read like notes a coach would prepare for a lesson."
    ),
    Persona.KID: (
        "Rubric for the kid persona (persona-matrix.md), a young player aged 8-14: "
        "the text should use short, simple sentences, sound encouraging and never "
        "harsh or clinical, and must not mention centipawn values or dense engine "
        "terminology."
    ),
}

_OUTPUT_CONTRACT = (
    "You are judging tone and persona fidelity only — never chess correctness, which "
    "is out of scope for this rubric. Respond with a single JSON object and nothing "
    "else, matching exactly this shape:\n"
    '{"person_correct": <bool>, "tone_appropriate": <bool>, '
    '"reading_level_appropriate": <bool>, "notes": "<one sentence>"}'
)


@dataclass(frozen=True)
class ToneJudgeResult:
    person_correct: bool
    tone_appropriate: bool
    reading_level_appropriate: bool
    notes: str

    @property
    def passed(self) -> bool:
        return self.person_correct and self.tone_appropriate and self.reading_level_appropriate


def _extract_judged_text(content: dict[str, object]) -> str:
    """The prose a tone judgment actually applies to — `summary` plus every finding's
    `text` and every recommendation, never the raw fact ids or numeric fields a
    generated report also carries, which have no "tone" of their own to judge."""
    parts = [str(content.get("summary", ""))]
    findings = content.get("findings", [])
    if isinstance(findings, list):
        parts.extend(str(f.get("text", "")) for f in findings if isinstance(f, dict))
    recommendations = content.get("recommendations", [])
    if isinstance(recommendations, list):
        parts.extend(str(r) for r in recommendations)
    return "\n".join(p for p in parts if p)


async def judge_tone(
    llm: LLMProvider, persona: Persona, content: dict[str, object]
) -> ToneJudgeResult:
    text = _extract_judged_text(content)
    messages = [
        Message(role="system", content=f"{_RUBRIC[persona]}\n\n{_OUTPUT_CONTRACT}"),
        Message(role="user", content=text),
    ]
    response = await llm.complete(
        CompletionRequest(messages=messages, response_format="json_object")
    )
    try:
        parsed = json.loads(response.content)
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    return ToneJudgeResult(
        person_correct=bool(parsed.get("person_correct", False)),
        tone_appropriate=bool(parsed.get("tone_appropriate", False)),
        reading_level_appropriate=bool(parsed.get("reading_level_appropriate", False)),
        notes=str(parsed.get("notes", "")),
    )


__all__ = ["ToneJudgeResult", "judge_tone"]
