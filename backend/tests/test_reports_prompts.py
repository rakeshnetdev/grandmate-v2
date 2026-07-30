"""Unit tests for `domain/reports/prompts.py` (Phase 16a, D-035 addendum): the
self-learner-only format change. Only checks the system prompt text — the JSON
grounding contract itself is already exercised end-to-end via `test_reports_service.py`.
"""

from __future__ import annotations

from app.db.models import Persona
from app.domain.reports.facts import Fact
from app.domain.reports.prompts import build_messages

_FACTS = [Fact(id="summary", kind="summary", severity="info", ply=None, confidence=None)]


def _system_text(persona: Persona) -> str:
    messages = build_messages(_FACTS, persona, white="A", black="B", result="1-0")
    return messages[0].content


class TestSelfLearnerFormat:
    def test_requires_a_kind_field_on_findings(self) -> None:
        assert '"kind"' in _system_text(Persona.SELF_LEARNER)

    def test_forbids_centipawn_numbers(self) -> None:
        text = _system_text(Persona.SELF_LEARNER)
        assert "Show centipawn values" not in text
        assert "No engine numbers" in text

    def test_forbids_second_person_address(self) -> None:
        assert 'Never "you" or "your"' in _system_text(Persona.SELF_LEARNER)

    def test_caps_mistakes_at_three_and_positives_at_two(self) -> None:
        text = _system_text(Persona.SELF_LEARNER)
        assert "up to 2" in text
        assert "3 MOST INSTRUCTIVE" in text


class TestCoachAndKidUnaffected:
    def test_coach_still_shows_centipawn_values(self) -> None:
        """Coach was deliberately kept on its Phase 9 behavior — unbounded, still shows
        engine numbers — the owner chose not to extend the new format to coach."""
        assert "Show centipawn values" in _system_text(Persona.COACH)

    def test_coach_prompt_has_no_kind_field_instruction(self) -> None:
        assert '"kind"' not in _system_text(Persona.COACH)

    def test_kid_prompt_is_unchanged(self) -> None:
        assert '"kind"' not in _system_text(Persona.KID)
        assert "grab a free piece" in _system_text(Persona.KID)
