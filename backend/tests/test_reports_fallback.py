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
_MATE_SWING_MOVE = Fact(
    id="move-19",
    kind="move",
    severity="critical",
    ply=19,
    confidence=None,
    data={
        "ply": 19,
        "classification": "blunder",
        "eval_swing_cp": None,
        "mate_swing": True,
        "best_move_uci": "e2e4",
    },
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

    def test_self_learner_persona_never_uses_second_person(self) -> None:
        """Phase 16a, D-035 addendum: the self-learner game format explicitly forbids
        "you"/"your" — refer to the player as White/Black/name instead."""
        report = build_fallback_report([_SUMMARY, _MOVE], Persona.SELF_LEARNER)
        text = report["findings"][0]["text"].lower()
        assert "your" not in text
        assert "you " not in text
        assert "black's" in text or "white's" in text

    def test_self_learner_findings_are_tagged_with_kind(self) -> None:
        report = build_fallback_report([_SUMMARY, _MOVE], Persona.SELF_LEARNER)
        assert report["findings"][0]["kind"] == "mistake"

    def test_coach_and_kid_findings_have_no_kind_tag(self) -> None:
        coach_report = build_fallback_report([_SUMMARY, _MOVE], Persona.COACH)
        kid_report = build_fallback_report([_SUMMARY, _MOVE], Persona.KID)
        assert "kind" not in coach_report["findings"][0]
        assert "kind" not in kid_report["findings"][0]

    def test_self_learner_mistake_names_the_better_move(self) -> None:
        move = Fact(
            id="move-4",
            kind="move",
            severity="critical",
            ply=4,
            confidence=None,
            data={
                "ply": 4,
                "classification": "blunder",
                "san": "Qxe4",
                "best_move_san": "Nf3",
                "best_move_uci": "g1f3",
            },
        )
        report = build_fallback_report([_SUMMARY, move], Persona.SELF_LEARNER)
        assert "Nf3" in report["findings"][0]["text"]

    def test_self_learner_positive_move_is_tagged_strength(self) -> None:
        move = Fact(
            id="move-6",
            kind="move",
            severity="notable",
            ply=6,
            confidence=None,
            data={"ply": 6, "classification": "best", "san": "Qxe4", "motif": "fork"},
        )
        report = build_fallback_report([_SUMMARY, move], Persona.SELF_LEARNER)
        assert report["findings"][0]["kind"] == "strength"
        assert "Qxe4" in report["findings"][0]["text"]
        assert "best" in report["findings"][0]["text"].lower()
        assert "fork" in report["findings"][0]["text"].lower()

    def test_no_findings_yields_no_recommendations(self) -> None:
        report = build_fallback_report([_SUMMARY], Persona.SELF_LEARNER)
        assert report["findings"] == []
        assert report["recommendations"] == []

    def test_missing_summary_fact_does_not_crash(self) -> None:
        report = build_fallback_report([_MOVE], Persona.SELF_LEARNER)
        assert report["summary"] == "No summary available."

    def test_a_mate_swing_never_prints_a_bogus_centipawn_number(self) -> None:
        """Regression test for the exact user-facing bug: "costing 99470 centipawns"
        came from printing classification.py's mate-score sentinel as if it were a real
        swing. The fallback text must describe the mate transition in words instead."""
        report = build_fallback_report([_SUMMARY, _MATE_SWING_MOVE], Persona.SELF_LEARNER)
        text = report["findings"][0]["text"]
        assert "centipawns" not in text
        assert "forced mate" in text
