"""Rate limiting middleware (Phase 17)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
import time
from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter per client IP."""

    def __init__(self, app: ASGIApp, limit_per_minute: int = 60) -> None:
        super().__init__(app)
        self._limit = limit_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Fast path for testing or if limit is disabled (<= 0)
        if self._limit <= 0:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        now = time.time()
        window_start = now - 60.0

        # Remove requests outside the 60-second window
        self._requests[client_ip] = [ts for ts in self._requests[client_ip] if ts > window_start]

        if len(self._requests[client_ip]) >= self._limit:
            return Response(
                content="Rate limit exceeded. Please try again later.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="text/plain",
            )

        self._requests[client_ip].append(now)
        return await call_next(request)


__all__ = ["RateLimitMiddleware"]
