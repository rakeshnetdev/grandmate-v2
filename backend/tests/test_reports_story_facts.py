"""Unit tests for `domain/reports/story_facts.py` (Phase 16b)."""

from __future__ import annotations

import uuid

import chess

from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameMove,
    GameSource,
    MoveClassification,
    MoveEvaluation,
)
from app.domain.reports.story_facts import extract_story_facts


def _game() -> Game:
    return Game(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "Player", "Black": "Opponent", "Result": "1-0"},
        raw_pgn_path="pgn/test.pgn",
        focus_color=GameColor.WHITE,
    )


def _analysis(evaluations: list[MoveEvaluation]) -> GameAnalysis:
    analysis = GameAnalysis(
        id=uuid.uuid4(),
        game_id=uuid.uuid4(),
        analysis_version="test",
        engine_depth=12,
        summary={"total_moves": len(evaluations), "counts": {}, "accuracy": 80.0},
    )
    analysis.evaluations = evaluations
    return analysis


def _move_eval(ply: int, classification: MoveClassification) -> MoveEvaluation:
    return MoveEvaluation(
        ply=ply,
        eval_cp=0,
        mate_in=None,
        best_move_uci="e2e4",
        pv=[],
        classification=classification,
        eval_swing_cp=0,
        mate_swing=False,
        is_critical_moment=False,
        deep_analyzed=False,
    )


def _game_move(ply: int) -> GameMove:
    # A real (starting-position) FEN — segment_game_phases parses fen_after with
    # python-chess to check material, so a placeholder string would fail there.
    fen = chess.STARTING_FEN
    return GameMove(
        game_id=uuid.uuid4(),
        ply=ply,
        san=f"m{ply}",
        uci="e2e4",
        fen_before=fen,
        fen_after=fen,
        epd_after=fen.rsplit(" ", 2)[0],
    )


class TestExtractStoryFacts:
    def test_includes_both_sides_blunders_regardless_of_focus_color(self) -> None:
        # ply 0 = White (the focus player), ply 1 = Black (the opponent) — the
        # findings-format report would only ever show ply 0; the story must show both.
        evaluations = [
            _move_eval(0, MoveClassification.BLUNDER),
            _move_eval(1, MoveClassification.BLUNDER),
        ]
        facts = extract_story_facts(
            game=_game(),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
            moves_by_ply={0: _game_move(0), 1: _game_move(1)},
        )
        move_ids = {f.id for f in facts if f.kind == "move"}
        assert move_ids == {"move-0", "move-1"}

    def test_move_facts_are_tagged_with_side(self) -> None:
        evaluations = [_move_eval(1, MoveClassification.BLUNDER)]
        facts = extract_story_facts(
            game=_game(),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
            moves_by_ply={1: _game_move(1)},
        )
        move_fact = next(f for f in facts if f.id == "move-1")
        assert move_fact.data["side"] == "black"

    def test_produces_an_opening_phase_fact_with_per_side_counts(self) -> None:
        evaluations = [
            _move_eval(0, MoveClassification.BEST),
            _move_eval(1, MoveClassification.MISTAKE),
        ]
        facts = extract_story_facts(
            game=_game(),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
            moves_by_ply={0: _game_move(0), 1: _game_move(1)},
        )
        opening_phase = next(f for f in facts if f.id == "phase-opening")
        assert opening_phase.data["white_counts"] == {"best": 1}
        assert opening_phase.data["black_counts"] == {"mistake": 1}

    def test_no_middlegame_or_endgame_phase_fact_for_a_short_game(self) -> None:
        # Under the default 12-ply opening cutoff and never reaching low material.
        evaluations = [_move_eval(i, MoveClassification.GOOD) for i in range(6)]
        facts = extract_story_facts(
            game=_game(),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
            moves_by_ply={i: _game_move(i) for i in range(6)},
        )
        phase_ids = {f.id for f in facts if f.kind == "phase"}
        assert phase_ids == {"phase-opening"}
