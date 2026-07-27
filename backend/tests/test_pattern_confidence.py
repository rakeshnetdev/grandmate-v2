"""Confidence corroboration unit tests."""

from __future__ import annotations

from app.db.models import MoveClassification, MoveEvaluation
from app.domain.patterns.confidence import corroborate


def _evaluation(classification: MoveClassification) -> MoveEvaluation:
    return MoveEvaluation(
        ply=0,
        eval_cp=0,
        mate_in=None,
        best_move_uci="e2e4",
        pv=[],
        classification=classification,
        eval_swing_cp=0,
        is_critical_moment=False,
        deep_analyzed=False,
    )


def test_no_evaluation_leaves_confidence_unchanged() -> None:
    assert corroborate(0.8, None) == 0.8


def test_blunder_boosts_confidence() -> None:
    assert corroborate(0.8, _evaluation(MoveClassification.BLUNDER)) == 0.9


def test_mistake_boosts_confidence() -> None:
    assert corroborate(0.8, _evaluation(MoveClassification.MISTAKE)) == 0.9


def test_engine_endorsed_move_lowers_confidence() -> None:
    assert corroborate(0.8, _evaluation(MoveClassification.BEST)) == 0.65


def test_good_or_inaccuracy_leaves_confidence_unchanged() -> None:
    assert corroborate(0.8, _evaluation(MoveClassification.GOOD)) == 0.8
    assert corroborate(0.8, _evaluation(MoveClassification.INACCURACY)) == 0.8


def test_confidence_is_clamped_to_the_unit_interval() -> None:
    assert corroborate(0.95, _evaluation(MoveClassification.BLUNDER)) == 1.0
    assert corroborate(0.05, _evaluation(MoveClassification.BEST)) == 0.0
