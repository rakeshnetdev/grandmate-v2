"""Corpus-level canonicalization tests: accuracy and timing (Phase 4 evaluation).

The corpus is deliberately small for MVP — 150 real games (75 Carlsen, 75
Praggnanandhaa) plus the 8 curated edge cases, trimmed down from the full 10,594-game
collection after the owner asked for a smaller fixture footprint. All of it runs in the
default suite; there is no separate "slow" tier to opt into.
"""

from __future__ import annotations

import time
from pathlib import Path

import chess.pgn

from app.domain.games.parsing import CanonicalizationError, canonicalize_pgn

FIXTURES = Path(__file__).parent / "fixtures" / "pgn"

# Generous relative to the ~32ms/game observed during evaluation — wide enough not to
# flake on a loaded CI runner, tight enough to catch a real regression (e.g. an
# accidental O(n^2) in replay).
_MAX_MS_PER_GAME = 150


def _iter_games(path: Path):  # type: ignore[no-untyped-def]
    with path.open() as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                return
            yield game


class TestEdgeCaseCorpus:
    def test_every_curated_edge_case_canonicalizes(self) -> None:
        """The set built for this phase specifically to stress unusual PGN shapes —
        variations, comments, NAGs, minimal headers, aborted games, non-standard time
        controls, `%clk` annotations — must all replay cleanly."""
        failures = []
        total = 0
        for game in _iter_games(FIXTURES / "edge_cases.pgn"):
            total += 1
            try:
                canonicalize_pgn(str(game))
            except CanonicalizationError as exc:
                failures.append((game.headers.get("Event"), exc.reason, exc.detail))

        assert total == 8, "edge_cases.pgn should hold exactly the 8 curated games"
        assert failures == []


class TestRealGameCorpus:
    def test_corpus_accuracy_rate(self) -> None:
        total = 0
        failures: list[tuple[str, str, str, str]] = []

        for path in (FIXTURES / "Carlsen.pgn", FIXTURES / "Praggnanandhaa.pgn"):
            for game in _iter_games(path):
                total += 1
                try:
                    canonicalize_pgn(str(game))
                except CanonicalizationError as exc:
                    failures.append(
                        (path.name, game.headers.get("Event", "?"), exc.reason.value, exc.detail)
                    )

        assert total == 150, "corpus fixtures should hold exactly 150 real games"
        assert failures == [], f"unexpected canonicalization failures: {failures}"

    def test_average_canonicalization_time_stays_within_budget(self) -> None:
        texts = [
            str(game)
            for path in (FIXTURES / "Carlsen.pgn", FIXTURES / "Praggnanandhaa.pgn")
            for game in _iter_games(path)
        ]

        start = time.perf_counter()
        for text in texts:
            canonicalize_pgn(text)
        elapsed_ms = (time.perf_counter() - start) * 1000

        per_game_ms = elapsed_ms / len(texts)
        assert per_game_ms < _MAX_MS_PER_GAME, (
            f"{per_game_ms:.1f}ms/game exceeds the {_MAX_MS_PER_GAME}ms budget "
            f"({len(texts)} games, {elapsed_ms:.0f}ms total)"
        )
