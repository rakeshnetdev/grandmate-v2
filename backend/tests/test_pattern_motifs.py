"""Tactical motif detector unit tests: one curated positive position per motif, plus the
false-positive guards found while building these (see each test's docstring for the bug
it catches). Pure — no engine, no database, positions built directly with `chess.Board`.
"""

from __future__ import annotations

import chess

from app.core.config import PatternSettings
from app.db.models import MotifType
from app.domain.patterns.motifs.registry import MOTIF_DETECTORS

SETTINGS = PatternSettings()


def _apply(fen_before: str, uci: str) -> tuple[chess.Board, chess.Move, chess.Board]:
    board_before = chess.Board(fen_before)
    move = chess.Move.from_uci(uci)
    assert move in board_before.legal_moves, f"{uci} illegal in {fen_before}"
    board_after = board_before.copy()
    board_after.push(move)
    return board_before, move, board_after


class TestFork:
    def test_knight_forks_king_and_rook(self) -> None:
        board_before, move, board_after = _apply("2r1k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "b5d6")
        result = MOTIF_DETECTORS[MotifType.FORK](board_before, move, board_after, SETTINGS)
        assert result is not None
        assert result.confidence == 0.9  # royal fork
        assert set(result.evidence["target_squares"]) == {"c8", "e8"}

    def test_king_counts_as_a_target_despite_zero_trade_value(self) -> None:
        """Regression: PIECE_VALUES_CP[KING] == 0 must not fall below
        MOTIF_FORK_MIN_TARGET_VALUE_CP and silently exclude the king as a fork target."""
        board_before, move, board_after = _apply("2r1k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "b5d6")
        result = MOTIF_DETECTORS[MotifType.FORK](board_before, move, board_after, SETTINGS)
        assert result is not None
        assert "e8" in result.evidence["target_squares"]

    def test_two_pawns_are_not_a_fork(self) -> None:
        """Below MOTIF_FORK_MIN_TARGET_VALUE_CP, targets don't count."""
        board_before, move, board_after = _apply("4k3/8/1p6/2N5/8/4p3/8/4K3 w - - 0 1", "c5d3")
        result = MOTIF_DETECTORS[MotifType.FORK](board_before, move, board_after, SETTINGS)
        assert result is None


class TestPin:
    def test_bishop_pins_knight_to_king(self) -> None:
        board_before, move, board_after = _apply("4k3/8/2n5/8/8/8/8/3B1K2 w - - 0 1", "d1a4")
        result = MOTIF_DETECTORS[MotifType.PIN](board_before, move, board_after, SETTINGS)
        assert result is not None
        assert result.evidence == {"pinned_square": "c6", "pinning_square": "a4"}

    def test_no_pin_when_not_on_the_king_line(self) -> None:
        board_before, move, board_after = _apply("4k3/8/2n5/8/8/8/8/3B1K2 w - - 0 1", "d1c2")
        result = MOTIF_DETECTORS[MotifType.PIN](board_before, move, board_after, SETTINGS)
        assert result is None


class TestSkewer:
    def test_rook_skewers_queen_in_front_of_rook(self) -> None:
        board_before, move, board_after = _apply("k3r3/8/8/4q3/8/8/6K1/7R w - - 0 1", "h1e1")
        result = MOTIF_DETECTORS[MotifType.SKEWER](board_before, move, board_after, SETTINGS)
        assert result is not None
        assert result.evidence == {
            "attacking_square": "e1",
            "front_square": "e5",
            "back_square": "e8",
        }

    def test_king_behind_the_front_piece_is_a_pin_not_a_skewer(self) -> None:
        """Regression: PIECE_VALUES_CP[KING] == 0 made `front_value > back_value` always
        true when the king was the back piece — every absolute pin was double-counted as
        a skewer until this was excluded explicitly."""
        board_before, move, board_after = _apply("4k3/8/2n5/8/8/8/8/3B1K2 w - - 0 1", "d1a4")
        result = MOTIF_DETECTORS[MotifType.SKEWER](board_before, move, board_after, SETTINGS)
        assert result is None

    def test_check_forcing_the_king_to_move_exposes_a_skewer(self) -> None:
        """Regression, caught by evaluation against real Lichess puzzle data (Phase 6
        eval, `skewer` angle): a king *in front* on the line is also forced to move
        (it's in check) regardless of its 0 trade value, so it must outrank whatever
        sits behind it — the plain value comparison alone missed this, since 0 is never
        greater than a real piece's value. Position is puzzle skewer_2's actual
        solution[0]: 1.Be2+ forks the king off the e2-a6 diagonal, exposing the rook on
        a6 for 2.Bxa6."""
        board_before, move, board_after = _apply(
            "8/5ppp/r2P4/8/8/3k1BPP/5P2/5K2 w - - 1 48", "f3e2"
        )
        result = MOTIF_DETECTORS[MotifType.SKEWER](board_before, move, board_after, SETTINGS)
        assert result is not None
        assert result.evidence == {
            "attacking_square": "e2",
            "front_square": "d3",
            "back_square": "a6",
        }


class TestXRay:
    def test_rook_x_rays_through_enemy_pawn_to_support_own_rook(self) -> None:
        board_before, move, board_after = _apply("R6k/p7/8/8/8/8/6K1/7R w - - 0 1", "h1a1")
        result = MOTIF_DETECTORS[MotifType.X_RAY](board_before, move, board_after, SETTINGS)
        assert result is not None
        assert result.evidence["through_square"] == "a7"
        assert result.evidence["supported_square"] == "a8"

    def test_lining_up_behind_a_piece_of_the_movers_own_colour_is_not_an_x_ray(self) -> None:
        """Same geometry as the positive case, but the piece in between is the mover's
        own (a7 is a white pawn, not black) — nothing is being x-rayed through an enemy
        piece, so this must not register."""
        board_before, move, board_after = _apply("R6k/P7/8/8/8/8/6K1/7R w - - 0 1", "h1a1")
        result = MOTIF_DETECTORS[MotifType.X_RAY](board_before, move, board_after, SETTINGS)
        assert result is None


class TestDiscoveredAttack:
    def test_bishop_moves_away_unmasking_rook_check(self) -> None:
        board_before, move, board_after = _apply("4q2k/8/8/8/4B3/8/8/K3R3 w - - 0 1", "e4d5")
        result = MOTIF_DETECTORS[MotifType.DISCOVERED_ATTACK](
            board_before, move, board_after, SETTINGS
        )
        assert result is not None
        assert result.evidence["target_square"] == "e8"

    def test_directly_attacking_something_new_is_not_a_discovery(self) -> None:
        """The moved piece's own new attack must not be misattributed as a discovery."""
        board_before, move, board_after = _apply("4k3/8/8/8/8/8/8/B3K3 w - - 0 1", "a1e5")
        result = MOTIF_DETECTORS[MotifType.DISCOVERED_ATTACK](
            board_before, move, board_after, SETTINGS
        )
        assert result is None


class TestDoubleCheck:
    def test_discovered_plus_direct_check_is_a_double_check(self) -> None:
        board_before, move, board_after = _apply("R2B3k/8/8/8/8/8/8/K7 w - - 0 1", "d8f6")
        result = MOTIF_DETECTORS[MotifType.DOUBLE_CHECK](board_before, move, board_after, SETTINGS)
        assert result is not None
        assert set(result.evidence["checker_squares"]) == {"a8", "f6"}

    def test_single_check_is_not_a_double_check(self) -> None:
        board_before, move, board_after = _apply("4k3/8/8/8/8/8/8/R3K3 w - - 0 1", "a1a8")
        result = MOTIF_DETECTORS[MotifType.DOUBLE_CHECK](board_before, move, board_after, SETTINGS)
        assert result is None


class TestBackRankMate:
    def test_rook_delivers_classic_back_rank_mate(self) -> None:
        board_before, move, board_after = _apply("6k1/5ppp/8/8/8/8/8/K2R4 w - - 0 1", "d1d8")
        result = MOTIF_DETECTORS[MotifType.BACK_RANK_MATE](
            board_before, move, board_after, SETTINGS
        )
        assert result is not None
        assert result.evidence == {"king_square": "g8"}

    def test_check_with_an_escape_square_is_not_a_mate(self) -> None:
        board_before, move, board_after = _apply("6k1/5p1p/6p1/8/8/8/8/K2R4 w - - 0 1", "d1d8")
        result = MOTIF_DETECTORS[MotifType.BACK_RANK_MATE](
            board_before, move, board_after, SETTINGS
        )
        assert result is None


class TestSmotheredMate:
    def test_knight_delivers_classic_smothered_mate(self) -> None:
        board_before, move, board_after = _apply("6rk/6pp/8/4N3/8/8/8/K7 w - - 0 1", "e5f7")
        result = MOTIF_DETECTORS[MotifType.SMOTHERED_MATE](
            board_before, move, board_after, SETTINGS
        )
        assert result is not None
        assert result.evidence == {"king_square": "h8"}

    def test_king_with_an_open_adjacent_square_is_not_smothered(self) -> None:
        board_before, move, board_after = _apply("7k/6pp/8/4N3/8/8/8/K7 w - - 0 1", "e5f7")
        result = MOTIF_DETECTORS[MotifType.SMOTHERED_MATE](
            board_before, move, board_after, SETTINGS
        )
        assert result is None


class TestHangingPiece:
    def test_undefended_attacked_knight_is_hanging(self) -> None:
        board_before, move, board_after = _apply("k7/1b6/8/3N4/8/8/7R/K7 w - - 0 1", "h2h3")
        result = MOTIF_DETECTORS[MotifType.HANGING_PIECE](board_before, move, board_after, SETTINGS)
        assert result is not None
        assert result.evidence == {"hanging_square": "d5", "piece": "N"}

    def test_defended_piece_is_not_hanging(self) -> None:
        # c4 pawn, not c3 — a pawn only defends diagonally one rank ahead, and c3 does
        # not cover d5.
        board_before, move, board_after = _apply("k7/1b6/8/3N4/2P5/8/7R/K7 w - - 0 1", "h2h3")
        result = MOTIF_DETECTORS[MotifType.HANGING_PIECE](board_before, move, board_after, SETTINGS)
        assert result is None


class TestRemovingTheDefender:
    def test_capturing_the_sole_defender_leaves_a_piece_hanging(self) -> None:
        board_before = chess.Board("k5Q1/2n5/4b3/8/8/8/6K1/2R5 w - - 0 1")
        move = chess.Move.from_uci("c1c7")
        assert move in board_before.legal_moves
        board_after = board_before.copy()
        board_after.push(move)

        result = MOTIF_DETECTORS[MotifType.REMOVING_THE_DEFENDER](
            board_before, move, board_after, SETTINGS
        )
        assert result is not None
        assert result.evidence == {
            "removed_defender_square": "c7",
            "newly_hanging_square": "e6",
        }

    def test_capturing_something_with_no_defensive_duty_finds_nothing(self) -> None:
        board_before = chess.Board("k5Q1/2n5/8/8/8/8/6K1/2R5 w - - 0 1")
        move = chess.Move.from_uci("c1c7")
        assert move in board_before.legal_moves
        board_after = board_before.copy()
        board_after.push(move)

        result = MOTIF_DETECTORS[MotifType.REMOVING_THE_DEFENDER](
            board_before, move, board_after, SETTINGS
        )
        assert result is None


def test_every_motif_type_has_a_registered_detector() -> None:
    assert set(MOTIF_DETECTORS) == set(MotifType)
