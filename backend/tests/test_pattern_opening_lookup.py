"""Opening lookup unit tests: EPD-keyed matching, deepest-match selection, transpositions
(ADR-0009). Loads the real vendored dataset — no fixture stands in for it, since the
dataset's own correctness (no cross-volume duplicate EPDs) is part of what this covers.
"""

from __future__ import annotations

from pathlib import Path

import chess
import pytest

from app.core.config import PatternSettings
from app.domain.patterns import OpeningDatasetError, load_opening_index

SETTINGS = PatternSettings()
INDEX = load_opening_index(SETTINGS)


def _epds(sans: list[str]) -> list[str]:
    board = chess.Board()
    epds = []
    for san in sans:
        board.push_san(san)
        epds.append(board.epd())
    return epds


def test_loads_the_real_vendored_dataset() -> None:
    assert len(INDEX) > 3000


def test_matches_a_known_opening() -> None:
    result = INDEX.match(_epds(["e4", "e5", "Nf3", "Nc6", "Bb5"]))
    assert result is not None
    assert result.eco == "C60"
    assert result.opening_name == "Ruy Lopez"
    assert result.matched_ply == 4


def test_keeps_the_deepest_match_not_the_first() -> None:
    """A game reaching a specific named variation matches both the broad family (after
    3.Bb5) and the more specific line (after 3...a6) — the deeper, more specific match
    must win."""
    broad = INDEX.match(_epds(["e4", "e5", "Nf3", "Nc6", "Bb5"]))
    specific = INDEX.match(_epds(["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"]))
    assert broad is not None
    assert specific is not None
    assert specific.matched_ply > broad.matched_ply
    assert "Ruy Lopez" in specific.opening_name


def test_transposition_reaches_the_same_match_as_the_direct_order() -> None:
    """EPD has no move-count component, so the identical position reached by a different
    move order must match identically — this is the whole point of ADR-0009's EPD choice
    over PGN-prefix matching."""
    direct = INDEX.match(_epds(["d4", "Nf6", "c4", "e6"]))
    transposed = INDEX.match(_epds(["c4", "Nf6", "d4", "e6"]))
    assert direct is not None
    assert transposed is not None
    assert direct.eco == transposed.eco
    assert direct.opening_name == transposed.opening_name
    assert direct.epd == transposed.epd


def test_leaving_book_does_not_advance_the_match() -> None:
    """The dataset is comprehensive enough that nearly every reasonable first move has
    *some* ECO entry, so "no match at all" isn't a realistic case to test. What matters
    is that a nonsensical continuation after a known line doesn't spuriously extend the
    match past where book actually ended."""
    in_book = INDEX.match(_epds(["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6"]))
    off_book = INDEX.match(_epds(["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "h4"]))
    assert in_book is not None
    assert off_book is not None
    assert off_book.matched_ply == in_book.matched_ply


def test_empty_move_list_has_no_match() -> None:
    assert INDEX.match([]) is None


def test_missing_dataset_file_raises_a_clear_error(tmp_path: Path) -> None:
    settings = PatternSettings(openings_data_dir=str(tmp_path))
    with pytest.raises(OpeningDatasetError, match=r"all\.tsv"):
        load_opening_index(settings)
