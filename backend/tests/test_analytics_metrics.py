"""Unit tests for the pure aggregation functions in `domain/analytics/metrics.py`.

No database involved — every model instance here is built in memory and never
persisted, which is exactly what these functions are designed to accept (see the
module's own docstring on why they take already-loaded data rather than a session).
"""

from __future__ import annotations

import uuid

from app.core.config import AnalyticsSettings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MotifFinding,
    MotifType,
    MoveClassification,
    MoveEvaluation,
    OpeningMatch,
    StrategicThemeFinding,
    StrategicThemeType,
)
from app.domain.analytics import metrics


def _settings(**overrides: object) -> AnalyticsSettings:
    return AnalyticsSettings(**overrides)  # type: ignore[arg-type]


def _game(
    *,
    focus_color: GameColor | None = GameColor.WHITE,
    result: str = "1-0",
    time_control: str | None = None,
) -> Game:
    headers = {"White": "Player", "Black": "Opponent", "Result": result}
    if time_control is not None:
        headers["TimeControl"] = time_control
    return Game(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers=headers,
        raw_pgn_path="pgn/test.pgn",
        focus_color=focus_color,
    )


def _analysis(
    *, accuracy: float = 90.0, counts: dict[str, int] | None = None, critical_moments: int = 0
) -> GameAnalysis:
    counts = counts or {"best": 1}
    analysis = GameAnalysis(
        id=uuid.uuid4(),
        game_id=uuid.uuid4(),
        analysis_version="test",
        engine_depth=12,
        summary={
            "total_moves": sum(counts.values()),
            "counts": counts,
            "accuracy": accuracy,
            "critical_moments": critical_moments,
        },
    )
    analysis.evaluations = []
    return analysis


def _evaluation(analysis: GameAnalysis, ply: int, classification: MoveClassification) -> None:
    analysis.evaluations.append(
        MoveEvaluation(
            game_analysis_id=analysis.id,
            ply=ply,
            eval_cp=0,
            mate_in=None,
            best_move_uci=None,
            pv=[],
            classification=classification,
            eval_swing_cp=0,
            is_critical_moment=False,
            deep_analyzed=False,
        )
    )


def _opening(name: str) -> OpeningMatch:
    return OpeningMatch(eco="C60", opening_name=name, epd="fen", matched_ply=4)


def _for_analytics(
    game: Game,
    analysis: GameAnalysis,
    *,
    opening: OpeningMatch | None = None,
    motifs: list[MotifFinding] | None = None,
    themes: list[StrategicThemeFinding] | None = None,
) -> metrics.GameForAnalytics:
    return metrics.GameForAnalytics(
        game=game,
        analysis=analysis,
        opening=opening,
        motifs=motifs or [],
        themes=themes or [],
    )


class TestDetermineOutcome:
    def test_unknown_focus_color_is_unknown(self) -> None:
        assert metrics.determine_outcome("1-0", None) == "unknown"

    def test_unresolved_result_is_unknown(self) -> None:
        assert metrics.determine_outcome("*", GameColor.WHITE) == "unknown"

    def test_white_win_from_whites_perspective(self) -> None:
        assert metrics.determine_outcome("1-0", GameColor.WHITE) == "win"

    def test_white_win_from_blacks_perspective(self) -> None:
        assert metrics.determine_outcome("1-0", GameColor.BLACK) == "loss"

    def test_draw(self) -> None:
        assert metrics.determine_outcome("1/2-1/2", GameColor.BLACK) == "draw"


class TestClassifyTimeControl:
    def test_missing_header_is_unknown(self) -> None:
        assert metrics.classify_time_control(None, _settings()) == "unknown"
        assert metrics.classify_time_control("-", _settings()) == "unknown"

    def test_unparseable_header_is_unknown(self) -> None:
        assert metrics.classify_time_control("correspondence", _settings()) == "unknown"

    def test_buckets_by_estimated_duration(self) -> None:
        settings = _settings()
        assert metrics.classify_time_control("60+0", settings) == "bullet"
        assert metrics.classify_time_control("300+0", settings) == "blitz"
        assert metrics.classify_time_control("600+0", settings) == "rapid"
        assert metrics.classify_time_control("1800+0", settings) == "classical"

    def test_increment_counts_toward_estimated_duration(self) -> None:
        # 60 + 40*3 = 180, which is not < the 180 bullet ceiling, so this lands in blitz.
        assert metrics.classify_time_control("60+3", _settings()) == "blitz"


class TestOpeningFamily:
    def test_no_match_is_unclassified(self) -> None:
        assert metrics.opening_family(None) == "Unclassified"

    def test_splits_on_first_colon(self) -> None:
        opening = _opening("Ruy Lopez: Closed, Chigorin Defense")
        assert metrics.opening_family(opening) == "Ruy Lopez"

    def test_name_without_colon_is_used_whole(self) -> None:
        opening = _opening("Sicilian Defense")
        assert metrics.opening_family(opening) == "Sicilian Defense"


class TestBasicAggregates:
    def test_average_accuracy_of_empty_list_is_none(self) -> None:
        assert metrics.average_accuracy([]) is None

    def test_average_accuracy(self) -> None:
        games = [
            _for_analytics(_game(), _analysis(accuracy=80.0)),
            _for_analytics(_game(), _analysis(accuracy=100.0)),
        ]
        assert metrics.average_accuracy(games) == 90.0

    def test_classification_rates_are_move_weighted(self) -> None:
        # 3 best out of 4 moves + 8 best out of 10 moves = 11/14 best.
        games = [
            _for_analytics(_game(), _analysis(counts={"best": 3, "blunder": 1})),
            _for_analytics(_game(), _analysis(counts={"best": 8, "blunder": 2})),
        ]
        rates = metrics.classification_rates(games)
        assert rates["best"] == round(11 / 14, 3)
        assert rates["blunder"] == round(3 / 14, 3)

    def test_average_critical_moments(self) -> None:
        games = [
            _for_analytics(_game(), _analysis(critical_moments=2)),
            _for_analytics(_game(), _analysis(critical_moments=4)),
        ]
        assert metrics.average_critical_moments(games) == 3.0


class TestOpeningFamilyPerformance:
    def test_groups_and_computes_win_rate(self) -> None:
        games = [
            _for_analytics(
                _game(focus_color=GameColor.WHITE, result="1-0"),
                _analysis(accuracy=90.0),
                opening=_opening("Ruy Lopez: Closed"),
            ),
            _for_analytics(
                _game(focus_color=GameColor.WHITE, result="0-1"),
                _analysis(accuracy=70.0),
                opening=_opening("Ruy Lopez: Open"),
            ),
            _for_analytics(
                _game(focus_color=GameColor.BLACK, result="1/2-1/2"),
                _analysis(accuracy=80.0),
                opening=None,
            ),
        ]
        stats = metrics.opening_family_performance(games)
        ruy = next(s for s in stats if s.family == "Ruy Lopez")
        assert ruy.games == 2
        assert ruy.wins == 1
        assert ruy.losses == 1
        assert ruy.win_rate == 0.5
        assert ruy.average_accuracy == 80.0

        unclassified = next(s for s in stats if s.family == "Unclassified")
        assert unclassified.games == 1
        assert unclassified.draws == 1
        assert unclassified.win_rate == 0.0


class TestColorSegmentation:
    def test_excludes_games_with_unknown_focus_color(self) -> None:
        games = [
            _for_analytics(_game(focus_color=GameColor.WHITE), _analysis()),
            _for_analytics(_game(focus_color=None), _analysis()),
        ]
        stats = metrics.color_segmentation(games)
        assert [s.color for s in stats] == ["white"]
        assert stats[0].games == 1


class TestTimeControlSegmentation:
    def test_groups_by_bucket(self) -> None:
        games = [
            _for_analytics(_game(time_control="60+0"), _analysis()),
            _for_analytics(_game(time_control="600+0"), _analysis()),
            _for_analytics(_game(time_control=None), _analysis()),
        ]
        buckets = {s.bucket: s.games for s in metrics.time_control_segmentation(games, _settings())}
        assert buckets == {"bullet": 1, "rapid": 1, "unknown": 1}


class TestRecurringWeaknesses:
    def test_hanging_piece_only_counts_when_players_own_move_was_bad(self) -> None:
        game = _game(focus_color=GameColor.WHITE)
        analysis = _analysis()
        _evaluation(analysis, ply=4, classification=MoveClassification.BLUNDER)
        motif = MotifFinding(
            game_analysis_id=analysis.id,
            ply=4,
            side=GameColor.WHITE,
            motif=MotifType.HANGING_PIECE,
            confidence=0.8,
            evidence={},
        )
        games = [_for_analytics(game, analysis, motifs=[motif])]

        settings = _settings(analytics_weakness_min_occurrence_rate=0.5)
        results = metrics.recurring_weaknesses(games, settings)

        assert len(results) == 1
        assert results[0].kind == "motif"
        assert results[0].name == "hanging_piece"

    def test_hanging_piece_does_not_count_if_the_move_was_not_bad(self) -> None:
        # A hanging-piece finding whose own ply was classified BEST would be a detector
        # inconsistency in practice, but the aggregation logic must not count it as a
        # weakness regardless — it only trusts MoveEvaluation's own classification.
        game = _game(focus_color=GameColor.WHITE)
        analysis = _analysis()
        _evaluation(analysis, ply=4, classification=MoveClassification.BEST)
        motif = MotifFinding(
            game_analysis_id=analysis.id,
            ply=4,
            side=GameColor.WHITE,
            motif=MotifType.HANGING_PIECE,
            confidence=0.8,
            evidence={},
        )
        games = [_for_analytics(game, analysis, motifs=[motif])]

        assert metrics.recurring_weaknesses(games, _settings()) == []

    def test_attacking_motif_counts_only_when_the_opponent_executed_it(self) -> None:
        game = _game(focus_color=GameColor.WHITE)
        analysis = _analysis()
        # The player forking the opponent is a strength, not a weakness.
        own_fork = MotifFinding(
            game_analysis_id=analysis.id,
            ply=10,
            side=GameColor.WHITE,
            motif=MotifType.FORK,
            confidence=0.9,
            evidence={},
        )
        games = [_for_analytics(game, analysis, motifs=[own_fork])]
        assert metrics.recurring_weaknesses(games, _settings()) == []

        opponent_fork = MotifFinding(
            game_analysis_id=analysis.id,
            ply=10,
            side=GameColor.BLACK,
            motif=MotifType.FORK,
            confidence=0.9,
            evidence={},
        )
        games = [_for_analytics(game, analysis, motifs=[opponent_fork])]
        results = metrics.recurring_weaknesses(games, _settings())
        assert len(results) == 1
        assert results[0].name == "fork"

    def test_weakness_theme_counts_when_it_belongs_to_the_player(self) -> None:
        game = _game(focus_color=GameColor.BLACK)
        analysis = _analysis()
        theme = StrategicThemeFinding(
            game_analysis_id=analysis.id,
            ply=20,
            side=GameColor.BLACK,
            theme=StrategicThemeType.BAD_BISHOP,
            confidence=0.6,
            evidence={},
        )
        games = [_for_analytics(game, analysis, themes=[theme])]
        results = metrics.recurring_weaknesses(games, _settings())
        assert len(results) == 1
        assert results[0].kind == "theme"
        assert results[0].name == "bad_bishop"

    def test_achievement_theme_is_never_a_weakness(self) -> None:
        game = _game(focus_color=GameColor.WHITE)
        analysis = _analysis()
        theme = StrategicThemeFinding(
            game_analysis_id=analysis.id,
            ply=20,
            side=GameColor.WHITE,
            theme=StrategicThemeType.OPEN_FILE_CONTROL,
            confidence=0.6,
            evidence={},
        )
        games = [_for_analytics(game, analysis, themes=[theme])]
        assert metrics.recurring_weaknesses(games, _settings()) == []

    def test_below_threshold_occurrence_rate_is_excluded(self) -> None:
        settings = _settings(analytics_weakness_min_occurrence_rate=0.5)
        with_weakness = _game(focus_color=GameColor.WHITE)
        analysis_a = _analysis()
        theme = StrategicThemeFinding(
            game_analysis_id=analysis_a.id,
            ply=1,
            side=GameColor.WHITE,
            theme=StrategicThemeType.BAD_BISHOP,
            confidence=0.6,
            evidence={},
        )
        games = [
            _for_analytics(with_weakness, analysis_a, themes=[theme]),
            _for_analytics(_game(focus_color=GameColor.WHITE), _analysis()),
            _for_analytics(_game(focus_color=GameColor.WHITE), _analysis()),
        ]
        # 1 out of 3 games = 0.333, below the 0.5 threshold.
        assert metrics.recurring_weaknesses(games, settings) == []

    def test_games_with_unknown_focus_color_are_excluded_from_denominator(self) -> None:
        settings = _settings(analytics_weakness_min_occurrence_rate=0.5)
        analysis_a = _analysis()
        theme = StrategicThemeFinding(
            game_analysis_id=analysis_a.id,
            ply=1,
            side=GameColor.WHITE,
            theme=StrategicThemeType.BAD_BISHOP,
            confidence=0.6,
            evidence={},
        )
        games = [
            _for_analytics(_game(focus_color=GameColor.WHITE), analysis_a, themes=[theme]),
            _for_analytics(_game(focus_color=None), _analysis()),
        ]
        # Only 1 evaluable game, and the weakness appears in it: rate 1.0.
        results = metrics.recurring_weaknesses(games, settings)
        assert len(results) == 1
        assert results[0].occurrence_rate == 1.0
