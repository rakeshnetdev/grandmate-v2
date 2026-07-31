"""Context propagation helpers for correlation IDs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import functools
from typing import Any, TypeVar
import structlog

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def run_with_correlation(func: F) -> F:
    """Decorator that captures the request_id and trace_id from the current
    structlog context and binds them in the background task execution context.
    """
    context = structlog.contextvars.get_contextvars()
    request_id = context.get("request_id")
    trace_id = context.get("trace_id")

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        structlog.contextvars.clear_contextvars()
        if request_id or trace_id:
            structlog.contextvars.bind_contextvars(
                request_id=request_id,
                trace_id=trace_id,
            )
        return await func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
