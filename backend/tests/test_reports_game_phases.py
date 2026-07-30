"""Unit tests for `domain/reports/game_phases.py` (Phase 16b)."""

from __future__ import annotations

import uuid

import chess

from app.db.models import GameMove, OpeningMatch
from app.domain.reports.game_phases import segment_game_phases

_START = chess.STARTING_FEN
# A position with only kings and pawns left (0 major/minor pieces) — a clear endgame.
_KP_ENDGAME = "8/4k3/8/8/8/8/4K3/8 w - - 0 40"


def _move(ply: int, fen_after: str = _START) -> GameMove:
    return GameMove(
        game_id=uuid.uuid4(),
        ply=ply,
        san=f"m{ply}",
        uci="e2e4",
        fen_before=_START,
        fen_after=fen_after,
        epd_after=fen_after.rsplit(" ", 2)[0],
    )


class TestSegmentGamePhases:
    def test_opening_end_uses_the_matched_book_ply_when_available(self) -> None:
        moves = [_move(i) for i in range(20)]
        opening = OpeningMatch(eco="C60", opening_name="Ruy Lopez", epd="x", matched_ply=6)
        phases = segment_game_phases(moves, opening)
        assert phases.opening_end_ply == 6

    def test_opening_end_falls_back_to_a_default_ply_cutoff_with_no_book_match(self) -> None:
        moves = [_move(i) for i in range(20)]
        phases = segment_game_phases(moves, None)
        assert phases.opening_end_ply == 12

    def test_opening_end_never_exceeds_the_games_total_plies(self) -> None:
        moves = [_move(i) for i in range(5)]
        phases = segment_game_phases(moves, None)
        assert phases.opening_end_ply == 5

    def test_endgame_start_is_none_when_material_never_drops_low_enough(self) -> None:
        moves = [_move(i, _START) for i in range(10)]
        phases = segment_game_phases(moves, None)
        assert phases.endgame_start_ply is None

    def test_endgame_start_is_the_ply_after_material_drops_to_the_threshold(self) -> None:
        moves = [_move(0, _START), _move(1, _KP_ENDGAME), _move(2, _KP_ENDGAME)]
        phases = segment_game_phases(moves, None)
        assert phases.endgame_start_ply == 2
