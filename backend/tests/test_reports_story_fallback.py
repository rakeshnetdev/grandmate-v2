"""Unit tests for `domain/reports/story_fallback.py` (Phase 16b)."""

from __future__ import annotations

from app.domain.reports.facts import Fact
from app.domain.reports.story_fallback import build_story_fallback_report

_SUMMARY = Fact(
    id="summary",
    kind="summary",
    severity="info",
    ply=None,
    confidence=None,
    data={"accuracy": 75.0},
)
_OPENING = Fact(
    id="opening",
    kind="opening",
    severity="info",
    ply=6,
    confidence=None,
    data={"eco": "C60", "opening_name": "Ruy Lopez", "matched_ply": 6},
)
_PHASE_OPENING = Fact(
    id="phase-opening",
    kind="phase",
    severity="info",
    ply=0,
    confidence=None,
    data={
        "phase": "opening",
        "ply_start": 0,
        "ply_end": 5,
        "white_counts": {"best": 3},
        "black_counts": {"good": 2, "inaccuracy": 1},
    },
)
_MISTAKE = Fact(
    id="move-10",
    kind="move",
    severity="critical",
    ply=10,
    confidence=None,
    data={"ply": 10, "side": "black", "classification": "blunder", "san": "Qh3"},
)


class TestBuildStoryFallbackReport:
    def test_produces_a_phase_finding_tagged_with_its_phase_name(self) -> None:
        report = build_story_fallback_report([_SUMMARY, _OPENING, _PHASE_OPENING])
        opening_finding = next(f for f in report["findings"] if f["kind"] == "opening")
        assert opening_finding["fact_ids"] == ["phase-opening"]
        assert "Ruy Lopez" in opening_finding["text"]

    def test_produces_lesson_findings_from_mistake_tier_moves(self) -> None:
        report = build_story_fallback_report([_SUMMARY, _MISTAKE])
        lesson_finding = next(f for f in report["findings"] if f["kind"] == "lesson")
        assert lesson_finding["fact_ids"] == ["move-10"]
        assert "Qh3" in lesson_finding["text"]

    def test_no_phase_facts_means_no_phase_findings(self) -> None:
        report = build_story_fallback_report([_SUMMARY])
        assert report["findings"] == []

    def test_missing_summary_fact_does_not_crash(self) -> None:
        report = build_story_fallback_report([])
        assert report["summary"] == "No summary available."
