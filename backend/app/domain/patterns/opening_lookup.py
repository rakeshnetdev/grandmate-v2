"""EPD-keyed opening lookup (Phase 6, D-011, ADR-0009).

Detection has no dependency on engine analysis — it only needs `GameMove.epd_after`
(Phase 4 output) — so it runs inline during canonicalization rather than waiting on a
background job. See `app/db/models/patterns.py` for why `game_openings` keys off
`game_id` directly while the tactics/strategy tables key off `game_analysis_id`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.core.config import PatternSettings
from app.core.config.groups import BACKEND_ROOT

_EXPECTED_HEADER = ["eco", "name", "pgn", "uci", "epd"]


class OpeningDatasetError(RuntimeError):
    """Raised when the vendored opening dataset cannot be loaded or is malformed."""


@dataclass(frozen=True)
class OpeningEntry:
    """One row of the vendored dataset, keyed by its EPD elsewhere."""

    eco: str
    name: str
    epd: str


@dataclass(frozen=True)
class OpeningMatchResult:
    """The deepest opening match found along a game's played positions."""

    eco: str
    opening_name: str
    epd: str
    matched_ply: int


class OpeningIndex:
    """EPD -> known opening entry, built once and reused for every game.

    A hash lookup per ply, not prefix-matching move text — see ADR-0009 for why EPD is
    the right key (transposition-safe, immune to move-counter differences that break full
    FEN equality for identical positions).
    """

    def __init__(self, entries_by_epd: dict[str, OpeningEntry]) -> None:
        self._entries_by_epd = entries_by_epd

    def __len__(self) -> int:
        return len(self._entries_by_epd)

    def match(self, played_epds: Sequence[str]) -> OpeningMatchResult | None:
        """Walk `played_epds` in ply order and return the deepest match, or `None`.

        Openings nest: an early position (e.g. after 1.e4) matches a broad family while a
        later position in the same game matches a specific named variation. Returning the
        *last* match found rather than the first is what ADR-0009 means by "keep the
        deepest match" — the more specific line is always the more informative one to
        report, and a game leaving book entirely correctly yields whatever was last
        matched before it did.
        """
        best: OpeningMatchResult | None = None
        for ply, epd in enumerate(played_epds):
            entry = self._entries_by_epd.get(epd)
            if entry is not None:
                best = OpeningMatchResult(
                    eco=entry.eco, opening_name=entry.name, epd=entry.epd, matched_ply=ply
                )
        return best


def load_opening_index(settings: PatternSettings) -> OpeningIndex:
    """Parse the vendored, cross-volume-deduplicated `all.tsv` into an `OpeningIndex`.

    Called once at process startup (`app.main.lifespan`) and stored on
    `app.state.opening_index` — re-parsing a ~3,800-row TSV per request would be wasted
    work for data that only changes on a manual re-vendor
    (`data/openings/PROVENANCE.md`).
    """
    data_dir = Path(settings.openings_data_dir)
    if not data_dir.is_absolute():
        data_dir = BACKEND_ROOT / data_dir
    dataset_path = data_dir / "all.tsv"

    if not dataset_path.is_file():
        raise OpeningDatasetError(
            f"Opening dataset not found at {dataset_path}. "
            "See backend/data/openings/PROVENANCE.md to (re)generate it."
        )

    entries_by_epd: dict[str, OpeningEntry] = {}
    with dataset_path.open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        if header != _EXPECTED_HEADER:
            raise OpeningDatasetError(
                f"Unexpected opening dataset header in {dataset_path}: {header!r}, "
                f"expected {_EXPECTED_HEADER!r}"
            )
        for line in handle:
            columns = line.rstrip("\n").split("\t")
            if len(columns) != len(_EXPECTED_HEADER):
                raise OpeningDatasetError(
                    f"Malformed row in {dataset_path}: expected "
                    f"{len(_EXPECTED_HEADER)} columns, got {len(columns)}"
                )
            eco, name, _pgn, _uci, epd = columns
            # gen.py already rejects duplicate EPDs within one invocation, and all.tsv
            # was generated from every source file in a single invocation (PROVENANCE.md)
            # specifically so this holds across ECO volumes too.
            entries_by_epd[epd] = OpeningEntry(eco=eco, name=name, epd=epd)

    return OpeningIndex(entries_by_epd)


__all__ = [
    "OpeningDatasetError",
    "OpeningEntry",
    "OpeningIndex",
    "OpeningMatchResult",
    "load_opening_index",
]
