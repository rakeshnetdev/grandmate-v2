"""Canonical game parsing unit tests: full replay, FEN/EPD correctness, failure taxonomy.

No database, no storage — `canonicalize_pgn` is pure. Spot-checked against known
positions rather than trusting python-chess's own FEN generation blindly: these assert
the *specific* values GrandMate persists, so a future refactor that subtly changes what
gets stored (e.g. accidentally swapping fen_before/fen_after) fails loudly here.
"""

from __future__ import annotations

import chess
import pytest

from app.domain.games.parsing import (
    CanonicalizationError,
    CanonicalizationFailureReason,
    canonicalize_pgn,
)

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

SIMPLE_GAME = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0
"""


class TestReplay:
    def test_replays_every_ply(self) -> None:
        result = canonicalize_pgn(SIMPLE_GAME)

        assert [m.san for m in result.moves] == ["e4", "e5", "Nf3", "Nc6", "Bb5"]
        assert [m.uci for m in result.moves] == ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]

    def test_plies_are_zero_indexed(self) -> None:
        result = canonicalize_pgn(SIMPLE_GAME)

        assert [m.ply for m in result.moves] == [0, 1, 2, 3, 4]

    def test_first_fen_before_is_the_starting_position(self) -> None:
        result = canonicalize_pgn(SIMPLE_GAME)

        assert result.moves[0].fen_before == STARTING_FEN

    def test_fen_after_matches_the_next_moves_fen_before(self) -> None:
        """The chain must be unbroken: this is what makes the move list reconstructible
        position-by-position rather than just a bag of independent rows."""
        result = canonicalize_pgn(SIMPLE_GAME)

        for current, following in zip(result.moves, result.moves[1:], strict=False):
            assert current.fen_after == following.fen_before

    def test_fen_after_e4_is_correct(self) -> None:
        result = canonicalize_pgn(SIMPLE_GAME)

        # No "e3" en passant target: python-chess only reports one when an en passant
        # capture is actually legal in the resulting position (modern FEN convention),
        # and no black pawn is adjacent to e4 here.
        assert result.moves[0].fen_after == (
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        )

    def test_epd_after_is_the_fen_without_move_counters(self) -> None:
        """EPD is what opening lookup (ADR-0009) matches against — it must identify a
        position independent of how many moves it took to reach."""
        result = canonicalize_pgn(SIMPLE_GAME)

        for move in result.moves:
            board = chess.Board(move.fen_after)
            assert move.epd_after == board.epd()
            assert move.fen_after.startswith(move.epd_after)

    def test_clock_ms_is_none_without_a_clk_annotation(self) -> None:
        result = canonicalize_pgn(SIMPLE_GAME)

        assert all(m.clock_ms is None for m in result.moves)

    def test_clock_ms_is_parsed_from_clk_annotations(self) -> None:
        annotated = SIMPLE_GAME.replace("1. e4 e5", "1. e4 {[%clk 0:01:00]} e5 {[%clk 0:00:59]}")

        result = canonicalize_pgn(annotated)

        assert result.moves[0].clock_ms == 60_000
        assert result.moves[1].clock_ms == 59_000

    def test_variations_are_excluded_from_the_canonical_mainline(self) -> None:
        with_variation = SIMPLE_GAME.replace("3. Bb5 1-0", "3. Bb5 (3. Bc4 Bc5) 1-0")

        result = canonicalize_pgn(with_variation)

        assert [m.san for m in result.moves] == ["e4", "e5", "Nf3", "Nc6", "Bb5"]


class TestFailureTaxonomy:
    def test_empty_text_is_unparseable(self) -> None:
        with pytest.raises(CanonicalizationError) as exc_info:
            canonicalize_pgn("")

        assert exc_info.value.reason == CanonicalizationFailureReason.UNPARSEABLE

    def test_garbage_text_is_unparseable(self) -> None:
        with pytest.raises(CanonicalizationError) as exc_info:
            canonicalize_pgn("not a pgn file at all")

        assert exc_info.value.reason == CanonicalizationFailureReason.UNPARSEABLE

    def test_no_moves_is_unparseable(self) -> None:
        no_moves = SIMPLE_GAME.replace("1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0", "1-0")

        with pytest.raises(CanonicalizationError) as exc_info:
            canonicalize_pgn(no_moves)

        assert exc_info.value.reason == CanonicalizationFailureReason.UNPARSEABLE

    def test_an_illegal_move_is_a_replay_error_caught_at_parse_time(self) -> None:
        """python-chess resolves SAN legality while building the tree, so an illegal move
        surfaces via `game.errors` (UNPARSEABLE here) rather than during our own replay
        loop — both are covered; this documents which one actually fires and why."""
        illegal = SIMPLE_GAME.replace("3. Bb5 1-0", "3. Qxd8 1-0")

        with pytest.raises(CanonicalizationError) as exc_info:
            canonicalize_pgn(illegal)

        assert exc_info.value.reason == CanonicalizationFailureReason.UNPARSEABLE
        assert "Qxd8" in exc_info.value.detail

    def test_replay_error_path_is_reachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """REPLAY_ERROR is genuinely defensive: python-chess already validated every move
        while building the tree, so by the time replay reaches it, it cannot fail through
        any real PGN input — this proves the branch itself is correct, not just assumed
        so, by forcing the one failure mode that would otherwise be untestable.

        Patches `Board.san` (SAN *generation*, called only in our own replay loop) rather
        than `Board.push` — `read_game` itself parses SAN *into* moves via a different
        code path, and patching `push` broke parsing too, so the forced failure never
        reached our loop at all.
        """
        monkeypatch.setattr(
            chess.Board,
            "san",
            lambda self, move: (_ for _ in ()).throw(RuntimeError("forced failure")),
        )

        with pytest.raises(CanonicalizationError) as exc_info:
            canonicalize_pgn(SIMPLE_GAME)

        assert exc_info.value.reason == CanonicalizationFailureReason.REPLAY_ERROR
