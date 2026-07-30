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

    def test_self_learner_mistakes_cap_at_the_configured_max(self) -> None:
        # None of self._facts()'s move facts are classification="best", so under the
        # new positive/mistake split (Phase 16a, D-035 addendum) they all land in the
        # mistakes pool, capped by report_self_learner_mistake_max — the old, now
        # unused-for-self-learner report_self_learner_max_findings no longer applies here.
        settings = _settings(report_self_learner_mistake_max=2)
        selected = select_for_persona(self._facts(5), Persona.SELF_LEARNER, settings)
        findings = [f for f in selected if f.kind == "move"]
        assert len(findings) == 2

    def test_self_learner_positive_and_mistake_facts_are_capped_independently(self) -> None:
        positive = [
            Fact(
                id=f"move-best-{i}",
                kind="move",
                severity="notable",
                ply=i,
                confidence=None,
                data={"classification": "best"},
            )
            for i in range(4)
        ]
        mistakes = [
            Fact(
                id=f"move-bad-{i}",
                kind="move",
                severity="notable",
                ply=100 + i,
                confidence=None,
                data={"classification": "blunder"},
            )
            for i in range(4)
        ]
        settings = _settings(report_self_learner_positive_max=2, report_self_learner_mistake_max=3)
        selected = select_for_persona(
            [*positive, *mistakes], Persona.SELF_LEARNER, settings
        )
        selected_ids = {f.id for f in selected}
        assert sum(1 for id_ in selected_ids if id_.startswith("move-best-")) == 2
        assert sum(1 for id_ in selected_ids if id_.startswith("move-bad-")) == 3

    def test_coach_never_receives_positive_move_facts(self) -> None:
        """Coach's report is unaffected by the Phase 16a self-learner-only format
        change — it never saw positive move facts before, and still shouldn't."""
        positive = Fact(
            id="move-best-0",
            kind="move",
            severity="notable",
            ply=0,
            confidence=None,
            data={"classification": "best"},
        )
        selected = select_for_persona([positive], Persona.COACH, _settings())
        assert not any(f.id == "move-best-0" for f in selected)

    def test_kid_never_receives_positive_move_facts(self) -> None:
        positive = Fact(
            id="move-best-0",
            kind="move",
            severity="notable",
            ply=0,
            confidence=None,
            data={"classification": "best"},
        )
        selected = select_for_persona([positive], Persona.KID, _settings())
        assert not any(f.id == "move-best-0" for f in selected)

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
