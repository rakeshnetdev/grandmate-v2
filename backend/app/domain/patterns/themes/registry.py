"""Theme -> detector map. All ten of `glossary.md`'s strategic themes are registered —
unlike motifs, none needed to be held back for engine corroboration (see `base.py`)."""

from __future__ import annotations

from app.db.models import StrategicThemeType
from app.domain.patterns.themes import (
    bad_bishop,
    centre_control,
    development_lag,
    open_file_control,
    passed_pawn_creation,
    pawn_structure_damage,
    piece_activity_imbalance,
    space_advantage,
    time_trouble_collapse,
    weak_king_safety,
)
from app.domain.patterns.themes.base import ThemeDetector

THEME_DETECTORS: dict[StrategicThemeType, ThemeDetector] = {
    StrategicThemeType.WEAK_KING_SAFETY: weak_king_safety.detect,
    StrategicThemeType.PAWN_STRUCTURE_DAMAGE: pawn_structure_damage.detect,
    StrategicThemeType.PASSED_PAWN_CREATION: passed_pawn_creation.detect,
    StrategicThemeType.PIECE_ACTIVITY_IMBALANCE: piece_activity_imbalance.detect,
    StrategicThemeType.BAD_BISHOP: bad_bishop.detect,
    StrategicThemeType.OPEN_FILE_CONTROL: open_file_control.detect,
    StrategicThemeType.CENTRE_CONTROL: centre_control.detect,
    StrategicThemeType.SPACE_ADVANTAGE: space_advantage.detect,
    StrategicThemeType.DEVELOPMENT_LAG: development_lag.detect,
    StrategicThemeType.TIME_TROUBLE_COLLAPSE: time_trouble_collapse.detect,
}

__all__ = ["THEME_DETECTORS"]
