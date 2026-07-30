"""Unit tests for `domain/reports/facts.py`. In-memory model instances only, same
convention as `test_analytics_metrics.py`.
"""

from __future__ import annotations

import uuid

from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameMove,
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
    ply: int,
    classification: MoveClassification,
    *,
    critical: bool = False,
    eval_swing_cp: int = 150,
    mate_swing: bool = False,
) -> MoveEvaluation:
    return MoveEvaluation(
        ply=ply,
        eval_cp=0,
        mate_in=None,
        best_move_uci="e2e4",
        pv=[],
        classification=classification,
        eval_swing_cp=eval_swing_cp,
        mate_swing=mate_swing,
        is_critical_moment=critical,
        best_move_san="Nf3",
        deep_analyzed=False,
    )


def _game_move(ply: int, san: str) -> GameMove:
    return GameMove(
        game_id=uuid.uuid4(),
        ply=ply,
        san=san,
        uci="e2e4",
        fen_before="fen-before",
        fen_after="fen-after",
        epd_after="epd-after",
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

    def test_a_mate_swing_never_carries_its_sentinel_derived_number(self) -> None:
        """Regression test: a move fact for a mate-involving swing must not surface the
        classification-only sentinel value as if it were a real centipawn count."""
        evaluations = [_move(0, MoveClassification.BLUNDER, eval_swing_cp=99_470, mate_swing=True)]
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
        )
        move_fact = next(f for f in facts if f.id == "move-0")
        assert move_fact.data["mate_swing"] is True
        assert move_fact.data["eval_swing_cp"] is None

    def test_moves_by_ply_supplies_the_played_moves_san(self) -> None:
        evaluations = [_move(4, MoveClassification.BLUNDER)]
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
            moves_by_ply={4: _game_move(4, "Qxe4")},
        )
        move_fact = next(f for f in facts if f.id == "move-4")
        assert move_fact.data["san"] == "Qxe4"
        assert move_fact.data["best_move_san"] == "Nf3"

    def test_a_ply_missing_from_moves_by_ply_has_a_null_san(self) -> None:
        evaluations = [_move(4, MoveClassification.BLUNDER)]
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
        )
        move_fact = next(f for f in facts if f.id == "move-4")
        assert move_fact.data["san"] is None


class TestExtractFactsPositiveMoves:
    """A BEST move becomes a "strength" fact only when it also landed a real tactic
    (a motif finding at the same ply) — not `is_critical_moment`, which is defined by a
    large centipawn *loss* a BEST move (near-zero loss, by definition) essentially never
    has. Verified against the real dev database: 0 of 1928 BEST-classified rows there
    were ever also `is_critical_moment`, which is what caught this originally."""

    def test_a_best_move_that_landed_a_tactic_becomes_a_strength_fact(self) -> None:
        evaluations = [_move(6, MoveClassification.BEST)]
        fork = MotifFinding(
            ply=6, side=GameColor.WHITE, motif=MotifType.FORK, confidence=0.9, evidence={}
        )
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[fork],
            themes=[],
            moves_by_ply={6: _game_move(6, "Qxe4")},
        )
        move_fact = next(f for f in facts if f.id == "move-6")
        assert move_fact.data["classification"] == "best"
        assert move_fact.data["san"] == "Qxe4"
        assert move_fact.data["motif"] == "fork"

    def test_a_routine_best_move_with_no_tactic_is_not_a_fact(self) -> None:
        """Most BEST moves in a game are unremarkable book/obvious moves — only ones
        that landed a real tactic are worth a "What Went Well" bullet."""
        evaluations = [_move(6, MoveClassification.BEST)]
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[],
            themes=[],
        )
        assert not any(f.kind == "move" for f in facts)

    def test_a_self_inflicted_motif_at_the_same_ply_does_not_count(self) -> None:
        """HANGING_PIECE is the mover's own blunder, not a tactic they landed — a BEST
        move can't plausibly coincide with one, but the exclusion is still asserted
        directly so the criterion doesn't silently invert if SELF_INFLICTED_MOTIFS
        grows."""
        evaluations = [_move(6, MoveClassification.BEST)]
        hanging = MotifFinding(
            ply=6, side=GameColor.WHITE, motif=MotifType.HANGING_PIECE, confidence=0.9, evidence={}
        )
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[hanging],
            themes=[],
        )
        assert not any(f.kind == "move" for f in facts)

    def test_a_tactic_suffered_by_the_mover_does_not_count(self) -> None:
        """The motif must be on the mover's own side — a tactic the *opponent* landed
        against them at a nearby ply must not be mistaken for the mover's own strength."""
        evaluations = [_move(6, MoveClassification.BEST)]
        fork_against_mover = MotifFinding(
            ply=6, side=GameColor.BLACK, motif=MotifType.FORK, confidence=0.9, evidence={}
        )
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=[fork_against_mover],
            themes=[],
        )
        assert not any(f.kind == "move" for f in facts)

    def test_only_the_players_own_best_moves_are_candidates_when_side_is_known(self) -> None:
        evaluations = [
            _move(0, MoveClassification.BEST),
            _move(1, MoveClassification.BEST),
        ]
        motifs = [
            MotifFinding(
                ply=0, side=GameColor.WHITE, motif=MotifType.FORK, confidence=0.9, evidence={}
            ),
            MotifFinding(
                ply=1, side=GameColor.BLACK, motif=MotifType.FORK, confidence=0.9, evidence={}
            ),
        ]
        facts = extract_facts(
            game=_game(GameColor.WHITE),
            analysis=_analysis(evaluations),
            opening=None,
            motifs=motifs,
            themes=[],
        )
        move_ids = {f.id for f in facts if f.kind == "move"}
        assert move_ids == {"move-0"}


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
