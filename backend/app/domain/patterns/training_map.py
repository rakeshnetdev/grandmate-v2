"""Motif/theme -> coaching training theme mapping (`glossary.md`'s "Training theme
mapping" table).

This is a lookup, not a report: it tags what a finding is *about* for downstream
consumers (Phase 8's aggregation, Phase 15's training-plan generation) to build on. It
does not judge whether a finding was good or bad for the side it belongs to — a fork a
profile delivered and a fork delivered against them file under the same training theme,
"Tactical pattern drilling"; separating "your strength" from "your weakness" is framing,
which is the persona/report layer's job (rule 9), not this domain module's.

`glossary.md` lists seven illustrative rows, several of which describe a *repeated*
pattern across games ("Repeated hanging pieces", "Opening-family underperformance") that
only Phase 8's cross-game aggregation can actually observe. This module maps every
motif/theme Phase 6 detects, one finding at a time; Phase 8 is expected to look here for
the training theme once it starts counting repetitions, not to duplicate the table.
"""

from __future__ import annotations

from app.db.models import MotifType, StrategicThemeType

MOTIF_TRAINING_THEMES: dict[MotifType, str] = {
    MotifType.FORK: "Tactical pattern drilling",
    MotifType.PIN: "Tactical pattern drilling",
    MotifType.SKEWER: "Tactical pattern drilling",
    MotifType.DISCOVERED_ATTACK: "Tactical pattern drilling",
    MotifType.DOUBLE_CHECK: "Tactical pattern drilling",
    MotifType.X_RAY: "Tactical pattern drilling",
    MotifType.REMOVING_THE_DEFENDER: "Tactical pattern drilling",
    MotifType.BACK_RANK_MATE: "Checkmate pattern recognition",
    MotifType.SMOTHERED_MATE: "Checkmate pattern recognition",
    # The one motif->theme pairing glossary.md states explicitly (as "repeated hanging
    # pieces"); a single instance still belongs to the same training theme.
    MotifType.HANGING_PIECE: "Blunder-check discipline",
}

THEME_TRAINING_THEMES: dict[StrategicThemeType, str] = {
    # Rows glossary.md states explicitly.
    StrategicThemeType.WEAK_KING_SAFETY: "King safety and castling timing",
    StrategicThemeType.PAWN_STRUCTURE_DAMAGE: "Structural decision-making",
    StrategicThemeType.DEVELOPMENT_LAG: "Opening principles",
    StrategicThemeType.TIME_TROUBLE_COLLAPSE: "Clock management",
    # Extended consistently for the remaining themes, which glossary.md's table did not
    # individually enumerate.
    StrategicThemeType.PASSED_PAWN_CREATION: "Endgame technique",
    StrategicThemeType.PIECE_ACTIVITY_IMBALANCE: "Piece activity and coordination",
    StrategicThemeType.BAD_BISHOP: "Piece activity and coordination",
    StrategicThemeType.OPEN_FILE_CONTROL: "Positional planning",
    StrategicThemeType.CENTRE_CONTROL: "Positional planning",
    StrategicThemeType.SPACE_ADVANTAGE: "Positional planning",
}


def training_theme_for_motif(motif: MotifType) -> str:
    return MOTIF_TRAINING_THEMES[motif]


def training_theme_for_theme(theme: StrategicThemeType) -> str:
    return THEME_TRAINING_THEMES[theme]


__all__ = [
    "MOTIF_TRAINING_THEMES",
    "THEME_TRAINING_THEMES",
    "training_theme_for_motif",
    "training_theme_for_theme",
]
