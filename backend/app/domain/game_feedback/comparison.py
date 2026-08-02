"""Compares one game against the player's recent history (Phase 19, D-037).

Pure functions over already-loaded data, same split as `analytics/metrics.py` vs. its
service: nothing here touches the database or an LLM, so every judgement the feature makes
about a player is unit-testable from plain fixtures.

Three questions, answered deterministically before any prose is written:

- **What repeated?** A weakness that counts against the player in this game *and* recurs
  across the baseline. Recurrence is the point — a one-off mistake is already covered by
  the per-game report, and calling it a pattern would be a lie about the history.
- **What improved?** A weakness that recurs across the baseline and is *absent* here. This
  is the claim most easily overstated, so absence alone is never called a fix: a single
  clean game is reported with a `clear_streak` of 1 and `sustained=False`, and only a run
  of `game_feedback_improvement_min_streak` clean games earns the stronger word.
- **How good was it?** The player's own move quality expressed as distance from their own
  recent mean, not as a bare number. "78% accuracy" tells a player nothing; "above the 71%
  you normally play at" tells them everything.

Player-only metrics, deliberately: `GameAnalysis.summary["accuracy"]` covers *both* sides'
moves, which is right for a neutral game summary and wrong for "how did I do". The same
published formula (share of best-or-good moves) is re-applied here to the player's own
moves only. Baseline and target are computed identically, so the comparison stays
internally consistent even though these numbers differ from the dashboard's.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Literal

from app.core.config import GameFeedbackSettings
from app.db.models import GameColor
from app.domain.analytics.metrics import (
    GameForAnalytics,
    Outcome,
    WeaknessKey,
    determine_outcome,
    player_weaknesses_in_game,
)
from app.domain.patterns.polarity import is_players_own_motif, is_players_own_theme

Band = Literal["well_above", "above", "in_line", "below", "well_below"]
MetricName = Literal["accuracy", "blunder_rate", "critical_moments"]

_GOOD_OR_BETTER = frozenset({"best", "good"})


@dataclass(frozen=True)
class RepeatedWeakness:
    """A recurring weakness that showed up again in this game."""

    kind: Literal["motif", "theme"]
    name: str
    baseline_games_with_finding: int
    baseline_games: int
    occurrence_rate: float
    # Where it happened in *this* game, so the feedback can point at real moves.
    plies: list[int]


@dataclass(frozen=True)
class ImprovedWeakness:
    """A recurring weakness that did not show up in this game."""

    kind: Literal["motif", "theme"]
    name: str
    baseline_games_with_finding: int
    baseline_games: int
    occurrence_rate: float
    # Consecutive most-recent attributable games clear of it, this game included — so the
    # minimum meaningful value is 1 ("not in this game"), never 0.
    clear_streak: int
    sustained: bool


@dataclass(frozen=True)
class MetricComparison:
    """One measure of this game against the baseline's distribution of the same measure."""

    name: MetricName
    value: float
    baseline_mean: float
    baseline_stdev: float
    # Signed so positive always means *better*, whichever direction the raw metric runs.
    # `None` when the baseline has no spread to measure against (see `_band_for`).
    z_score: float | None
    band: Band


@dataclass(frozen=True)
class GameComparison:
    """Everything deterministic the feedback report is allowed to claim."""

    baseline_games: int
    sufficient_baseline: bool
    # False when the player's own side in this game is unknown, which makes every claim
    # here unattributable — see `player_weaknesses_in_game`.
    attributable: bool
    outcome: Outcome
    repeated: list[RepeatedWeakness]
    improved: list[ImprovedWeakness]
    metrics: list[MetricComparison]
    overall_band: Band


@dataclass(frozen=True)
class _PlayerMetrics:
    accuracy: float
    blunder_rate: float
    critical_moments: float


# Whether a bigger number is a better game, per metric. Drives the sign of `z_score` so
# every band reads in the same direction regardless of which way the raw metric runs.
_HIGHER_IS_BETTER: dict[MetricName, bool] = {
    "accuracy": True,
    "blunder_rate": False,
    "critical_moments": False,
}


def _side_to_move(ply: int) -> GameColor:
    """`ply` is 0-indexed (see `domain/games/parsing.py`), so an even ply is White's."""
    return GameColor.WHITE if ply % 2 == 0 else GameColor.BLACK


def _player_metrics(game: GameForAnalytics) -> _PlayerMetrics | None:
    """This game measured over the player's own moves only. `None` when their side is
    unknown or they have no evaluated moves — nothing to attribute either way."""
    focus = game.game.focus_color
    if focus is None:
        return None

    own_moves = [mv for mv in game.analysis.evaluations if _side_to_move(mv.ply) == focus]
    if not own_moves:
        return None

    good = sum(1 for mv in own_moves if mv.classification.value in _GOOD_OR_BETTER)
    blunders = sum(1 for mv in own_moves if mv.classification.value == "blunder")
    critical = sum(1 for mv in own_moves if mv.is_critical_moment)
    total = len(own_moves)
    return _PlayerMetrics(
        accuracy=round(100 * good / total, 1),
        blunder_rate=round(blunders / total, 4),
        critical_moments=float(critical),
    )


def _band_for(directional_score: float, settings: GameFeedbackSettings) -> Band:
    """Map a directional score (positive = better) onto plain language."""
    if directional_score >= settings.game_feedback_band_strong_z:
        return "well_above"
    if directional_score >= settings.game_feedback_band_slight_z:
        return "above"
    if directional_score <= -settings.game_feedback_band_strong_z:
        return "well_below"
    if directional_score <= -settings.game_feedback_band_slight_z:
        return "below"
    return "in_line"


def _compare_metric(
    name: MetricName,
    value: float,
    baseline_values: list[float],
    settings: GameFeedbackSettings,
) -> tuple[MetricComparison, float]:
    """One metric compared against its baseline, plus the directional score used to band
    it and to feed the overall verdict.

    The score is a z-score whenever the baseline has spread. When it does not — every
    prior game scored identically, which is common for a whole-number metric like critical
    moments — a z-score is undefined, but the *direction* of a difference is still
    certain: every previous game was one value and this one is not. That case is reported
    at the minimum tier (the "slight" threshold) rather than as "in line", which would
    hide a real difference, or as "well above", which would claim a magnitude no spread
    exists to justify. `z_score` itself stays `None` there, so a reader inspecting the
    numbers is never shown a statistic that was not actually computed.
    """
    mean = statistics.fmean(baseline_values)
    # Population stdev, not sample: the baseline is the whole of the history being
    # compared against, not a sample drawn from some larger population of games.
    stdev = statistics.pstdev(baseline_values) if len(baseline_values) > 1 else 0.0
    better_when_higher = _HIGHER_IS_BETTER[name]

    z_score: float | None = None
    if stdev > 0:
        raw_z = (value - mean) / stdev
        z_score = round(raw_z if better_when_higher else -raw_z, 2)
        directional_score = z_score
    elif value == mean:
        directional_score = 0.0
    else:
        improved = (value > mean) if better_when_higher else (value < mean)
        directional_score = (
            settings.game_feedback_band_slight_z
            if improved
            else -settings.game_feedback_band_slight_z
        )

    comparison = MetricComparison(
        name=name,
        value=value,
        baseline_mean=round(mean, 2),
        baseline_stdev=round(stdev, 2),
        z_score=z_score,
        band=_band_for(directional_score, settings),
    )
    return comparison, directional_score


def _plies_for(game: GameForAnalytics, kind: str, name: str) -> list[int]:
    """Where a given weakness occurred in this game, on the player's own side."""
    focus = game.game.focus_color
    if focus is None:
        return []
    if kind == "motif":
        return sorted(
            f.ply for f in game.motifs if f.motif.value == name and is_players_own_motif(f, focus)
        )
    return sorted(
        f.ply for f in game.themes if f.theme.value == name and is_players_own_theme(f, focus)
    )


def _clear_streak(weakness: WeaknessKey, prior_weaknesses: list[set[WeaknessKey]]) -> int:
    """Consecutive most-recent games free of `weakness`, counting this game as the first.

    `prior_weaknesses` is in recency order, so this walks backwards through the player's
    history and stops at the first game where the weakness reappeared. Starts at 1 because
    the caller only asks about weaknesses already known to be absent from the current game.
    """
    streak = 1
    for weaknesses in prior_weaknesses:
        if weakness in weaknesses:
            break
        streak += 1
    return streak


def compare_game_to_baseline(
    target: GameForAnalytics,
    prior: list[GameForAnalytics],
    settings: GameFeedbackSettings,
) -> GameComparison:
    """The full deterministic comparison of `target` against `prior` (most recent first).

    Games whose focus colour is unknown are dropped from `prior` entirely rather than
    counted as clean games — an unattributable game is not evidence of an absent weakness,
    and letting it inflate the denominator would quietly water down every occurrence rate.
    """
    outcome = determine_outcome(target.game.headers.get("Result"), target.game.focus_color)
    evaluable = [g for g in prior if g.game.focus_color is not None]
    baseline_games = len(evaluable)
    sufficient = baseline_games >= settings.game_feedback_min_baseline_games

    target_weaknesses = player_weaknesses_in_game(target)
    attributable = target.game.focus_color is not None

    # Below the minimum, no claim is made at all: the caller renders a "not enough
    # history yet" state instead. Computing repeats and verdicts anyway would leave a
    # tempting, meaningless payload sitting in the response for someone to render later.
    if not attributable or not sufficient:
        return GameComparison(
            baseline_games=baseline_games,
            sufficient_baseline=sufficient,
            attributable=attributable,
            outcome=outcome,
            repeated=[],
            improved=[],
            metrics=[],
            overall_band="in_line",
        )

    prior_weaknesses = [player_weaknesses_in_game(g) for g in evaluable]
    occurrence_counts: dict[WeaknessKey, int] = {}
    for weaknesses in prior_weaknesses:
        for key in weaknesses:
            occurrence_counts[key] = occurrence_counts.get(key, 0) + 1

    threshold = settings.game_feedback_repeat_min_occurrence_rate
    recurring = {
        key: count
        for key, count in occurrence_counts.items()
        if count / baseline_games >= threshold
    }

    repeated = [
        RepeatedWeakness(
            kind=kind,
            name=name,
            baseline_games_with_finding=count,
            baseline_games=baseline_games,
            occurrence_rate=round(count / baseline_games, 3),
            plies=_plies_for(target, kind, name),
        )
        for (kind, name), count in recurring.items()
        if (kind, name) in target_weaknesses
    ]

    improved: list[ImprovedWeakness] = []
    for (kind, name), count in recurring.items():
        if (kind, name) in target_weaknesses:
            continue
        streak = _clear_streak((kind, name), prior_weaknesses)
        improved.append(
            ImprovedWeakness(
                kind=kind,
                name=name,
                baseline_games_with_finding=count,
                baseline_games=baseline_games,
                occurrence_rate=round(count / baseline_games, 3),
                clear_streak=streak,
                sustained=streak >= settings.game_feedback_improvement_min_streak,
            )
        )

    metrics, directional_scores = _build_metrics(target, evaluable, settings)
    return GameComparison(
        baseline_games=baseline_games,
        sufficient_baseline=True,
        attributable=True,
        outcome=outcome,
        repeated=sorted(repeated, key=lambda r: r.occurrence_rate, reverse=True),
        improved=sorted(improved, key=lambda i: (i.sustained, i.occurrence_rate), reverse=True),
        metrics=metrics,
        overall_band=_overall_band(directional_scores, settings),
    )


def _build_metrics(
    target: GameForAnalytics,
    evaluable: list[GameForAnalytics],
    settings: GameFeedbackSettings,
) -> tuple[list[MetricComparison], list[float]]:
    """Every metric compared, alongside the directional scores behind them."""
    target_metrics = _player_metrics(target)
    baseline_metrics = [m for m in (_player_metrics(g) for g in evaluable) if m is not None]
    if target_metrics is None or not baseline_metrics:
        return [], []

    results = [
        _compare_metric(
            name,
            getattr(target_metrics, name),
            [getattr(m, name) for m in baseline_metrics],
            settings,
        )
        for name in ("accuracy", "blunder_rate", "critical_moments")
    ]
    return [comparison for comparison, _ in results], [score for _, score in results]


def _overall_band(directional_scores: list[float], settings: GameFeedbackSettings) -> Band:
    """One verdict from the individual measures: the mean of their directional scores.

    Averaging rather than picking accuracy alone, because the three measures genuinely can
    disagree — a game can be accurate overall and still contain the one blunder that lost
    it. A game only reads as clearly better when the measures broadly agree, which is the
    honest bar for telling someone they played well.
    """
    if not directional_scores:
        return "in_line"
    return _band_for(statistics.fmean(directional_scores), settings)


__all__ = [
    "Band",
    "GameComparison",
    "ImprovedWeakness",
    "MetricComparison",
    "MetricName",
    "RepeatedWeakness",
    "compare_game_to_baseline",
]
