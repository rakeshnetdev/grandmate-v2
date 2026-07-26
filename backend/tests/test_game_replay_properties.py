"""Property tests for move-replay consistency (Phase 4 exit criterion).

python-chess has no strategy for generating from-scratch legal game sequences, so these
sample real games from the corpus fixtures rather than synthesizing positions — the
property under test is replay *consistency*, not move legality (which the corpus already
guarantees by construction: every game here is a real, played game).

The core property: `canonicalize_pgn`'s SAN-based replay and an independently driven
UCI-based replay must reach bit-identical FEN strings at every ply. If they diverge, one
of the two replay paths has a bug — this is exactly the kind of error that a single
example-based test on one game would not reliably catch, but a hundred sampled real games
will.
"""

from __future__ import annotations

import io
from pathlib import Path

import chess
import chess.pgn
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.domain.games.parsing import canonicalize_pgn

FIXTURES = Path(__file__).parent / "fixtures" / "pgn"


def _load_games(path: Path, limit: int) -> list[str]:
    texts: list[str] = []
    with path.open() as handle:
        for _ in range(limit):
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            texts.append(str(game))
    return texts


def _sample_corpus_games() -> list[str]:
    """The whole (deliberately small, 150-game) corpus plus the curated edge cases."""
    edge_cases = _load_games(FIXTURES / "edge_cases.pgn", limit=100)
    carlsen_sample = _load_games(FIXTURES / "Carlsen.pgn", limit=150)
    pragg_sample = _load_games(FIXTURES / "Praggnanandhaa.pgn", limit=150)
    return edge_cases + carlsen_sample + pragg_sample


_SAMPLE_GAMES = _sample_corpus_games()


def _independent_uci_replay(pgn_text: str) -> list[str]:
    """A second, independent replay path: push UCI moves directly rather than going
    through SAN computation. Returns the FEN after each ply."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    assert game is not None
    board = chess.Board()
    fens_after: list[str] = []
    for node in game.mainline():
        board.push(node.move)
        fens_after.append(board.fen())
    return fens_after


class TestReplayConsistency:
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(pgn_text=st.sampled_from(_SAMPLE_GAMES))
    def test_fen_chain_matches_an_independent_replay(self, pgn_text: str) -> None:
        canonical = canonicalize_pgn(pgn_text)
        independent_fens = _independent_uci_replay(pgn_text)

        assert [m.fen_after for m in canonical.moves] == independent_fens

    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(pgn_text=st.sampled_from(_SAMPLE_GAMES))
    def test_fen_before_chain_has_no_gaps(self, pgn_text: str) -> None:
        canonical = canonicalize_pgn(pgn_text)

        assert canonical.moves[0].fen_before == chess.STARTING_FEN
        for current, following in zip(canonical.moves, canonical.moves[1:], strict=False):
            assert current.fen_after == following.fen_before

    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(pgn_text=st.sampled_from(_SAMPLE_GAMES))
    def test_epd_is_always_a_prefix_of_its_fen(self, pgn_text: str) -> None:
        canonical = canonicalize_pgn(pgn_text)

        for move in canonical.moves:
            assert move.fen_after.startswith(move.epd_after)
            assert chess.Board(move.fen_after).epd() == move.epd_after
