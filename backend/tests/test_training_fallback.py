"""Unit tests for `domain/reports/training_fallback.py`."""

from __future__ import annotations

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.critic import validate_report
from app.domain.reports.facts import Fact
from app.domain.reports.training_fallback import build_fallback_training_plan

_WEAKNESS = Fact(
    id="weakness-motif-fork",
    kind="recurring_weakness",
    severity="critical",
    ply=None,
    confidence=0.6,
    data={
        "weakness_kind": "motif",
        "name": "fork",
        "games_with_finding": 6,
        "occurrence_rate": 0.6,
    },
)
_CHUNK = Fact(
    id="chunk-fork-0",
    kind="knowledge_chunk",
    severity="info",
    ply=None,
    confidence=0.8,
    data={"weakness_name": "fork", "content": "A fork attacks two pieces at once."},
)


class TestBuildFallbackTrainingPlan:
    def test_produces_the_same_shape_the_critic_expects(self) -> None:
        plan = build_fallback_training_plan([_WEAKNESS, _CHUNK], Persona.SELF_LEARNER)
        assert set(plan.keys()) == {"summary", "findings", "recommendations"}

    def test_finding_references_the_weakness_and_its_chunks(self) -> None:
        plan = build_fallback_training_plan([_WEAKNESS, _CHUNK], Persona.SELF_LEARNER)
        assert plan["findings"][0]["fact_ids"] == ["weakness-motif-fork", "chunk-fork-0"]

    def test_kid_persona_never_mentions_centipawns(self) -> None:
        plan = build_fallback_training_plan([_WEAKNESS, _CHUNK], Persona.KID)
        violations = validate_report(plan, [_WEAKNESS, _CHUNK], Persona.KID, ReportSettings())
        assert violations == []

    def test_coach_persona_refers_to_the_student_in_third_person(self) -> None:
        plan = build_fallback_training_plan([_WEAKNESS, _CHUNK], Persona.COACH)
        assert "student" in plan["findings"][0]["text"].lower()

    def test_self_learner_persona_addresses_the_player_directly(self) -> None:
        plan = build_fallback_training_plan([_WEAKNESS, _CHUNK], Persona.SELF_LEARNER)
        assert "your" in plan["findings"][0]["text"].lower()

    def test_no_weaknesses_yields_no_findings_or_recommendations(self) -> None:
        plan = build_fallback_training_plan([], Persona.SELF_LEARNER)
        assert plan["findings"] == []
        assert plan["recommendations"] == []
