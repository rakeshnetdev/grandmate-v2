"""Pure aggregation functions for profile-level analytics (Phase 8).

Free of any I/O — every function here takes already-loaded data and settings, and
returns a plain value or dataclass. `service.py` is the only caller and the only place
that touches the database; that split is what makes these functions cheap to unit test
without seeding a real session per case.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from app.core.config import AnalyticsSettings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    MotifFinding,
    MotifType,
    OpeningMatch,
    StrategicThemeFinding,
    StrategicThemeType,
)
from app.domain.patterns.polarity import (
    SELF_INFLICTED_MOTIFS,
    is_players_own_motif,
    is_players_own_theme,
)

Outcome = Literal["win", "draw", "loss", "unknown"]
TimeControlBucket = Literal["bullet", "blitz", "rapid", "classical", "unknown"]

_MISTAKE_OR_WORSE = frozenset({"mistake", "blunder"})


@dataclass(frozen=True)
class GameForAnalytics:
    """One profile's game, bundled with everything a metric needs to read. Assembled
    once by `service.py` so every metric function shares the same join instead of
    re-querying per metric."""

    game: Game
    analysis: GameAnalysis
    opening: OpeningMatch | None
    motifs: list[MotifFinding]
    themes: list[StrategicThemeFinding]


def determine_outcome(result: str | None, focus_color: GameColor | None) -> Outcome:
    """The player's own outcome, from a PGN `Result` header and which side they played.
    `None` focus_color (can't tell which side was the player's) or an unresolved header
    (`"*"`, missing) both read as "unknown" rather than being guessed at."""
    if focus_color is None or result not in {"1-0", "0-1", "1/2-1/2"}:
        return "unknown"
    if result == "1/2-1/2":
        return "draw"
    white_won = result == "1-0"
    player_is_white = focus_color == GameColor.WHITE
    return "win" if white_won == player_is_white else "loss"


def classify_time_control(
    header_value: str | None, settings: AnalyticsSettings
) -> TimeControlBucket:
    """Bucket a PGN `TimeControl` header (`"300+2"`, `"600"`, `"-"`) into the familiar
    bullet/blitz/rapid/classical tiers, estimating game duration as base + 40 *
    increment — the same convention Lichess and Chess.com use, so a profile's
    segmentation reads the way a player already expects."""
    if not header_value or header_value == "-":
        return "unknown"
    base_str, _, increment_str = header_value.partition("+")
    try:
        base_seconds = int(base_str)
        increment_seconds = int(increment_str) if increment_str else 0
    except ValueError:
        return "unknown"

    estimated_seconds = base_seconds + 40 * increment_seconds
    if estimated_seconds < settings.time_control_bullet_max_s:
        return "bullet"
    if estimated_seconds < settings.time_control_blitz_max_s:
        return "blitz"
    if estimated_seconds < settings.time_control_rapid_max_s:
        return "rapid"
    return "classical"


def opening_family(opening: OpeningMatch | None) -> str:
    """The human-readable family an opening match belongs to — the text before the
    first colon in `opening_name` ("Ruy Lopez: Closed, ..." -> "Ruy Lopez"). Reuses
    Phase 6's existing naming rather than inventing a new grouping taxonomy."""
    if opening is None:
        return "Unclassified"
    return opening.opening_name.split(":", 1)[0].strip()


def average_accuracy(games: list[GameForAnalytics]) -> float | None:
    if not games:
        return None
    total = sum(float(g.analysis.summary.get("accuracy", 0.0)) for g in games)
    return round(total / len(games), 1)


def classification_rates(games: list[GameForAnalytics]) -> dict[str, float]:
    """Share of all moves across `games` at each classification, e.g. `{"blunder":
    0.04, ...}`. Move-weighted rather than game-averaged, so a 60-move loss and a
    20-move win contribute proportionally to their own move count, not equally."""
    totals: Counter[str] = Counter()
    total_moves = 0
    for g in games:
        counts = g.analysis.summary.get("counts", {})
        for classification, count in counts.items():
            totals[classification] += count
            total_moves += count
    if total_moves == 0:
        return {}
    return {
        classification: round(count / total_moves, 3) for classification, count in totals.items()
    }


def average_critical_moments(games: list[GameForAnalytics]) -> float | None:
    if not games:
        return None
    total = sum(float(g.analysis.summary.get("critical_moments", 0)) for g in games)
    return round(total / len(games), 2)


def _outcome_counts(games: list[GameForAnalytics]) -> tuple[int, int, int, int]:
    """(wins, draws, losses, decided) — `decided` excludes "unknown" outcomes from the
    win-rate denominator, since an unresolved/unattributable result is not a loss."""
    outcomes = [determine_outcome(g.game.headers.get("Result"), g.game.focus_color) for g in games]
    wins, draws, losses = outcomes.count("win"), outcomes.count("draw"), outcomes.count("loss")
    return wins, draws, losses, wins + draws + losses


@dataclass(frozen=True)
class OpeningFamilyStats:
    family: str
    games: int
    wins: int
    draws: int
    losses: int
    win_rate: float | None
    average_accuracy: float | None


def opening_family_performance(games: list[GameForAnalytics]) -> list[OpeningFamilyStats]:
    """Win/draw/loss and average accuracy grouped by opening family, most-played first."""
    buckets: dict[str, list[GameForAnalytics]] = {}
    for g in games:
        buckets.setdefault(opening_family(g.opening), []).append(g)

    stats: list[OpeningFamilyStats] = []
    for family, family_games in buckets.items():
        wins, draws, losses, decided = _outcome_counts(family_games)
        stats.append(
            OpeningFamilyStats(
                family=family,
                games=len(family_games),
                wins=wins,
                draws=draws,
                losses=losses,
                win_rate=round(wins / decided, 3) if decided else None,
                average_accuracy=average_accuracy(family_games),
            )
        )
    return sorted(stats, key=lambda s: s.games, reverse=True)


@dataclass(frozen=True)
class ColorSegmentStats:
    color: str
    games: int
    average_accuracy: float | None
    classification_rates: dict[str, float]
    win_rate: float | None


def color_segmentation(games: list[GameForAnalytics]) -> list[ColorSegmentStats]:
    """Performance split by which side the player had. Games where the player's side
    could not be determined (`focus_color is None` — self-play, or an opponent name
    that doesn't match a linked platform username) are excluded here; there is no side
    to attribute them to."""
    stats: list[ColorSegmentStats] = []
    for color in (GameColor.WHITE, GameColor.BLACK):
        color_games = [g for g in games if g.game.focus_color == color]
        if not color_games:
            continue
        wins, _draws, _losses, decided = _outcome_counts(color_games)
        stats.append(
            ColorSegmentStats(
                color=color.value,
                games=len(color_games),
                average_accuracy=average_accuracy(color_games),
                classification_rates=classification_rates(color_games),
                win_rate=round(wins / decided, 3) if decided else None,
            )
        )
    return stats


@dataclass(frozen=True)
class TimeControlSegmentStats:
    bucket: str
    games: int
    average_accuracy: float | None
    win_rate: float | None


def time_control_segmentation(
    games: list[GameForAnalytics], settings: AnalyticsSettings
) -> list[TimeControlSegmentStats]:
    buckets: dict[str, list[GameForAnalytics]] = {}
    for g in games:
        bucket_label = classify_time_control(g.game.headers.get("TimeControl"), settings)
        buckets.setdefault(bucket_label, []).append(g)

    stats: list[TimeControlSegmentStats] = []
    for label, bucket_games in buckets.items():
        wins, _draws, _losses, decided = _outcome_counts(bucket_games)
        stats.append(
            TimeControlSegmentStats(
                bucket=label,
                games=len(bucket_games),
                average_accuracy=average_accuracy(bucket_games),
                win_rate=round(wins / decided, 3) if decided else None,
            )
        )
    return sorted(stats, key=lambda s: s.games, reverse=True)


@dataclass(frozen=True)
class WeaknessStats:
    kind: Literal["motif", "theme"]
    name: str
    games_with_finding: int
    occurrence_rate: float


def recurring_weaknesses(
    games: list[GameForAnalytics], settings: AnalyticsSettings
) -> list[WeaknessStats]:
    """Motifs/themes that recur, and count against the player, above
    `analytics_weakness_min_occurrence_rate` of the games where the player's side could
    be determined (games with `focus_color is None` are excluded from both the count and
    the denominator — there's nothing to attribute in either direction for them).

    For a self-inflicted motif (HANGING_PIECE), the finding's ply is exactly the
    player's own move, so it only counts if that move was also classified
    mistake-or-worse — a precise check, not a guess, since the ply and the move are the
    same thing. For every other (attacking) motif, the finding's ply belongs to the
    *opponent's* move, whose classification reflects the opponent's move quality, not a
    cost to the player — there is nothing meaningful to cross-reference there, so
    occurrence against the player is itself the signal.
    """
    evaluable = [g for g in games if g.game.focus_color is not None]
    if not evaluable:
        return []

    motif_game_counts: Counter[MotifType] = Counter()
    theme_game_counts: Counter[StrategicThemeType] = Counter()

    for g in evaluable:
        # Narrows `GameColor | None` for the type checker — `evaluable`'s own filter
        # already guarantees this at runtime.
        assert g.game.focus_color is not None
        focus = g.game.focus_color
        classification_by_ply = {mv.ply: mv.classification.value for mv in g.analysis.evaluations}

        motifs_this_game: set[MotifType] = set()
        for finding in g.motifs:
            if not is_players_own_motif(finding, focus):
                continue
            if (
                finding.motif in SELF_INFLICTED_MOTIFS
                and classification_by_ply.get(finding.ply) not in _MISTAKE_OR_WORSE
            ):
                continue
            motifs_this_game.add(finding.motif)
        motif_game_counts.update(motifs_this_game)

        themes_this_game = {
            finding.theme for finding in g.themes if is_players_own_theme(finding, focus)
        }
        theme_game_counts.update(themes_this_game)

    total = len(evaluable)
    results: list[WeaknessStats] = []
    for motif, count in motif_game_counts.items():
        rate = count / total
        if rate >= settings.analytics_weakness_min_occurrence_rate:
            results.append(WeaknessStats("motif", motif.value, count, round(rate, 3)))
    for theme, count in theme_game_counts.items():
        rate = count / total
        if rate >= settings.analytics_weakness_min_occurrence_rate:
            results.append(WeaknessStats("theme", theme.value, count, round(rate, 3)))

    return sorted(results, key=lambda w: w.occurrence_rate, reverse=True)


__all__ = [
    "ColorSegmentStats",
    "GameForAnalytics",
    "OpeningFamilyStats",
    "Outcome",
    "TimeControlBucket",
    "TimeControlSegmentStats",
    "WeaknessStats",
    "average_accuracy",
    "average_critical_moments",
    "classification_rates",
    "classify_time_control",
    "color_segmentation",
    "determine_outcome",
    "opening_family",
    "opening_family_performance",
    "recurring_weaknesses",
    "time_control_segmentation",
]
