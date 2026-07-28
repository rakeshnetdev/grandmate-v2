"""Unit tests for `domain/reports/critic.py`."""

from __future__ import annotations

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.critic import validate_report
from app.domain.reports.facts import Fact

_FACTS = [
    Fact(id="summary", kind="summary", severity="info", ply=None, confidence=None),
    Fact(id="move-4", kind="move", severity="critical", ply=4, confidence=None),
]


def _settings(**overrides: object) -> ReportSettings:
    return ReportSettings(**overrides)  # type: ignore[arg-type]


class TestValidateReport:
    def test_a_well_formed_grounded_report_passes(self) -> None:
        parsed = {
            "summary": "A close game.",
            "findings": [{"fact_ids": ["move-4"], "text": "You blundered on move 4."}],
            "recommendations": ["Review move 4."],
        }
        assert validate_report(parsed, _FACTS, Persona.SELF_LEARNER, _settings()) == []

    def test_a_reference_to_an_unknown_fact_id_fails(self) -> None:
        parsed = {
            "summary": "A close game.",
            "findings": [{"fact_ids": ["move-999"], "text": "..."}],
            "recommendations": [],
        }
        violations = validate_report(parsed, _FACTS, Persona.SELF_LEARNER, _settings())
        assert any("move-999" in v for v in violations)

    def test_a_finding_with_no_fact_ids_fails(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [{"fact_ids": [], "text": "..."}],
            "recommendations": [],
        }
        violations = validate_report(parsed, _FACTS, Persona.SELF_LEARNER, _settings())
        assert violations

    def test_a_finding_with_no_text_fails(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [{"fact_ids": ["move-4"], "text": "  "}],
            "recommendations": [],
        }
        violations = validate_report(parsed, _FACTS, Persona.SELF_LEARNER, _settings())
        assert violations

    def test_a_non_dict_response_fails(self) -> None:
        assert validate_report(["not", "a", "dict"], _FACTS, Persona.SELF_LEARNER, _settings())

    def test_missing_findings_key_fails(self) -> None:
        assert validate_report({"summary": "..."}, _FACTS, Persona.SELF_LEARNER, _settings())

    def test_exceeding_the_persona_cap_fails(self) -> None:
        settings = _settings(report_self_learner_max_findings=1)
        parsed = {
            "summary": "...",
            "findings": [
                {"fact_ids": ["move-4"], "text": "one"},
                {"fact_ids": ["move-4"], "text": "two"},
            ],
            "recommendations": [],
        }
        violations = validate_report(parsed, _FACTS, Persona.SELF_LEARNER, settings)
        assert violations

    def test_coach_has_no_finding_cap(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [{"fact_ids": ["move-4"], "text": f"finding {i}"} for i in range(20)],
            "recommendations": [],
        }
        assert validate_report(parsed, _FACTS, Persona.COACH, _settings()) == []

    def test_kid_persona_mentioning_a_centipawn_value_fails(self) -> None:
        parsed = {
            "summary": "You lost 250 centipawns on move 4.",
            "findings": [{"fact_ids": ["move-4"], "text": "..."}],
            "recommendations": [],
        }
        violations = validate_report(parsed, _FACTS, Persona.KID, _settings())
        assert any("centipawn" in v for v in violations)

    def test_kid_persona_plain_language_passes(self) -> None:
        parsed = {
            "summary": "You made a big mistake on move 4 — a chance to learn!",
            "findings": [{"fact_ids": ["move-4"], "text": "Here's your chance to improve!"}],
            "recommendations": ["Try spotting forks before you move."],
        }
        assert validate_report(parsed, _FACTS, Persona.KID, _settings()) == []
