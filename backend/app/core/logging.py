"""Structured logging setup.

JSON in production so logs are machine-parseable by whatever aggregator Phase 17 picks;
human-readable console output in development. Request and trace ids are bound to the
context in Phase 17 — the plumbing here is deliberately minimal for now.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import AppSettings


def configure_logging(settings: AppSettings) -> None:
    """Configure structlog and the stdlib logging bridge.

    Called once at application startup. Safe to call again in tests.
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level, force=True)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    # Production emits JSON; development gets colourised key-value output that is far
    # easier to read while iterating.
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for a module."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]


__all__ = ["configure_logging", "get_logger"]
