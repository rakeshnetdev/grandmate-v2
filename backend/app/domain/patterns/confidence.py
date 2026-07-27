"""Confidence corroboration policy (Phase 6).

Detectors report a structural confidence based purely on board geometry — they have no
access to engine evaluations (`motifs/base.py`'s docstring explains why). This is the one
place that nudges a finding's confidence using this ply's engine-derived classification,
applied uniformly by the orchestrating service rather than duplicated per detector.

Only applied to the two motifs whose whole point is "was this actually a costly moment"
(`HANGING_PIECE`, `REMOVING_THE_DEFENDER`). The others are either near-certain structural
facts already (double check, the mate patterns) or motifs where "the engine also rates
this move well" doesn't make the structural finding any less true (a fork is a fork
whether or not it was the objectively best move).
"""

from __future__ import annotations

from app.db.models import MotifType, MoveClassification, MoveEvaluation

CORROBORATED_MOTIFS = frozenset({MotifType.HANGING_PIECE, MotifType.REMOVING_THE_DEFENDER})

_SIGNIFICANT_CLASSIFICATIONS = frozenset({MoveClassification.MISTAKE, MoveClassification.BLUNDER})
_BOOST = 0.1
_PENALTY = 0.15


def corroborate(base_confidence: float, evaluation: MoveEvaluation | None) -> float:
    """Adjust `base_confidence` using this ply's engine classification, clamped to
    [0, 1]. No evaluation available (analysis pending, or this ply wasn't classified)
    means no adjustment — silence is not evidence either way."""
    if evaluation is None:
        return base_confidence
    if evaluation.classification in _SIGNIFICANT_CLASSIFICATIONS:
        adjusted = base_confidence + _BOOST
    elif evaluation.classification == MoveClassification.BEST:
        # The engine call this move fine, which weighs against "this hanging piece was
        # actually a costly blunder" — the piece may have been a deliberate, safe sac or
        # was going to be traded evenly regardless.
        adjusted = base_confidence - _PENALTY
    else:
        adjusted = base_confidence
    return max(0.0, min(1.0, adjusted))


__all__ = ["CORROBORATED_MOTIFS", "corroborate"]
