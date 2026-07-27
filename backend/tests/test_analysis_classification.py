"""Move classification unit tests: centipawn loss and the five-category label.

Pure — no engine, no database. `EngineEvaluation` instances are built directly.
"""

from __future__ import annotations

from app.core.config import EngineSettings
from app.db.models import MoveClassification
from app.domain.analysis.classification import classify_move, compute_cpl
from app.integrations.engine import EngineEvaluation


def _eval(
    cp: int | None = None, mate: int | None = None, best: str | None = "e2e4"
) -> EngineEvaluation:
    return EngineEvaluation(eval_cp=cp, mate_in=mate, best_move_uci=best, pv=[best] if best else [])


class TestComputeCpl:
    def test_no_loss_when_eval_is_unchanged(self) -> None:
        # Before: +50 for the mover. After: -50 for the opponent (their turn now),
        # which is +50 back in the mover's frame — no loss.
        cpl = compute_cpl(_eval(cp=50), _eval(cp=-50))
        assert cpl == 0

    def test_loss_when_eval_drops(self) -> None:
        # Before: +50 for the mover. After: +20 for the opponent (their turn), i.e. -20
        # in the mover's frame — a 70cp swing against them.
        cpl = compute_cpl(_eval(cp=50), _eval(cp=20))
        assert cpl == 70

    def test_never_negative(self) -> None:
        # A move that improves on the engine's own assessment of the starting position
        # cannot happen against optimal defense — clamped to 0, not left negative.
        cpl = compute_cpl(_eval(cp=20), _eval(cp=-50))
        assert cpl == 0

    def test_mate_for_me_to_losing_is_a_huge_swing(self) -> None:
        cpl = compute_cpl(_eval(mate=3), _eval(cp=0))
        assert cpl > 50_000

    def test_missing_a_mate_and_walking_into_one_is_a_huge_swing(self) -> None:
        cpl = compute_cpl(_eval(cp=0), _eval(mate=2))
        assert cpl > 50_000


class TestClassifyMove:
    def test_exact_best_move_is_best_regardless_of_cpl(self) -> None:
        """Guards the special case: a real top-choice move must never fall into GOOD
        over evaluation noise between two separate engine calls."""
        settings = EngineSettings()
        label = classify_move(played_uci="e2e4", best_move_uci="e2e4", cpl=5, settings=settings)
        assert label == MoveClassification.BEST

    def test_zero_loss_but_different_move_is_good_not_best(self) -> None:
        settings = EngineSettings()
        label = classify_move(played_uci="d2d4", best_move_uci="e2e4", cpl=0, settings=settings)
        assert label == MoveClassification.GOOD

    def test_boundaries_use_configured_thresholds(self) -> None:
        settings = EngineSettings(inaccuracy_cp=50, mistake_cp=100, blunder_cp=300)

        assert (
            classify_move(played_uci="a", best_move_uci="b", cpl=49, settings=settings)
            == MoveClassification.GOOD
        )
        assert (
            classify_move(played_uci="a", best_move_uci="b", cpl=50, settings=settings)
            == MoveClassification.INACCURACY
        )
        assert (
            classify_move(played_uci="a", best_move_uci="b", cpl=99, settings=settings)
            == MoveClassification.INACCURACY
        )
        assert (
            classify_move(played_uci="a", best_move_uci="b", cpl=100, settings=settings)
            == MoveClassification.MISTAKE
        )
        assert (
            classify_move(played_uci="a", best_move_uci="b", cpl=299, settings=settings)
            == MoveClassification.MISTAKE
        )
        assert (
            classify_move(played_uci="a", best_move_uci="b", cpl=300, settings=settings)
            == MoveClassification.BLUNDER
        )

    def test_thresholds_are_read_from_settings_not_hardcoded(self) -> None:
        """A magic-number regression check: tightening the config must actually tighten
        classification, proving the thresholds are not baked into the function."""
        loose = EngineSettings(inaccuracy_cp=200)
        tight = EngineSettings(inaccuracy_cp=10)

        assert (
            classify_move(played_uci="a", best_move_uci="b", cpl=50, settings=loose)
            == MoveClassification.GOOD
        )
        assert (
            classify_move(played_uci="a", best_move_uci="b", cpl=50, settings=tight)
            == MoveClassification.INACCURACY
        )

    def test_no_best_move_available_never_matches(self) -> None:
        """A position with no legal moves (checkmate/stalemate) has best_move_uci=None —
        must not spuriously equal a played move via some falsy-comparison bug."""
        settings = EngineSettings()
        label = classify_move(played_uci="e2e4", best_move_uci=None, cpl=0, settings=settings)
        assert label == MoveClassification.GOOD
