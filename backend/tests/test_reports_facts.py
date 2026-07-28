"""Unit tests for `domain/reports/facts.py`. In-memory model instances only, same
convention as `test_analytics_metrics.py`.
"""

from __future__ import annotations

import uuid

from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MotifFinding,
    MotifType,
    MoveClassification,
    MoveEvaluation,
    OpeningMatch,
    StrategicThemeFinding,
    StrategicThemeType,
)
from app.domain.reports.facts import extract_facts


def _game(focus_color: GameColor | None) -> Game:
    return Game(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "Player", "Black": "Opponent", "Result": "1-0"},
        raw_pgn_path="pgn/test.pgn",
        focus_color=focus_color,
    )


def _analysis(evaluations: list[MoveEvaluation] | None = None) -> GameAnalysis:
    analysis = GameAnalysis(
        id=uuid.uuid4(),
        game_id=uuid.uuid4(),
        analysis_version="test",
        engine_depth=12,
        summary={"total_moves": 4, "counts": {"best": 4}, "accuracy": 90.0, "critical_moments": 0},
    )
    analysis.evaluations = evaluations or []
    return analysis


def _move(
    ply: int, classification: MoveClassification, *, critical: bool = False
) -> MoveEvaluation:
    return MoveEvaluation(
        ply=ply,
        eval_cp=0,
        mate_in=None,
        best_move_uci="e2e4",
        pv=[],
        classification=classification,
        eval_swing_cp=150,
        is_critical_moment=critical,
        deep_analyzed=False,
    )


class TestExtractFactsSummaryAndOpening:
    def test_summary_fact_always_present(self) -> None:
        facts = extract_facts(
            game=_game(GameColor.WHITE), analysis=_analysis(), opening=None, motifs=[], themes=[]
        )
        assert any(f.id == "summary" for f in facts)

    def test_opening_fact_present_only_when_a_match_exists(self) -> None:
        opening = OpeningMatch(eco="C60", opening_name="Ruy Lopez", epd="fen", matched_ply=4)
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(),
            opening=opening,
            motifs=[],
            themes=[],
        )
        assert any(f.id == "opening" for f in facts)

        no_opening_facts = extract_facts(
            game=_game(GameColor.WHITE), analysis=_analysis(), opening=None, motifs=[], themes=[]
        )
        assert not any(f.id == "opening" for f in no_opening_facts)


class TestExtractFactsMoves:
    def test_only_notable_classifications_become_facts(self) -> None:
        evaluations = [
            _move(0, MoveClassification.BEST),
            _move(2, MoveClassification.GOOD),
            _move(4, MoveClassification.INACCURACY),
            _move(6, MoveClassification.MISTAKE),
            _move(8, MoveClassification.BLUNDER),
        ]
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
        )
        move_ids = {f.id for f in facts if f.kind == "move"}
        assert move_ids == {"move-4", "move-6", "move-8"}

    def test_only_the_players_own_moves_are_candidates_when_side_is_known(self) -> None:
        # ply 0 = White's move, ply 1 = Black's move (0-indexed).
        evaluations = [_move(0, MoveClassification.BLUNDER), _move(1, MoveClassification.BLUNDER)]
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
        )
        move_ids = {f.id for f in facts if f.kind == "move"}
        assert move_ids == {"move-0"}

    def test_every_notable_move_is_a_candidate_when_side_is_unknown(self) -> None:
        evaluations = [_move(0, MoveClassification.BLUNDER), _move(1, MoveClassification.BLUNDER)]
        facts = extract_facts(
            game=_game(None), analysis=_analysis(evaluations), opening=None, motifs=[], themes=[]
        )
        move_ids = {f.id for f in facts if f.kind == "move"}
        assert move_ids == {"move-0", "move-1"}

    def test_blunder_and_critical_moment_are_critical_severity(self) -> None:
        evaluations = [
            _move(0, MoveClassification.BLUNDER),
            _move(2, MoveClassification.MISTAKE, critical=True),
            _move(4, MoveClassification.INACCURACY),
        ]
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
        )
        by_id = {f.id: f for f in facts if f.kind == "move"}
        assert by_id["move-0"].severity == "critical"
        assert by_id["move-2"].severity == "critical"
        assert by_id["move-4"].severity == "notable"


class TestExtractFactsMotifsAndThemes:
    def test_motif_facts_use_the_shared_polarity_rule(self) -> None:
        own_fork = MotifFinding(
            ply=10, side=GameColor.WHITE, motif=MotifType.FORK, confidence=0.9, evidence={}
        )
        suffered_fork = MotifFinding(
            ply=12, side=GameColor.BLACK, motif=MotifType.FORK, confidence=0.9, evidence={}
        )
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(),
            opening=None,
            motifs=[own_fork, suffered_fork],
            themes=[],
        )
        motif_ids = {f.id for f in facts if f.kind == "motif"}
        assert motif_ids == {"motif-fork-12"}

    def test_theme_facts_exclude_achievements(self) -> None:
        weakness = StrategicThemeFinding(
            ply=20,
            side=GameColor.WHITE,
            theme=StrategicThemeType.BAD_BISHOP,
            confidence=0.6,
            evidence={},
        )
        achievement = StrategicThemeFinding(
            ply=22,
            side=GameColor.WHITE,
            theme=StrategicThemeType.OPEN_FILE_CONTROL,
            confidence=0.6,
            evidence={},
        )
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(),
            opening=None,
            motifs=[],
            themes=[weakness, achievement],
        )
        theme_ids = {f.id for f in facts if f.kind == "theme"}
        assert theme_ids == {"theme-bad_bishop-20"}
