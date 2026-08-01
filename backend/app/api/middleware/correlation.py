"""Request correlation and log context middleware.

Assigns a unique request id and trace id to every inbound request, binds them
to structlog's context variables so all logs emitted during the request carry
them, and returns them in the response headers.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-Id"
TRACE_HEADER = "X-Trace-Id"


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware that injects request_id and trace_id into logging contextvars."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Extract from inbound headers, or generate fresh
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        trace_id = request.headers.get(TRACE_HEADER) or str(uuid.uuid4()).replace("-", "")[:16]

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
        )

        response = await call_next(request)

        # Propagate back to caller in headers
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


__all__ = ["REQUEST_ID_HEADER", "TRACE_HEADER", "CorrelationMiddleware"]
