"""Motif/theme polarity: whose "problem" a Phase 6 finding actually is (D-020).

Originally derived for Phase 8's recurring-weakness detection, and shared here because
Phase 9's per-game report facts need the identical judgement call — "is this finding the
player's own issue, or something that merely happened near them" — and duplicating it
would risk the two silently drifting apart the next time a motif or theme is added.

Motifs are always recorded against the *mover's* side (see `MotifFinding`'s docstring and
`PatternDetectionService` — `side = board_before.turn` at that ply, for every motif). What
that means for the mover differs by motif though: creating a fork/pin/skewer/discovered-
attack/etc. is a tactical *win* for the mover, so the finding is the *other* side's
problem. `HANGING_PIECE` is the one exception — it is defined as the mover leaving their
own piece hanging, a self-inflicted blunder, so there the mover *is* the one with the
problem. Getting this backwards would silently call a player's own successful forks a
weakness, or miss that they keep getting forked.

Themes are recorded per side directly from what's true of that side's own position (each
detector under `domain/patterns/themes/` is called once per side and returns a finding
when *that side* has the property). But not every theme is bad news for the side it
describes: `PASSED_PAWN_CREATION`, `OPEN_FILE_CONTROL`, `CENTRE_CONTROL`, and
`SPACE_ADVANTAGE` are achievements, not weaknesses.
"""

from __future__ import annotations

from app.db.models import (
    GameColor,
    MotifFinding,
    MotifType,
    StrategicThemeFinding,
    StrategicThemeType,
)

SELF_INFLICTED_MOTIFS = frozenset({MotifType.HANGING_PIECE})

WEAKNESS_THEMES = frozenset(
    {
        StrategicThemeType.WEAK_KING_SAFETY,
        StrategicThemeType.PAWN_STRUCTURE_DAMAGE,
        StrategicThemeType.PIECE_ACTIVITY_IMBALANCE,
        StrategicThemeType.BAD_BISHOP,
        StrategicThemeType.DEVELOPMENT_LAG,
        StrategicThemeType.TIME_TROUBLE_COLLAPSE,
    }
)


def is_players_own_motif(finding: MotifFinding, focus_color: GameColor) -> bool:
    """Whether this motif finding is the player's own tactical problem (they were
    forked/pinned/etc., or they hung a piece themselves) rather than a tactic they
    executed against their opponent."""
    if finding.motif in SELF_INFLICTED_MOTIFS:
        return finding.side == focus_color
    return finding.side != focus_color


def is_players_own_theme(finding: StrategicThemeFinding, focus_color: GameColor) -> bool:
    """Whether this theme finding is a genuine structural weakness belonging to the
    player (not an achievement, and recorded against their own side)."""
    return finding.side == focus_color and finding.theme in WEAKNESS_THEMES


__all__ = [
    "SELF_INFLICTED_MOTIFS",
    "WEAKNESS_THEMES",
    "is_players_own_motif",
    "is_players_own_theme",
]
