"""Unit tests for `domain/game_feedback/comparison.py` (Phase 19).

No database — the comparison functions take already-loaded data by design, same as
`test_analytics_metrics.py`.

The cases here are chosen around the claims that would actually hurt a player if they were
wrong: calling a one-off a pattern, calling a single quiet game a fix, and calling an
ordinary game good or bad on a sample too thin to say.
"""

from __future__ import annotations

import uuid

from app.core.config import GameFeedbackSettings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MotifFinding,
    MotifType,
    MoveClassification,
    MoveEvaluation,
)
from app.domain.analytics.metrics import GameForAnalytics
from app.domain.game_feedback.comparison import compare_game_to_baseline


def _settings(**overrides: object) -> GameFeedbackSettings:
    return GameFeedbackSettings(**overrides)  # type: ignore[arg-type]


def _game(*, focus_color: GameColor | None = GameColor.WHITE, result: str = "1-0") -> Game:
    return Game(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "Player", "Black": "Opponent", "Result": result},
        raw_pgn_path="pgn/test.pgn",
        focus_color=focus_color,
    )


def _analysis(classifications: list[MoveClassification]) -> GameAnalysis:
    """A game whose White (even-ply) moves carry `classifications`. Black's moves are
    always BEST so they can never be mistaken for the player's own contribution."""
    analysis = GameAnalysis(
        id=uuid.uuid4(),
        game_id=uuid.uuid4(),
        analysis_version="test",
        engine_depth=12,
        summary={"total_moves": len(classifications) * 2, "counts": {}, "accuracy": 0.0},
    )
    analysis.evaluations = []
    for index, classification in enumerate(classifications):
        for ply, own in ((index * 2, True), (index * 2 + 1, False)):
            analysis.evaluations.append(
                MoveEvaluation(
                    game_analysis_id=analysis.id,
                    ply=ply,
                    eval_cp=0,
                    mate_in=None,
                    best_move_uci=None,
                    pv=[],
                    classification=classification if own else MoveClassification.BEST,
                    eval_swing_cp=0,
                    is_critical_moment=False,
                    deep_analyzed=False,
                )
            )
    return analysis


def _hanging_piece(analysis: GameAnalysis, ply: int) -> MotifFinding:
    """A hanging-piece finding on White's own move. Self-inflicted motifs only count when
    the same ply was also a mistake or worse, so the caller must classify it that way."""
    return MotifFinding(
        game_analysis_id=analysis.id,
        ply=ply,
        side=GameColor.WHITE,
        motif=MotifType.HANGING_PIECE,
        confidence=0.9,
        evidence={},
    )


def _blundered_game(*, hanging_at: int | None = None) -> GameForAnalytics:
    """A game where the player's move 1 (ply 0) is a blunder, optionally with a hanging
    piece detected at that same ply."""
    analysis = _analysis([MoveClassification.BLUNDER, MoveClassification.BEST])
    motifs = [_hanging_piece(analysis, hanging_at)] if hanging_at is not None else []
    return GameForAnalytics(game=_game(), analysis=analysis, opening=None, motifs=motifs, themes=[])


def _clean_game() -> GameForAnalytics:
    analysis = _analysis([MoveClassification.BEST, MoveClassification.BEST])
    return GameForAnalytics(game=_game(), analysis=analysis, opening=None, motifs=[], themes=[])


class TestBaselineSufficiency:
    def test_thin_baseline_asserts_nothing(self) -> None:
        result = compare_game_to_baseline(
            _blundered_game(hanging_at=0),
            [_blundered_game(hanging_at=0) for _ in range(3)],
            _settings(game_feedback_min_baseline_games=5),
        )
        assert result.sufficient_baseline is False
        # Not merely flagged — genuinely empty, so nothing downstream can render a
        # verdict off a sample the comparison itself considers too thin.
        assert result.repeated == []
        assert result.improved == []
        assert result.metrics == []

    def test_unknown_player_side_is_unattributable(self) -> None:
        target = _blundered_game(hanging_at=0)
        target = GameForAnalytics(
            game=_game(focus_color=None),
            analysis=target.analysis,
            opening=None,
            motifs=target.motifs,
            themes=[],
        )
        result = compare_game_to_baseline(
            target, [_blundered_game(hanging_at=0) for _ in range(6)], _settings()
        )
        assert result.attributable is False
        assert result.repeated == []

    def test_unattributable_baseline_games_are_not_counted_as_clean(self) -> None:
        """A game whose side is unknown must not dilute an occurrence rate."""
        unknown = _clean_game()
        unknown = GameForAnalytics(
            game=_game(focus_color=None),
            analysis=unknown.analysis,
            opening=None,
            motifs=[],
            themes=[],
        )
        prior = [_blundered_game(hanging_at=0) for _ in range(5)] + [unknown] * 5
        result = compare_game_to_baseline(
            _blundered_game(hanging_at=0), prior, _settings(game_feedback_min_baseline_games=5)
        )
        assert result.baseline_games == 5
        assert result.repeated[0].occurrence_rate == 1.0


class TestRepeatedWeaknesses:
    def test_recurring_weakness_present_again_is_reported(self) -> None:
        result = compare_game_to_baseline(
            _blundered_game(hanging_at=0),
            [_blundered_game(hanging_at=0) for _ in range(6)],
            _settings(),
        )
        assert [(r.kind, r.name) for r in result.repeated] == [("motif", "hanging_piece")]
        assert result.repeated[0].occurrence_rate == 1.0
        # Ply 0 is White's first move, which a player calls move 1.
        assert result.repeated[0].plies == [0]

    def test_one_off_in_history_is_not_a_pattern(self) -> None:
        """Present in this game, but rare enough in the baseline that calling it a
        recurring habit would misdescribe the player's history."""
        prior = [_blundered_game(hanging_at=0)] + [_clean_game() for _ in range(9)]
        result = compare_game_to_baseline(
            _blundered_game(hanging_at=0),
            prior,
            _settings(game_feedback_repeat_min_occurrence_rate=0.3),
        )
        assert result.repeated == []

    def test_hanging_piece_on_a_good_move_does_not_count(self) -> None:
        """Polarity rule inherited from analytics: a self-inflicted motif only counts
        against the player when that same move was a mistake or worse."""
        analysis = _analysis([MoveClassification.BEST, MoveClassification.BEST])
        target = GameForAnalytics(
            game=_game(),
            analysis=analysis,
            opening=None,
            motifs=[_hanging_piece(analysis, 0)],
            themes=[],
        )
        result = compare_game_to_baseline(
            target, [_blundered_game(hanging_at=0) for _ in range(6)], _settings()
        )
        assert result.repeated == []
        assert [(i.kind, i.name) for i in result.improved] == [("motif", "hanging_piece")]


class TestImprovement:
    def test_single_clean_game_is_not_called_sustained(self) -> None:
        """The claim this feature most easily gets wrong: one quiet game is an absence,
        not a fix."""
        prior = [_blundered_game(hanging_at=0) for _ in range(6)]
        result = compare_game_to_baseline(
            _clean_game(), prior, _settings(game_feedback_improvement_min_streak=3)
        )
        assert len(result.improved) == 1
        assert result.improved[0].clear_streak == 1
        assert result.improved[0].sustained is False

    def test_streak_of_clean_games_is_sustained(self) -> None:
        # Two clean games immediately before this one, then the habit's history.
        prior = [_clean_game(), _clean_game()] + [_blundered_game(hanging_at=0) for _ in range(6)]
        result = compare_game_to_baseline(
            _clean_game(), prior, _settings(game_feedback_improvement_min_streak=3)
        )
        assert result.improved[0].clear_streak == 3
        assert result.improved[0].sustained is True

    def test_streak_breaks_at_the_most_recent_recurrence(self) -> None:
        """A relapse two games ago must reset the count, not be averaged away."""
        prior = [
            _clean_game(),
            _blundered_game(hanging_at=0),
            _clean_game(),
        ] + [_blundered_game(hanging_at=0) for _ in range(5)]
        result = compare_game_to_baseline(
            _clean_game(), prior, _settings(game_feedback_improvement_min_streak=3)
        )
        assert result.improved[0].clear_streak == 2
        assert result.improved[0].sustained is False


class TestVerdictMetrics:
    def test_better_than_usual_reads_above(self) -> None:
        """A perfect game against a baseline of consistently poor ones."""
        prior = [_blundered_game() for _ in range(6)]
        result = compare_game_to_baseline(_clean_game(), prior, _settings())
        accuracy = next(m for m in result.metrics if m.name == "accuracy")
        assert accuracy.value == 100.0
        assert accuracy.baseline_mean == 50.0
        assert accuracy.band in {"above", "well_above"}

    def test_worse_than_usual_reads_below(self) -> None:
        prior = [_clean_game() for _ in range(5)] + [_blundered_game() for _ in range(1)]
        result = compare_game_to_baseline(_blundered_game(), prior, _settings())
        assert result.overall_band in {"below", "well_below"}

    def test_no_spread_and_no_difference_reads_in_line(self) -> None:
        prior = [_clean_game() for _ in range(6)]
        result = compare_game_to_baseline(_clean_game(), prior, _settings())
        accuracy = next(m for m in result.metrics if m.name == "accuracy")
        assert accuracy.z_score is None
        assert accuracy.band == "in_line"

    def test_no_spread_but_a_real_difference_is_reported_at_the_minimum_tier(self) -> None:
        """Every prior game identical and this one worse: the direction is certain, the
        magnitude is not. It must be neither hidden as "in line" nor overstated as a
        large move, and no z-score may be invented for it."""
        prior = [_clean_game() for _ in range(6)]
        result = compare_game_to_baseline(_blundered_game(), prior, _settings())
        accuracy = next(m for m in result.metrics if m.name == "accuracy")
        assert accuracy.z_score is None
        assert accuracy.band == "below"

    def test_blunder_rate_is_scored_in_the_right_direction(self) -> None:
        """Fewer blunders must read as better, even though the raw number is lower."""
        prior = [_blundered_game() for _ in range(4)] + [_clean_game() for _ in range(2)]
        result = compare_game_to_baseline(_clean_game(), prior, _settings())
        blunders = next(m for m in result.metrics if m.name == "blunder_rate")
        assert blunders.value == 0.0
        assert blunders.z_score is not None and blunders.z_score > 0
