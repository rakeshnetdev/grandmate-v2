"""StockfishEngine integration tests: a real engine process, real UCI I/O.

Depth kept low (6) throughout — these test the adapter's plumbing (does it start, does it
parse scores correctly, does it time out, does it shut down cleanly), not analysis
quality. Skips cleanly if Stockfish is not installed at the configured path, same
philosophy as the Postgres-dependent tests skipping when the database is not reachable.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import chess
import pytest
import pytest_asyncio

from app.core.config import EngineSettings
from app.integrations.engine import EngineError, EngineTimeoutError, StockfishEngine

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# White to move, black just delivered fool's mate — no legal moves for White.
CHECKMATE_FEN = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"

pytestmark = pytest.mark.skipif(
    not os.path.exists(EngineSettings().stockfish_path),
    reason="Stockfish not found — set STOCKFISH_PATH",
)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[StockfishEngine]:
    e = StockfishEngine(EngineSettings())
    await e.start()
    yield e
    await e.quit()


class TestAnalyse:
    async def test_evaluates_the_starting_position(self, engine: StockfishEngine) -> None:
        result = await engine.analyse(STARTING_FEN, depth=6)

        assert result.eval_cp is not None
        assert result.mate_in is None
        assert result.best_move_uci is not None
        assert len(result.pv) > 0

    async def test_detects_an_already_delivered_checkmate(self, engine: StockfishEngine) -> None:
        result = await engine.analyse(CHECKMATE_FEN, depth=6)

        assert result.eval_cp is None
        assert result.mate_in == 0
        assert result.best_move_uci is None
        assert result.pv == []

    async def test_independent_engine_instances_agree_at_the_same_depth(self) -> None:
        """The real reproducibility contract: `dispatch.py` starts a fresh engine per
        job, so what must hold is two *separate* cold-started engines agreeing — not a
        single warm engine repeating the identical query.

        That second, stronger-sounding property does **not** hold: a warm engine's hash
        table carries state between calls, and re-querying the exact same position
        immediately afterwards can return a slightly different eval/PV as a result — a
        real, verified nuance (not a flake), which is exactly why this test uses two
        independent engines rather than one engine queried twice.
        """
        settings = EngineSettings()
        first_engine = StockfishEngine(settings)
        await first_engine.start()
        try:
            first = await first_engine.analyse(STARTING_FEN, depth=8)
        finally:
            await first_engine.quit()

        second_engine = StockfishEngine(settings)
        await second_engine.start()
        try:
            second = await second_engine.analyse(STARTING_FEN, depth=8)
        finally:
            await second_engine.quit()

        assert first == second

    async def test_best_move_is_legal(self, engine: StockfishEngine) -> None:
        """Legal-line validation (Phase 5 evaluation criterion): whatever the engine
        proposes must actually be playable from the position given."""
        result = await engine.analyse(STARTING_FEN, depth=6)

        board = chess.Board(STARTING_FEN)
        assert result.best_move_uci is not None
        assert chess.Move.from_uci(result.best_move_uci) in board.legal_moves

    async def test_pv_is_a_fully_legal_line(self, engine: StockfishEngine) -> None:
        result = await engine.analyse(STARTING_FEN, depth=8)

        board = chess.Board(STARTING_FEN)
        for uci in result.pv:
            move = chess.Move.from_uci(uci)
            assert move in board.legal_moves, f"{uci} illegal at {board.fen()}"
            board.push(move)


class TestTimeout:
    async def test_analysis_exceeding_the_timeout_raises(self) -> None:
        settings = EngineSettings(engine_timeout_s=0)
        engine = StockfishEngine(settings)
        await engine.start()
        try:
            with pytest.raises(EngineTimeoutError):
                await engine.analyse(STARTING_FEN, depth=20)
        finally:
            await engine.quit()


class TestLifecycle:
    async def test_analysing_before_start_raises(self) -> None:
        engine = StockfishEngine(EngineSettings())
        with pytest.raises(EngineError, match="not started"):
            await engine.analyse(STARTING_FEN, depth=6)

    async def test_quit_is_safe_to_call_twice(self, engine: StockfishEngine) -> None:
        await engine.quit()
        await engine.quit()  # must not raise

    async def test_missing_stockfish_binary_raises_engine_error(self) -> None:
        settings = EngineSettings(stockfish_path="/nonexistent/stockfish-binary")
        engine = StockfishEngine(settings)
        with pytest.raises(EngineError):
            await engine.start()
