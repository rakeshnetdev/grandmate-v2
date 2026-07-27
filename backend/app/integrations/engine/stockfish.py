"""Stockfish adapter via python-chess's async UCI protocol (ADR-0004).

Deliberately the async engine API (`chess.engine.popen_uci`), not the synchronous
`SimpleEngine` the reference implementation used — analysis runs inside a FastAPI
background task on the app's own event loop, and a blocking call there would stall every
other request the server is handling while Stockfish thinks.
"""

from __future__ import annotations

import asyncio
import contextlib

import chess
import chess.engine

from app.core.config import EngineSettings
from app.integrations.engine.base import EngineError, EngineEvaluation, EngineTimeoutError


class StockfishEngine:
    """One Stockfish process, single-threaded for reproducibility (see `EngineSettings`).

    One instance per game being analysed, not shared across concurrent games — bounded
    concurrency at the game level (`ENGINE_MAX_CONCURRENT_GAMES`) means each concurrent
    analysis owns its own process.
    """

    def __init__(self, settings: EngineSettings) -> None:
        self._settings = settings
        self._transport: asyncio.SubprocessTransport | None = None
        self._protocol: chess.engine.UciProtocol | None = None

    async def start(self) -> None:
        try:
            transport, protocol = await chess.engine.popen_uci(self._settings.stockfish_path)
        except FileNotFoundError as exc:
            raise EngineError(f"Stockfish not found at {self._settings.stockfish_path!r}") from exc
        await protocol.configure(
            {"Threads": self._settings.engine_threads, "Hash": self._settings.engine_hash_mb}
        )
        self._transport = transport
        self._protocol = protocol

    async def analyse(self, fen: str, *, depth: int) -> EngineEvaluation:
        if self._protocol is None:
            raise EngineError("Engine not started — call start() first")

        board = chess.Board(fen)
        try:
            info = await asyncio.wait_for(
                self._protocol.analyse(board, chess.engine.Limit(depth=depth)),
                timeout=self._settings.engine_timeout_s,
            )
        except TimeoutError as exc:
            raise EngineTimeoutError(
                f"Analysis of {fen!r} at depth {depth} exceeded {self._settings.engine_timeout_s}s"
            ) from exc
        except chess.engine.EngineError as exc:
            raise EngineError(str(exc)) from exc

        pv_moves = info.get("pv", [])
        pv_uci = [move.uci() for move in pv_moves]
        best_move_uci = pv_uci[0] if pv_uci else None

        score = info.get("score")
        if score is None:
            # No legal moves: checkmate or stalemate. Not a failure — a real, final
            # position that simply has nothing left to evaluate a move for.
            return EngineEvaluation(eval_cp=None, mate_in=None, best_move_uci=None, pv=[])

        pov_score = score.pov(board.turn)
        if pov_score.is_mate():
            return EngineEvaluation(
                eval_cp=None, mate_in=pov_score.mate(), best_move_uci=best_move_uci, pv=pv_uci
            )
        return EngineEvaluation(
            eval_cp=pov_score.score(), mate_in=None, best_move_uci=best_move_uci, pv=pv_uci
        )

    async def quit(self) -> None:
        """Shut down the engine process, best-effort.

        `protocol.quit()` sends the UCI `quit` command and waits for the process to exit
        — but after a timed-out analysis the process may already be wedged, so this never
        lets a slow or unresponsive shutdown stop the transport from being closed.
        Without the explicit `transport.close()`, the underlying subprocess pipes are
        left for the garbage collector, which raises `ResourceWarning` (a hard failure
        under this project's `filterwarnings=error`) at an unpredictable, un-awaitable
        later time instead of here.
        """
        if self._protocol is not None:
            with contextlib.suppress(TimeoutError, chess.engine.EngineError):
                await asyncio.wait_for(self._protocol.quit(), timeout=5)
            self._protocol = None
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    async def __aenter__(self) -> StockfishEngine:
        await self.start()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.quit()


__all__ = ["StockfishEngine"]
