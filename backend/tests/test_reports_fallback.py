"""Unit tests for `domain/reports/fallback.py`."""

from __future__ import annotations

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.critic import validate_report
from app.domain.reports.facts import Fact
from app.domain.reports.fallback import build_fallback_report

_SUMMARY = Fact(
    id="summary",
    kind="summary",
    severity="info",
    ply=None,
    confidence=None,
    data={"accuracy": 88.0, "counts": {"best": 8, "blunder": 1}},
)
_MOVE = Fact(
    id="move-4",
    kind="move",
    severity="critical",
    ply=4,
    confidence=None,
    data={"ply": 4, "classification": "blunder", "eval_swing_cp": 320, "best_move_uci": "e2e4"},
)


class TestBuildFallbackReport:
    def test_produces_the_same_shape_the_critic_expects(self) -> None:
        report = build_fallback_report([_SUMMARY, _MOVE], Persona.SELF_LEARNER)
        assert set(report.keys()) == {"summary", "findings", "recommendations"}
        assert isinstance(report["findings"], list)

    def test_every_finding_references_a_real_fact_id(self) -> None:
        report = build_fallback_report([_SUMMARY, _MOVE], Persona.SELF_LEARNER)
        assert report["findings"][0]["fact_ids"] == ["move-4"]

    def test_kid_persona_never_mentions_centipawns(self) -> None:
        # The fallback's own text must itself pass the same critic the LLM path does.
        report = build_fallback_report([_SUMMARY, _MOVE], Persona.KID)
        violations = validate_report(report, [_SUMMARY, _MOVE], Persona.KID, ReportSettings())
        assert violations == []

    def test_coach_persona_refers_to_the_player_in_third_person(self) -> None:
        report = build_fallback_report([_SUMMARY, _MOVE], Persona.COACH)
        assert "student" in report["findings"][0]["text"].lower()

    def test_self_learner_persona_addresses_the_player_directly(self) -> None:
        report = build_fallback_report([_SUMMARY, _MOVE], Persona.SELF_LEARNER)
        assert "your" in report["findings"][0]["text"].lower()

    def test_no_findings_yields_no_recommendations(self) -> None:
        report = build_fallback_report([_SUMMARY], Persona.SELF_LEARNER)
        assert report["findings"] == []
        assert report["recommendations"] == []

    def test_missing_summary_fact_does_not_crash(self) -> None:
        report = build_fallback_report([_MOVE], Persona.SELF_LEARNER)
        assert report["summary"] == "No summary available."
