"""Move quality classification: centipawn loss and the five-category label (Phase 5).

Logic ported from `grandmate/backend/src/coach/analysis/classify.py` (see
`changes/0001-reuse-ledger.md`), rewritten for v2's `EngineSettings` (no module-level
constants) and extended from the reference's four buckets to the five in the project
glossary — the reference collapsed "played the engine's exact top move" and "played
something else with ~0 loss" into one `"ok"` bucket; v2 keeps them distinct as
`BEST`/`GOOD`.
"""

from __future__ import annotations

from app.core.config import EngineSettings
from app.db.models import MoveClassification
from app.integrations.engine import EngineEvaluation

# Mate scores have no natural centipawn value. Clamped to a flat magnitude well past any
# real evaluation and past BLUNDER_CP by a wide margin, so a position that swings to or
# from a forced mate always classifies as a blunder-tier swing regardless of exactly how
# many moves the mate is in — matching common practice (e.g. Lichess's accuracy model)
# rather than trying to rank "mate in 1" as meaningfully worse than "mate in 5" for this
# purpose.
_MATE_SCORE_CP = 100_000


def _comparable_cp(evaluation: EngineEvaluation) -> int:
    """A single centipawn-like number for comparison, collapsing the eval_cp/mate_in
    split back into one axis. Only used for centipawn-loss arithmetic — never stored."""
    if evaluation.mate_in is not None:
        return _MATE_SCORE_CP if evaluation.mate_in > 0 else -_MATE_SCORE_CP
    return evaluation.eval_cp or 0


def compute_cpl(eval_before: EngineEvaluation, eval_after: EngineEvaluation) -> int:
    """Centipawn loss for the move actually played, from the mover's own perspective.

    `eval_before` is the position before the move, already in the mover's frame (it is
    their turn to move there). `eval_after` is the position after the move — but now it
    is the *opponent's* turn, so their evaluation is in the opponent's frame and must be
    negated to compare on the same axis. Always >= 0: negative would mean the move
    somehow improved on the engine's own assessment of the starting position, which
    cannot happen against optimal defense.

    When either side of the swing is a forced mate, this number is `_MATE_SCORE_CP`
    arithmetic, not a real centipawn count — see `is_mate_swing`/`display_swing_cp`.
    Callers that classify a move may use it as-is; callers that display it to a user or
    an LLM must go through `display_swing_cp` first.
    """
    best = _comparable_cp(eval_before)
    played = -_comparable_cp(eval_after)
    return max(0, best - played)


def is_mate_swing(eval_before: EngineEvaluation, eval_after: EngineEvaluation) -> bool:
    """True when either side of this swing is a forced-mate evaluation, meaning
    `compute_cpl`'s return value for it is `_MATE_SCORE_CP`-derived rather than a real
    centipawn count."""
    return eval_before.mate_in is not None or eval_after.mate_in is not None


def display_swing_cp(eval_swing_cp: int, mate_swing: bool) -> int | None:
    """The centipawn-loss value safe to surface to a user or an LLM prompt: unchanged, or
    `None` when `mate_swing` is True and `eval_swing_cp` is really `_MATE_SCORE_CP`
    arithmetic rather than a real evaluation swing (e.g. "costing 99,470 centipawns" for
    a move that let a forced mate slip to a merely-winning position)."""
    return None if mate_swing else eval_swing_cp


def classify_move(
    *,
    played_uci: str,
    best_move_uci: str | None,
    cpl: int,
    settings: EngineSettings,
) -> MoveClassification:
    """The five-category label. An exact match with the engine's top move is always
    `BEST`, independent of `cpl` — avoids a move that objectively *is* the top choice
    landing in `GOOD` over floating-point-scale noise between two separate evaluations."""
    if best_move_uci is not None and played_uci == best_move_uci:
        return MoveClassification.BEST
    if cpl < settings.inaccuracy_cp:
        return MoveClassification.GOOD
    if cpl < settings.mistake_cp:
        return MoveClassification.INACCURACY
    if cpl < settings.blunder_cp:
        return MoveClassification.MISTAKE
    return MoveClassification.BLUNDER


__all__ = ["classify_move", "compute_cpl", "display_swing_cp", "is_mate_swing"]
