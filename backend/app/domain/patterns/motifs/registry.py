"""Motif -> detector map. The single place that has to change to add or drop a motif —
`PatternDetectionService` just iterates this, it has no motif-specific knowledge itself.

Only the ten low/medium-difficulty motifs confirmed with the owner (see this phase's
report) are registered. The six high-difficulty ones from `glossary.md` (deflection,
decoy, overloading, interference, zwischenzug, windmill) are intentionally absent, not
forgotten — they need engine-corroborated confidence to ship safely.
"""

from __future__ import annotations

from app.db.models import MotifType
from app.domain.patterns.motifs import (
    back_rank_mate,
    discovered_attack,
    double_check,
    fork,
    hanging_piece,
    pin,
    removing_the_defender,
    skewer,
    smothered_mate,
    x_ray,
)
from app.domain.patterns.motifs.base import MotifDetector

MOTIF_DETECTORS: dict[MotifType, MotifDetector] = {
    MotifType.FORK: fork.detect,
    MotifType.PIN: pin.detect,
    MotifType.SKEWER: skewer.detect,
    MotifType.DISCOVERED_ATTACK: discovered_attack.detect,
    MotifType.DOUBLE_CHECK: double_check.detect,
    MotifType.BACK_RANK_MATE: back_rank_mate.detect,
    MotifType.SMOTHERED_MATE: smothered_mate.detect,
    MotifType.HANGING_PIECE: hanging_piece.detect,
    MotifType.REMOVING_THE_DEFENDER: removing_the_defender.detect,
    MotifType.X_RAY: x_ray.detect,
}

__all__ = ["MOTIF_DETECTORS"]
