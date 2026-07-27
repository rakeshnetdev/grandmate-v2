"""Training theme mapping unit tests: completeness and the rows glossary.md states
explicitly (D-012's training theme mapping table)."""

from __future__ import annotations

from app.db.models import MotifType, StrategicThemeType
from app.domain.patterns.training_map import (
    MOTIF_TRAINING_THEMES,
    THEME_TRAINING_THEMES,
    training_theme_for_motif,
    training_theme_for_theme,
)


def test_every_motif_has_a_training_theme() -> None:
    assert set(MOTIF_TRAINING_THEMES) == set(MotifType)


def test_every_strategic_theme_has_a_training_theme() -> None:
    assert set(THEME_TRAINING_THEMES) == set(StrategicThemeType)


def test_glossary_stated_rows_are_honoured() -> None:
    """The rows glossary.md's "Training theme mapping" table states verbatim."""
    assert training_theme_for_motif(MotifType.HANGING_PIECE) == "Blunder-check discipline"
    assert training_theme_for_theme(StrategicThemeType.DEVELOPMENT_LAG) == "Opening principles"
    assert (
        training_theme_for_theme(StrategicThemeType.WEAK_KING_SAFETY)
        == "King safety and castling timing"
    )
    assert (
        training_theme_for_theme(StrategicThemeType.PAWN_STRUCTURE_DAMAGE)
        == "Structural decision-making"
    )
    assert training_theme_for_theme(StrategicThemeType.TIME_TROUBLE_COLLAPSE) == "Clock management"
