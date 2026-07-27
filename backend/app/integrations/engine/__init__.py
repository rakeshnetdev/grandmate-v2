"""Chess engine adapters (ADR-0004)."""

from app.core.config import EngineSettings
from app.integrations.engine.base import (
    EngineAdapter,
    EngineError,
    EngineEvaluation,
    EngineTimeoutError,
)
from app.integrations.engine.stockfish import StockfishEngine


def build_engine(settings: EngineSettings) -> StockfishEngine:
    """Construct the configured engine. One factory, same reason as `build_storage`:
    callers depend on the Protocol, not a concrete class."""
    return StockfishEngine(settings)


__all__ = [
    "EngineAdapter",
    "EngineError",
    "EngineEvaluation",
    "EngineTimeoutError",
    "StockfishEngine",
    "build_engine",
]
