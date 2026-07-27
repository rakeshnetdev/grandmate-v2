"""AnalysisService orchestration tests: tiered policy, persistence, summary.

Uses a fake `EngineAdapter` with canned per-(fen, depth) responses rather than real
Stockfish — these tests are about the *policy* (does a critical swing trigger a deep
pass, is each position evaluated exactly once, is the summary correct), not analysis
quality, which `tests/test_engine_stockfish.py` and the real-engine smoke test below
already cover.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import EngineSettings
from app.db.models import (
    Game,
    GameMove,
    GameSource,
    MoveClassification,
    MoveEvaluation,
    Profile,
    ProfileKind,
    User,
)
from app.domain.analysis.service import AnalysisService
from app.integrations.engine import EngineEvaluation


class FakeEngine:
    """Returns a canned `EngineEvaluation` for each `(fen, depth)` pair, and records
    every call made — tests assert against `.calls` to verify the tiered policy's
    actual behaviour, not just its final output."""

    def __init__(self, responses: dict[tuple[str, int], EngineEvaluation]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, int]] = []

    async def analyse(self, fen: str, *, depth: int) -> EngineEvaluation:
        self.calls.append((fen, depth))
        return self._responses[(fen, depth)]

    async def quit(self) -> None:
        pass


def _eval(cp: int, best: str = "e2e4") -> EngineEvaluation:
    return EngineEvaluation(eval_cp=cp, mate_in=None, best_move_uci=best, pv=[best])


async def _make_profile(session: AsyncSession) -> Profile:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


async def _make_game_with_moves(session: AsyncSession, profile: Profile, fens: list[str]) -> Game:
    """`fens` has N+1 entries for an N-move game: fens[i] is the position before ply i
    and after ply i-1. Moves themselves are placeholders — the fake engine only cares
    about FEN + depth, and classification only cares about UCI equality with best_move,
    which these tests set independently per case."""
    game = Game(
        profile_id=profile.id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "A", "Black": "B"},
        raw_pgn_path="pgn/test.pgn",
    )
    session.add(game)
    await session.flush()

    for ply in range(len(fens) - 1):
        session.add(
            GameMove(
                game_id=game.id,
                ply=ply,
                san=f"move{ply}",
                uci=f"uci{ply}",
                fen_before=fens[ply],
                fen_after=fens[ply + 1],
                epd_after=fens[ply + 1].rsplit(" ", 2)[0],
            )
        )
    await session.flush()
    return game


class TestTieredPolicy:
    async def test_each_position_is_evaluated_exactly_once_at_shallow_depth(
        self, db_session: AsyncSession
    ) -> None:
        """N+1 positions for N plies, not 2N — fen_after[i] == fen_before[i+1] must not
        be evaluated twice."""
        profile = await _make_profile(db_session)
        fens = ["fen0", "fen1", "fen2", "fen3"]  # 3 plies
        game = await _make_game_with_moves(db_session, profile, fens)
        settings = EngineSettings(critical_swing_cp=999_999)  # nothing crosses this
        engine = FakeEngine(
            {(fen, settings.engine_depth): _eval(0, best=f"uci{i}") for i, fen in enumerate(fens)}
        )
        service = AnalysisService(db_session, engine, settings)

        await service.analyze_game(game.id)

        shallow_calls = [c for c in engine.calls if c[1] == settings.engine_depth]
        assert len(shallow_calls) == 4  # 4 positions for 3 plies
        assert len(set(shallow_calls)) == 4  # each position exactly once

    async def test_a_critical_swing_triggers_a_deep_pass_on_the_resulting_position(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        fens = ["fen0", "fen1", "fen2"]  # 2 plies
        game = await _make_game_with_moves(db_session, profile, fens)
        settings = EngineSettings(critical_swing_cp=100)
        engine = FakeEngine(
            {
                # fen0: +50 for White (side to move at ply 0).
                ("fen0", settings.engine_depth): _eval(50, best="uci0"),
                # fen1: +200 for Black (side to move after ply 0) — White dropped from
                # +50 to -200 in its own frame, a 250cp swing: cpl = 50 - (-200) = 250.
                ("fen1", settings.engine_depth): _eval(200, best="uci1"),
                # fen2: -190 for White (side to move after ply 1) — Black held onto
                # roughly the same advantage, so ply 1 itself is not a critical swing:
                # cpl = 200 - 190 = 10.
                ("fen2", settings.engine_depth): _eval(-190, best="uci2"),
                # Deep pass re-evaluates fen1 (the position after the critical ply 0).
                ("fen1", settings.engine_deep_depth): _eval(190, best="uci1"),
            }
        )
        service = AnalysisService(db_session, engine, settings)

        analysis = await service.analyze_game(game.id)

        deep_calls = [c for c in engine.calls if c[1] == settings.engine_deep_depth]
        assert deep_calls == [("fen1", settings.engine_deep_depth)]

        moves = (
            (
                await db_session.execute(
                    select(MoveEvaluation)
                    .where(MoveEvaluation.game_analysis_id == analysis.id)
                    .order_by(MoveEvaluation.ply)
                )
            )
            .scalars()
            .all()
        )
        assert moves[0].is_critical_moment is True
        assert moves[0].deep_analyzed is True
        assert moves[0].eval_swing_cp == 50 - (-190)  # recomputed off the deepened eval
        # ply 1's eval_before is fen1 — also deep-analyzed, since it's the same position.
        assert moves[1].deep_analyzed is True
        assert moves[1].is_critical_moment is False

    async def test_no_critical_swings_means_no_deep_calls(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        fens = ["fen0", "fen1"]
        game = await _make_game_with_moves(db_session, profile, fens)
        settings = EngineSettings(critical_swing_cp=100)
        engine = FakeEngine(
            {
                ("fen0", settings.engine_depth): _eval(10, best="uci0"),
                ("fen1", settings.engine_depth): _eval(-5, best="uci1"),
            }
        )
        service = AnalysisService(db_session, engine, settings)

        await service.analyze_game(game.id)

        deep_calls = [c for c in engine.calls if c[1] == settings.engine_deep_depth]
        assert deep_calls == []


class TestPersistenceAndSummary:
    async def test_persists_game_analysis_and_move_evaluations(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        fens = ["fen0", "fen1"]
        game = await _make_game_with_moves(db_session, profile, fens)
        settings = EngineSettings(critical_swing_cp=999_999)
        engine = FakeEngine(
            {
                ("fen0", settings.engine_depth): _eval(0, best="uci0"),
                ("fen1", settings.engine_depth): _eval(0, best="uci1"),
            }
        )
        service = AnalysisService(db_session, engine, settings)

        analysis = await service.analyze_game(game.id)
        await db_session.flush()

        assert analysis.game_id == game.id
        assert analysis.engine_depth == settings.engine_depth
        assert analysis.completed_at is not None

        moves = (
            (
                await db_session.execute(
                    select(MoveEvaluation).where(MoveEvaluation.game_analysis_id == analysis.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(moves) == 1
        assert moves[0].classification == MoveClassification.BEST

    async def test_summary_counts_classifications(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        # Move 0 (uci0 -> best) is BEST. Move 1 played "other" against a big swing ->
        # should land as a worse classification.
        fens = ["fen0", "fen1", "fen2"]
        game = await _make_game_with_moves(db_session, profile, fens)
        settings = EngineSettings(critical_swing_cp=999_999)
        engine = FakeEngine(
            {
                ("fen0", settings.engine_depth): _eval(0, best="uci0"),
                ("fen1", settings.engine_depth): _eval(0, best="other"),
                # +400 for White (side to move after Black's ply 1) means Black's move
                # was a severe blunder — cpl = 0 - (-400) = 400.
                ("fen2", settings.engine_depth): _eval(400, best="uci2"),
            }
        )
        service = AnalysisService(db_session, engine, settings)

        analysis = await service.analyze_game(game.id)

        assert analysis.summary["total_moves"] == 2
        assert analysis.summary["counts"]["best"] == 1
        assert analysis.summary["counts"]["blunder"] == 1
        assert analysis.summary["accuracy"] == 50.0

    async def test_raises_for_a_game_with_no_moves(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = Game(
            profile_id=profile.id,
            source=GameSource.UPLOAD,
            content_hash=str(uuid.uuid4()),
            headers={},
            raw_pgn_path="pgn/empty.pgn",
        )
        db_session.add(game)
        await db_session.flush()
        engine = FakeEngine({})
        service = AnalysisService(db_session, engine, EngineSettings())

        with pytest.raises(ValueError, match="no canonicalized moves"):
            await service.analyze_game(game.id)
