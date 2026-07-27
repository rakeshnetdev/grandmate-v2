"""Time trouble collapse: `side`'s move quality drops sharply once the clock reads below
`THEME_TIME_TROUBLE_CLOCK_MS_THRESHOLD`, compared to the rest of the game. The only theme
that reads `MoveEvaluation.classification` directly rather than replaying positions — it
is fundamentally about a *quality* change, which board geometry alone cannot show.

Silently declines (returns `None`) rather than guessing when clock data is absent —
most manually uploaded PGNs have no `%clk` annotations (Phase 4), and "no clock data"
is not evidence of anything.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import PatternSettings
from app.db.models import GameColor, MoveClassification, MoveEvaluation
from app.domain.patterns.themes.base import PlyContext, ThemeDetection

_GOOD_ENOUGH = {MoveClassification.BEST, MoveClassification.GOOD}


def _accuracy(evaluations: list[MoveEvaluation]) -> float:
    good = sum(1 for evaluation in evaluations if evaluation.classification in _GOOD_ENOUGH)
    return 100 * good / len(evaluations)


def detect(
    plies: Sequence[PlyContext], side: GameColor, settings: PatternSettings
) -> ThemeDetection | None:
    side_plies = [p for p in plies if p.side == side and p.evaluation is not None]

    time_trouble = [
        p
        for p in side_plies
        if p.move.clock_ms is not None
        and p.move.clock_ms < settings.theme_time_trouble_clock_ms_threshold
    ]
    rest = [
        p
        for p in side_plies
        if p.move.clock_ms is None
        or p.move.clock_ms >= settings.theme_time_trouble_clock_ms_threshold
    ]
    # Two comparison groups, each needing enough data points that one lucky/unlucky move
    # doesn't read as a "collapse".
    if len(time_trouble) < 2 or len(rest) < 2:
        return None

    # The `if p.evaluation is not None` filter is redundant at runtime — `side_plies`
    # already guarantees it — but it is what lets mypy narrow the comprehension's result
    # to `list[MoveEvaluation]` instead of `list[MoveEvaluation | None]`.
    time_trouble_accuracy = _accuracy(
        [p.evaluation for p in time_trouble if p.evaluation is not None]
    )
    rest_accuracy = _accuracy([p.evaluation for p in rest if p.evaluation is not None])
    drop = rest_accuracy - time_trouble_accuracy
    if drop < settings.theme_time_trouble_accuracy_drop_pct:
        return None

    return ThemeDetection(
        ply=time_trouble[0].ply,
        confidence=0.65,
        evidence={
            "time_trouble_accuracy": round(time_trouble_accuracy, 1),
            "rest_of_game_accuracy": round(rest_accuracy, 1),
            "plies_in_time_trouble": len(time_trouble),
        },
    )


__all__ = ["detect"]
