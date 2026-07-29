"""Unit tests for `evals/harness/tone_judge.py` (Phase 16) — `FakeLLMProvider` scripts
the judge's response, so these are hermetic despite exercising the real prompt-building
and parsing code path."""

from __future__ import annotations

import json

from app.db.models import Persona
from evals.harness.tone_judge import _extract_judged_text, judge_tone
from tests.fake_llm import FakeLLMProvider

_CONTENT = {
    "summary": "A close game.",
    "findings": [{"fact_ids": ["move-4"], "text": "Your move 4 was a blunder."}],
    "recommendations": ["Review move 4."],
}


class TestExtractJudgedText:
    def test_combines_summary_finding_text_and_recommendations(self) -> None:
        text = _extract_judged_text(_CONTENT)
        assert "A close game." in text
        assert "Your move 4 was a blunder." in text
        assert "Review move 4." in text

    def test_tolerates_missing_fields(self) -> None:
        assert _extract_judged_text({}) == ""


class TestJudgeTone:
    async def test_a_passing_judgment_parses_into_a_passing_result(self) -> None:
        response = json.dumps(
            {
                "person_correct": True,
                "tone_appropriate": True,
                "reading_level_appropriate": True,
                "notes": "Direct, second-person, encouraging.",
            }
        )
        llm = FakeLLMProvider(responses=[response])

        result = await judge_tone(llm, Persona.SELF_LEARNER, _CONTENT)

        assert result.passed is True
        assert len(llm.calls) == 1

    async def test_any_failing_dimension_fails_the_whole_judgment(self) -> None:
        response = json.dumps(
            {
                "person_correct": True,
                "tone_appropriate": False,
                "reading_level_appropriate": True,
                "notes": "Too clinical for a kid audience.",
            }
        )
        llm = FakeLLMProvider(responses=[response])

        result = await judge_tone(llm, Persona.KID, _CONTENT)

        assert result.passed is False

    async def test_malformed_json_fails_closed_rather_than_crashing(self) -> None:
        llm = FakeLLMProvider(responses=["not valid json"])

        result = await judge_tone(llm, Persona.COACH, _CONTENT)

        assert result.passed is False
