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
    """Generic grounding mechanics (fact_id checks, cap enforcement, JSON shape) —
    exercised via SELF_LEARNER with report_kind="training" so these keep testing the
    original Phase 9 behaviour untouched by the Phase 16a self-learner-only game format
    (see TestSelfLearnerGameFormat below for that)."""

    def test_a_well_formed_grounded_report_passes(self) -> None:
        parsed = {
            "summary": "A close game.",
            "findings": [{"fact_ids": ["move-4"], "text": "You blundered on move 4."}],
            "recommendations": ["Review move 4."],
        }
        violations = validate_report(
            parsed, _FACTS, Persona.SELF_LEARNER, _settings(), report_kind="training"
        )
        assert violations == []

    def test_a_reference_to_an_unknown_fact_id_fails(self) -> None:
        parsed = {
            "summary": "A close game.",
            "findings": [{"fact_ids": ["move-999"], "text": "..."}],
            "recommendations": [],
        }
        violations = validate_report(
            parsed, _FACTS, Persona.SELF_LEARNER, _settings(), report_kind="training"
        )
        assert any("move-999" in v for v in violations)

    def test_a_finding_with_no_fact_ids_fails(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [{"fact_ids": [], "text": "..."}],
            "recommendations": [],
        }
        violations = validate_report(
            parsed, _FACTS, Persona.SELF_LEARNER, _settings(), report_kind="training"
        )
        assert violations

    def test_a_finding_with_no_text_fails(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [{"fact_ids": ["move-4"], "text": "  "}],
            "recommendations": [],
        }
        violations = validate_report(
            parsed, _FACTS, Persona.SELF_LEARNER, _settings(), report_kind="training"
        )
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
        violations = validate_report(
            parsed, _FACTS, Persona.SELF_LEARNER, settings, report_kind="training"
        )
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


_MISTAKE_FACT = Fact(
    id="move-4",
    kind="move",
    severity="critical",
    ply=4,
    confidence=None,
    data={"classification": "blunder"},
)
_STRENGTH_FACT = Fact(
    id="move-6",
    kind="move",
    severity="notable",
    ply=6,
    confidence=None,
    data={"classification": "best"},
)


class TestSelfLearnerGameFormat:
    """Phase 16a, D-035 addendum: the self-learner-only game-review format's rules —
    report_kind defaults to "game", so these don't need to pass it explicitly."""

    def test_a_well_formed_report_with_kind_tags_passes(self) -> None:
        parsed = {
            "summary": "White pushed a strong attack; Black blundered late.",
            "findings": [
                {
                    "fact_ids": ["move-6"],
                    "text": "White's move 6 was best.",
                    "kind": "strength",
                },
                {
                    "fact_ids": ["move-4"],
                    "text": "Black's move 4 was a blunder.",
                    "kind": "mistake",
                },
            ],
            "recommendations": ["Review Black's move 4."],
        }
        violations = validate_report(
            parsed, [_MISTAKE_FACT, _STRENGTH_FACT], Persona.SELF_LEARNER, _settings()
        )
        assert violations == []

    def test_a_finding_missing_kind_fails(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [{"fact_ids": ["move-4"], "text": "Black's move 4 was a blunder."}],
            "recommendations": [],
        }
        violations = validate_report(parsed, [_MISTAKE_FACT], Persona.SELF_LEARNER, _settings())
        assert any("kind" in v for v in violations)

    def test_a_strength_kind_on_a_non_best_fact_fails(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [
                {
                    "fact_ids": ["move-4"],
                    "text": "Black's move 4 was a blunder.",
                    "kind": "strength",
                }
            ],
            "recommendations": [],
        }
        violations = validate_report(parsed, [_MISTAKE_FACT], Persona.SELF_LEARNER, _settings())
        assert any("strength" in v for v in violations)

    def test_a_mistake_kind_on_a_best_fact_fails(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [
                {"fact_ids": ["move-6"], "text": "White's move 6 was best.", "kind": "mistake"}
            ],
            "recommendations": [],
        }
        violations = validate_report(parsed, [_STRENGTH_FACT], Persona.SELF_LEARNER, _settings())
        assert any("mistake" in v for v in violations)

    def test_style_rules_are_left_to_the_prompt_not_enforced_here(self) -> None:
        """Second person and engine numbers are style, and style is the prompt's job:
        when the self-learner prompt stopped stating those rules, enforcing them here
        only burned both LLM attempts and forced the deterministic fallback. Kid's own
        centipawn ban is different — a `persona-matrix.md` safety rule — and is still
        enforced (see `TestValidateReport`)."""
        parsed = {
            "summary": "Your game had a rough patch — you lost 320 centipawns on move 4.",
            "findings": [
                {"fact_ids": ["move-4"], "text": "Black's move 4 was a blunder.", "kind": "mistake"}
            ],
            "recommendations": [],
        }
        violations = validate_report(parsed, [_MISTAKE_FACT], Persona.SELF_LEARNER, _settings())
        assert violations == []

    def test_the_split_cap_is_positive_plus_mistake_max(self) -> None:
        settings = _settings(report_self_learner_positive_max=1, report_self_learner_mistake_max=1)
        parsed = {
            "summary": "...",
            "findings": [
                {"fact_ids": ["move-6"], "text": "Best move.", "kind": "strength"},
                {"fact_ids": ["move-4"], "text": "Blunder.", "kind": "mistake"},
                {"fact_ids": ["move-4"], "text": "Another one.", "kind": "mistake"},
            ],
            "recommendations": [],
        }
        violations = validate_report(
            parsed, [_MISTAKE_FACT, _STRENGTH_FACT], Persona.SELF_LEARNER, settings
        )
        assert any("exceeds" in v for v in violations)

    def test_training_report_kind_is_unaffected_by_the_game_format_rules(self) -> None:
        """A training-plan self-learner report (Phase 15) never had a `kind` field or a
        second-person ban — report_kind="training" must keep exempting it."""
        parsed = {
            "summary": "Your training plan for this window.",
            "findings": [{"fact_ids": ["move-4"], "text": "You should review this."}],
            "recommendations": [],
        }
        violations = validate_report(
            parsed, [_MISTAKE_FACT], Persona.SELF_LEARNER, _settings(), report_kind="training"
        )
        assert violations == []


_REPEAT_FACT = Fact(
    id="repeat-motif-hanging_piece", kind="repeat", severity="notable", ply=0, confidence=None
)
_IMPROVEMENT_FACT = Fact(
    id="improved-motif-fork", kind="improvement", severity="notable", ply=None, confidence=None
)
_VERDICT_FACT = Fact(
    id="verdict-accuracy", kind="verdict", severity="info", ply=None, confidence=None
)
_FEEDBACK_FACTS = [_REPEAT_FACT, _IMPROVEMENT_FACT, _VERDICT_FACT]


class TestPatternFeedbackFormat:
    """Phase 19's format rules. The check that matters is the last one: a model must not
    be able to turn "this happened again" into "you have fixed this"."""

    def test_a_well_formed_feedback_report_passes(self) -> None:
        parsed = {
            "summary": "Better than usual, same old habit.",
            "findings": [
                {
                    "fact_ids": ["repeat-motif-hanging_piece"],
                    "kind": "repeated",
                    "text": "You hung a piece again.",
                },
                {
                    "fact_ids": ["improved-motif-fork"],
                    "kind": "improved",
                    "text": "No missed forks this game.",
                },
                {
                    "fact_ids": ["verdict-accuracy"],
                    "kind": "verdict",
                    "text": "Above your recent average.",
                },
            ],
            "recommendations": [],
        }
        violations = validate_report(
            parsed,
            _FEEDBACK_FACTS,
            Persona.SELF_LEARNER,
            _settings(),
            report_kind="pattern_feedback",
        )
        assert violations == []

    def test_a_kind_from_another_report_format_fails(self) -> None:
        parsed = {
            "summary": "...",
            "findings": [
                {"fact_ids": ["repeat-motif-hanging_piece"], "kind": "mistake", "text": "..."}
            ],
            "recommendations": [],
        }
        violations = validate_report(
            parsed,
            _FEEDBACK_FACTS,
            Persona.SELF_LEARNER,
            _settings(),
            report_kind="pattern_feedback",
        )
        assert any("invalid or missing kind" in v for v in violations)

    def test_claiming_improvement_from_a_repeat_fact_fails(self) -> None:
        """The damaging hallucination this critic exists to stop: the cited fact says the
        weakness recurred, the prose says it was fixed."""
        parsed = {
            "summary": "...",
            "findings": [
                {
                    "fact_ids": ["repeat-motif-hanging_piece"],
                    "kind": "improved",
                    "text": "You have stopped hanging pieces.",
                }
            ],
            "recommendations": [],
        }
        violations = validate_report(
            parsed,
            _FEEDBACK_FACTS,
            Persona.SELF_LEARNER,
            _settings(),
            report_kind="pattern_feedback",
        )
        assert any("cites no fact of kind improvement" in v for v in violations)
