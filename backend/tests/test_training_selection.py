"""Unit tests for `domain/reports/training_selection.py`."""

from __future__ import annotations

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.facts import Fact
from app.domain.reports.training_selection import rank_weaknesses, select_training_facts


def _settings(**overrides: object) -> ReportSettings:
    return ReportSettings(**overrides)  # type: ignore[arg-type]


def _weakness(
    id_: str, name: str, severity: str = "notable", confidence: float = 0.4, recently: bool = False
) -> Fact:
    return Fact(
        id=id_,
        kind="recurring_weakness",
        severity=severity,  # type: ignore[arg-type]
        ply=None,
        confidence=confidence,
        data={"name": name, "recently_recommended": recently},
    )


def _chunk(id_: str, weakness_name: str) -> Fact:
    return Fact(
        id=id_,
        kind="knowledge_chunk",
        severity="info",
        ply=None,
        confidence=0.5,
        data={"weakness_name": weakness_name, "content": "x"},
    )


class TestRankWeaknesses:
    def test_not_recently_recommended_sorts_before_recently_recommended(self) -> None:
        fresh = _weakness("a", "fork", recently=False)
        stale = _weakness("b", "pin", recently=True)
        ranked = rank_weaknesses([stale, fresh])
        assert [f.id for f in ranked] == ["a", "b"]

    def test_critical_sorts_before_notable_within_the_same_recency(self) -> None:
        notable = _weakness("a", "fork", severity="notable")
        critical = _weakness("b", "pin", severity="critical")
        ranked = rank_weaknesses([notable, critical])
        assert [f.id for f in ranked] == ["b", "a"]

    def test_higher_occurrence_rate_sorts_first_within_the_same_severity(self) -> None:
        low = _weakness("a", "fork", confidence=0.3)
        high = _weakness("b", "pin", confidence=0.9)
        ranked = rank_weaknesses([low, high])
        assert [f.id for f in ranked] == ["b", "a"]


class TestSelectTrainingFacts:
    def test_self_learner_caps_at_the_configured_max(self) -> None:
        weaknesses = [_weakness(f"w{i}", f"name{i}") for i in range(5)]
        settings = _settings(report_self_learner_max_findings=2)
        selected = select_training_facts(weaknesses, Persona.SELF_LEARNER, settings)
        assert len([f for f in selected if f.kind == "recurring_weakness"]) == 2

    def test_coach_is_unbounded(self) -> None:
        weaknesses = [_weakness(f"w{i}", f"name{i}") for i in range(10)]
        selected = select_training_facts(weaknesses, Persona.COACH, _settings())
        assert len([f for f in selected if f.kind == "recurring_weakness"]) == 10

    def test_a_weakness_is_never_dropped_outright_for_being_recently_recommended(self) -> None:
        # Recently-recommended weaknesses rank behind fresh ones but must still be
        # selectable when the persona cap has room, since they remain true (D-032).
        weaknesses = [_weakness("stale", "fork", recently=True)]
        settings = _settings(report_self_learner_max_findings=5)
        selected = select_training_facts(weaknesses, Persona.SELF_LEARNER, settings)
        assert any(f.data["name"] == "fork" for f in selected)

    def test_chunks_for_excluded_weaknesses_are_not_selected(self) -> None:
        weaknesses = [_weakness(f"w{i}", f"name{i}") for i in range(3)]
        chunks = [_chunk("c0", "name0"), _chunk("c1", "name1"), _chunk("c2", "name2")]
        settings = _settings(report_self_learner_max_findings=1)
        selected = select_training_facts(weaknesses + chunks, Persona.SELF_LEARNER, settings)
        selected_weakness_names = {
            f.data["name"] for f in selected if f.kind == "recurring_weakness"
        }
        chunk_weaknesses = {
            f.data["weakness_name"] for f in selected if f.kind == "knowledge_chunk"
        }
        assert chunk_weaknesses <= selected_weakness_names
        assert len(selected_weakness_names) == 1
