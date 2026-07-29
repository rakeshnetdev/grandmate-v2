"""Unit tests for the pure scoring functions in
`evals/harness/classifier_accuracy_eval.py` (Phase 16, D-033) — no DB, no engine
process. `sample_moves`/`score_against_deep_engine` need a live Postgres and a real
Stockfish binary and were exercised directly against the dev environment; what's tested
here is the part with real branching logic: detection F1, per-class metrics, and the
negative control's ability to actually fail."""

from __future__ import annotations

from app.db.models import MoveClassification
from evals.harness.classifier_accuracy_eval import (
    SampledMove,
    ScoredMove,
    _detection_f1,
    _negative_control,
    _per_class_metrics,
    _severity_accuracy,
)


def _scored(ground_truth: MoveClassification, production: MoveClassification) -> ScoredMove:
    sampled = SampledMove(
        game_id="g1",
        ply=0,
        fen_before="startpos",
        played_uci="e2e4",
        production_classification=production,
    )
    return ScoredMove(sampled=sampled, ground_truth_classification=ground_truth, ground_truth_cpl=0)


class TestSeverityAccuracy:
    def test_all_matches_is_perfect_accuracy(self) -> None:
        scored = [_scored(MoveClassification.BEST, MoveClassification.BEST) for _ in range(5)]
        assert _severity_accuracy(scored) == 1.0

    def test_no_matches_is_zero_accuracy(self) -> None:
        scored = [_scored(MoveClassification.BEST, MoveClassification.BLUNDER) for _ in range(5)]
        assert _severity_accuracy(scored) == 0.0

    def test_empty_input_has_no_accuracy_to_report(self) -> None:
        assert _severity_accuracy([]) is None


class TestDetectionF1:
    def test_perfect_agreement_scores_a_perfect_f1(self) -> None:
        scored = [
            _scored(MoveClassification.BLUNDER, MoveClassification.BLUNDER),
            _scored(MoveClassification.BEST, MoveClassification.BEST),
        ]
        result = _detection_f1(scored)
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0

    def test_a_missed_blunder_hurts_recall_not_precision(self) -> None:
        scored = [
            _scored(MoveClassification.BLUNDER, MoveClassification.BEST),  # false negative
            _scored(MoveClassification.BEST, MoveClassification.BEST),  # true negative
        ]
        result = _detection_f1(scored)
        assert result["recall"] == 0.0

    def test_a_false_alarm_hurts_precision_not_recall(self) -> None:
        scored = [
            _scored(MoveClassification.BEST, MoveClassification.MISTAKE),  # false positive
            _scored(MoveClassification.BLUNDER, MoveClassification.BLUNDER),  # true positive
        ]
        result = _detection_f1(scored)
        assert result["precision"] == 0.5
        assert result["recall"] == 1.0

    def test_good_and_inaccuracy_sit_on_opposite_sides_of_the_notable_boundary(self) -> None:
        # GOOD is not notable, INACCURACY is — this is the actual production/glossary
        # boundary the detection metric is built around.
        scored = [
            _scored(MoveClassification.INACCURACY, MoveClassification.INACCURACY),
            _scored(MoveClassification.GOOD, MoveClassification.GOOD),
        ]
        result = _detection_f1(scored)
        assert result["f1"] == 1.0


class TestPerClassMetrics:
    def test_reports_support_and_scores_for_every_class(self) -> None:
        scored = [_scored(MoveClassification.BEST, MoveClassification.BEST)]
        per_class = _per_class_metrics(scored)
        assert set(per_class.keys()) == {c.value for c in MoveClassification}
        assert per_class["best"]["support"] == 1
        assert per_class["best"]["f1"] == 1.0

    def test_a_class_with_no_ground_truth_examples_has_no_recall(self) -> None:
        scored = [_scored(MoveClassification.BEST, MoveClassification.BEST)]
        per_class = _per_class_metrics(scored)
        assert per_class["blunder"]["support"] == 0
        assert per_class["blunder"]["recall"] is None


class TestNegativeControl:
    def test_scrambling_ground_truth_can_make_a_perfect_run_fail(self) -> None:
        # The real point of a negative control: prove the metric is capable of
        # reporting something other than a perfect score, not just that it CAN produce
        # a low number by construction — see the module docstring.
        scored = [
            _scored(cls, cls)
            for cls in (
                MoveClassification.BEST,
                MoveClassification.GOOD,
                MoveClassification.INACCURACY,
                MoveClassification.MISTAKE,
                MoveClassification.BLUNDER,
            )
        ]
        assert _severity_accuracy(scored) == 1.0

        scrambled = _negative_control(scored, seed=1)
        scrambled_accuracy = _severity_accuracy(scrambled)

        assert scrambled_accuracy is not None
        assert scrambled_accuracy < 1.0

    def test_negative_control_preserves_the_original_production_labels(self) -> None:
        scored = [_scored(MoveClassification.BLUNDER, MoveClassification.MISTAKE)]
        scrambled = _negative_control(scored, seed=1)
        assert scrambled[0].sampled.production_classification == MoveClassification.MISTAKE
