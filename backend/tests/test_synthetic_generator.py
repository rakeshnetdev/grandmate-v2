"""Unit tests for `evals/harness/synthetic_generator.py` (Phase 16) — in-memory model
instances, no DB. `sample_analyzed_games`'s real query was exercised directly by hand
against the dev database; what's tested here is the part with actual branching logic:
question templating and provenance/reference-fact assembly."""

from __future__ import annotations

import uuid

from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MoveClassification,
    MoveEvaluation,
    OpeningMatch,
)
from evals.harness.synthetic_generator import SampledGame, generate_scenarios


def _game(headers: dict[str, str] | None = None) -> Game:
    return Game(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers=headers or {"White": "A", "Black": "B", "Result": "1-0"},
        raw_pgn_path="pgn/test.pgn",
        focus_color=GameColor.WHITE,
    )


def _analysis(evaluations: list[MoveEvaluation]) -> GameAnalysis:
    analysis = GameAnalysis(
        id=uuid.uuid4(),
        game_id=uuid.uuid4(),
        analysis_version="test",
        engine_depth=12,
        summary={
            "total_moves": len(evaluations),
            "counts": {"best": len(evaluations)},
            "accuracy": 90.0,
            "critical_moments": 0,
        },
    )
    analysis.evaluations = evaluations
    return analysis


def _evaluation(ply: int, classification: MoveClassification, swing: int = 0) -> MoveEvaluation:
    return MoveEvaluation(
        game_analysis_id=uuid.uuid4(),
        ply=ply,
        eval_cp=0,
        mate_in=None,
        best_move_uci=None,
        pv=[],
        classification=classification,
        eval_swing_cp=swing,
        is_critical_moment=classification == MoveClassification.BLUNDER,
        deep_analyzed=False,
    )


class TestGenerateScenarios:
    def test_one_scenario_per_intent_per_game(self) -> None:
        evaluations = [_evaluation(i, MoveClassification.BEST) for i in range(4)]
        analysis = _analysis(evaluations)
        sampled = SampledGame(
            game=_game(),
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            moves=["e4", "e5", "Nf3", "Nc6"],
        )

        rows = generate_scenarios([sampled])

        intents = {row["scenario_id"].rsplit("-", 1)[-1] for row in rows}
        assert intents == {"explain", "compare", "summarise", "train_next"}
        assert len(rows) == 4

    def test_explain_question_names_the_actual_blundered_move(self) -> None:
        evaluations = [
            _evaluation(0, MoveClassification.BEST),
            _evaluation(1, MoveClassification.BEST),
            _evaluation(2, MoveClassification.BLUNDER, swing=400),
        ]
        analysis = _analysis(evaluations)
        sampled = SampledGame(
            game=_game(),
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            moves=["e4", "e5", "Qh5??"],
        )

        rows = generate_scenarios([sampled])

        explain_row = next(r for r in rows if r["scenario_id"].endswith("-explain"))
        assert "Qh5??" in explain_row["question"]
        assert "blunder" in explain_row["question"]

    def test_falls_back_to_the_opening_when_there_is_no_notable_move(self) -> None:
        evaluations = [_evaluation(i, MoveClassification.BEST) for i in range(2)]
        analysis = _analysis(evaluations)
        opening = OpeningMatch(
            id=uuid.uuid4(),
            game_id=uuid.uuid4(),
            eco="C50",
            opening_name="Italian Game",
            matched_ply=1,
        )
        sampled = SampledGame(
            game=_game(),
            analysis=analysis,
            opening=opening,
            motifs=[],
            themes=[],
            moves=["e4", "e5"],
        )

        rows = generate_scenarios([sampled])

        explain_row = next(r for r in rows if r["scenario_id"].endswith("-explain"))
        assert "Italian Game" in explain_row["question"]

    def test_every_row_carries_provenance_and_is_unreviewed(self) -> None:
        analysis = _analysis([_evaluation(0, MoveClassification.BEST)])
        sampled = SampledGame(
            game=_game(),
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            moves=["e4"],
        )

        rows = generate_scenarios([sampled])

        for row in rows:
            assert row["reviewed_by"] is None
            assert row["provenance"]["source_game_id"] == str(sampled.game.id)
            assert row["provenance"]["generator_version"]

    def test_reference_facts_come_from_deterministic_extraction_not_a_model(self) -> None:
        analysis = _analysis([_evaluation(0, MoveClassification.BEST)])
        sampled = SampledGame(
            game=_game(),
            analysis=analysis,
            opening=None,
            motifs=[],
            themes=[],
            moves=["e4"],
        )

        rows = generate_scenarios([sampled])

        fact_kinds = {f["kind"] for f in rows[0]["reference_facts"]}
        assert "summary" in fact_kinds

    def test_no_samples_yields_no_scenarios(self) -> None:
        assert generate_scenarios([]) == []
