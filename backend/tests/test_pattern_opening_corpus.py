"""Opening detection corpus evaluation (Phase 6): accuracy against the same 150-game
real corpus Phase 4 already established (`test_corpus_canonicalization.py`), reusing it
rather than adding a second fixture set.

Ground truth here is each game's own `[ECO "..."]` PGN header — independent of this
codebase's `OpeningIndex`, since those headers were assigned by whatever tool originally
exported these games, not by our detector. That independence is what makes this a real
accuracy check rather than the detector grading its own homework.

A mismatch is not automatically a defect: `OpeningIndex.match` deliberately keeps the
*deepest* EPD match along the game (see `opening_lookup.py` and
`final_docs/v2/adr/0009-opening-data-source.md`), which is often a more specific named
variation than whatever ECO a different tool assigned at a shallower point. The
family-level check below (same ECO letter) separates that from a genuine wrong-family
miss.
"""

from __future__ import annotations

from pathlib import Path

import chess.pgn

from app.core.config import PatternSettings
from app.domain.games.parsing import canonicalize_pgn
from app.domain.patterns import load_opening_index

FIXTURES = Path(__file__).parent / "fixtures" / "pgn"

_SETTINGS = PatternSettings()
_INDEX = load_opening_index(_SETTINGS)

# Real corpus divergences are dominated by shared opening families that differ only in
# depth/sub-variation (see the phase report for the full breakdown) — genuine
# cross-family misses are rare enough that a small, explicit budget catches regressions
# without being brittle to a single reclassification.
_MAX_CROSS_FAMILY_MISMATCHES = 5


def _iter_games(path: Path):  # type: ignore[no-untyped-def]
    with path.open() as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                return
            yield game


class TestOpeningCorpusAccuracy:
    def test_every_corpus_game_gets_a_match(self) -> None:
        """No-match would mean a real, played opening isn't represented anywhere in the
        vendored Lichess dataset at all — that's a coverage gap worth failing loudly on,
        distinct from a same-family depth mismatch."""
        no_match = []
        for path in (FIXTURES / "Carlsen.pgn", FIXTURES / "Praggnanandhaa.pgn"):
            for game in _iter_games(path):
                canonical = canonicalize_pgn(str(game))
                epds = [move.epd_after for move in canonical.moves]
                if _INDEX.match(epds) is None:
                    no_match.append((path.name, game.headers.get("Event", "?")))

        assert no_match == [], f"games with no opening match at all: {no_match}"

    def test_cross_family_mismatch_rate_stays_within_budget(self) -> None:
        cross_family = []
        for path in (FIXTURES / "Carlsen.pgn", FIXTURES / "Praggnanandhaa.pgn"):
            for game in _iter_games(path):
                header_eco = game.headers.get("ECO", "")
                canonical = canonicalize_pgn(str(game))
                epds = [move.epd_after for move in canonical.moves]
                match = _INDEX.match(epds)
                assert match is not None  # covered by the coverage test above
                if header_eco and match.eco[0] != header_eco[0]:
                    cross_family.append((path.name, header_eco, match.eco, match.opening_name))

        assert len(cross_family) <= _MAX_CROSS_FAMILY_MISMATCHES, (
            f"{len(cross_family)} cross-family mismatches exceeds budget: {cross_family}"
        )
