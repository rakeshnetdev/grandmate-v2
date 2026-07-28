"""Unit tests for `domain/patterns/polarity.py` — extracted from Phase 8's analytics
metrics so Phase 9's report facts can reuse the identical judgement call. In-memory
model instances only, same convention as `test_analytics_metrics.py`.
"""

from __future__ import annotations

from app.db.models import (
    GameColor,
    MotifFinding,
    MotifType,
    StrategicThemeFinding,
    StrategicThemeType,
)
from app.domain.patterns.polarity import is_players_own_motif, is_players_own_theme


def _motif(motif: MotifType, side: GameColor) -> MotifFinding:
    return MotifFinding(ply=1, side=side, motif=motif, confidence=0.8, evidence={})


def _theme(theme: StrategicThemeType, side: GameColor) -> StrategicThemeFinding:
    return StrategicThemeFinding(ply=1, side=side, theme=theme, confidence=0.6, evidence={})


class TestIsPlayersOwnMotif:
    def test_an_attacking_motif_the_player_created_is_not_their_problem(self) -> None:
        finding = _motif(MotifType.FORK, side=GameColor.WHITE)
        assert is_players_own_motif(finding, GameColor.WHITE) is False

    def test_an_attacking_motif_the_opponent_created_is_the_players_problem(self) -> None:
        finding = _motif(MotifType.FORK, side=GameColor.BLACK)
        assert is_players_own_motif(finding, GameColor.WHITE) is True

    def test_hanging_piece_by_the_player_is_the_players_problem(self) -> None:
        finding = _motif(MotifType.HANGING_PIECE, side=GameColor.WHITE)
        assert is_players_own_motif(finding, GameColor.WHITE) is True

    def test_hanging_piece_by_the_opponent_is_not_the_players_problem(self) -> None:
        finding = _motif(MotifType.HANGING_PIECE, side=GameColor.BLACK)
        assert is_players_own_motif(finding, GameColor.WHITE) is False


class TestIsPlayersOwnTheme:
    def test_a_weakness_theme_on_the_players_own_side_is_their_problem(self) -> None:
        finding = _theme(StrategicThemeType.BAD_BISHOP, side=GameColor.WHITE)
        assert is_players_own_theme(finding, GameColor.WHITE) is True

    def test_a_weakness_theme_on_the_opponents_side_is_not_the_players_problem(self) -> None:
        finding = _theme(StrategicThemeType.BAD_BISHOP, side=GameColor.BLACK)
        assert is_players_own_theme(finding, GameColor.WHITE) is False

    def test_an_achievement_theme_is_never_the_players_problem_even_on_their_own_side(
        self,
    ) -> None:
        finding = _theme(StrategicThemeType.OPEN_FILE_CONTROL, side=GameColor.WHITE)
        assert is_players_own_theme(finding, GameColor.WHITE) is False
