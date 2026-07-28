"""Unit tests for `domain/reports/selection.py`."""

from __future__ import annotations

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.facts import Fact
from app.domain.reports.selection import rank_facts, select_for_persona


def _settings(**overrides: object) -> ReportSettings:
    return ReportSettings(**overrides)  # type: ignore[arg-type]


def _fact(id_: str, severity: str = "notable", confidence: float | None = None) -> Fact:
    return Fact(id=id_, kind="move", severity=severity, ply=0, confidence=confidence)  # type: ignore[arg-type]


class TestRankFacts:
    def test_critical_sorts_before_notable_sorts_before_info(self) -> None:
        facts = [_fact("a", "info"), _fact("b", "critical"), _fact("c", "notable")]
        ranked = rank_facts(facts)
        assert [f.id for f in ranked] == ["b", "c", "a"]

    def test_higher_confidence_sorts_first_within_the_same_severity(self) -> None:
        facts = [
            _fact("low", "notable", confidence=0.5),
            _fact("high", "notable", confidence=0.9),
        ]
        ranked = rank_facts(facts)
        assert [f.id for f in ranked] == ["high", "low"]


class TestSelectForPersona:
    def _facts(self, n: int) -> list[Fact]:
        summary = Fact(id="summary", kind="summary", severity="info", ply=None, confidence=None)
        opening = Fact(id="opening", kind="opening", severity="info", ply=None, confidence=None)
        findings = [
            Fact(id=f"move-{i}", kind="move", severity="notable", ply=i, confidence=None)
            for i in range(n)
        ]
        return [summary, opening, *findings]

    def test_summary_and_opening_are_always_kept(self) -> None:
        selected = select_for_persona(self._facts(0), Persona.KID, _settings())
        ids = {f.id for f in selected}
        assert {"summary", "opening"} <= ids

    def test_self_learner_caps_at_the_configured_max(self) -> None:
        settings = _settings(report_self_learner_max_findings=2)
        selected = select_for_persona(self._facts(5), Persona.SELF_LEARNER, settings)
        findings = [f for f in selected if f.kind == "move"]
        assert len(findings) == 2

    def test_kid_caps_at_the_configured_max(self) -> None:
        settings = _settings(report_kid_max_findings=1)
        selected = select_for_persona(self._facts(5), Persona.KID, settings)
        findings = [f for f in selected if f.kind == "move"]
        assert len(findings) == 1

    def test_coach_is_unbounded(self) -> None:
        selected = select_for_persona(self._facts(20), Persona.COACH, _settings())
        findings = [f for f in selected if f.kind == "move"]
        assert len(findings) == 20

    def test_kid_suppresses_findings_below_the_confidence_floor(self) -> None:
        settings = _settings(report_kid_min_confidence_to_show=0.7, report_kid_max_findings=10)
        facts = [
            Fact(id="summary", kind="summary", severity="info", ply=None, confidence=None),
            Fact(id="low", kind="motif", severity="notable", ply=1, confidence=0.5),
            Fact(id="high", kind="motif", severity="notable", ply=2, confidence=0.9),
        ]
        selected = select_for_persona(facts, Persona.KID, settings)
        ids = {f.id for f in selected}
        assert "low" not in ids
        assert "high" in ids

    def test_findings_without_a_confidence_are_not_suppressed_for_kid(self) -> None:
        # Move facts have confidence=None (the classification itself is the signal, not
        # a confidence score) — the kid floor must not silently drop every move fact.
        settings = _settings(report_kid_min_confidence_to_show=0.9, report_kid_max_findings=10)
        facts = [
            Fact(id="summary", kind="summary", severity="info", ply=None, confidence=None),
            Fact(id="move-1", kind="move", severity="critical", ply=1, confidence=None),
        ]
        selected = select_for_persona(facts, Persona.KID, settings)
        assert any(f.id == "move-1" for f in selected)
