"""Chess engine interface (ADR-0004).

Analysis code depends on this Protocol, never on `python-chess`'s engine module or a
concrete Stockfish process directly — the same shape as `StorageBackend`. A future
alternative engine, or a test double, is one adapter, not a rewrite of every caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class EngineError(RuntimeError):
    """Raised when the engine could not be reached or returned something unusable."""


class EngineTimeoutError(EngineError):
    """Raised when analysis exceeds `ENGINE_TIMEOUT_S`."""


@dataclass(frozen=True)
class EngineEvaluation:
    """One position's evaluation, from the side-to-move's point of view.

    Exactly one of `eval_cp`/`mate_in` is set. `mate_in` positive means the side to move
    delivers mate in that many moves; negative means they get mated in that many.
    """

    eval_cp: int | None
    mate_in: int | None
    best_move_uci: str | None
    pv: list[str]


@runtime_checkable
class EngineAdapter(Protocol):
    """What analysis code may assume about a chess engine."""

    async def start(self) -> None:
        """Initialize the engine (e.g. spawn the process). Must be called before
        `analyse`. Raises `EngineError` if the engine could not be started."""
        ...

    async def analyse(self, fen: str, *, depth: int) -> EngineEvaluation:
        """Evaluate the position at `fen` to `depth`. Raises `EngineError` on failure,
        `EngineTimeoutError` if it exceeds the configured timeout."""
        ...

    async def quit(self) -> None:
        """Terminate the underlying engine process. Safe to call more than once."""
        ...


__all__ = ["EngineAdapter", "EngineError", "EngineEvaluation", "EngineTimeoutError"]
