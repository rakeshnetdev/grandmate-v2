"""Request tracing middleware.

Creates one trace per request, binds it to the context so any code beneath can record
spans without being passed a recorder, and returns the trace id in the ``X-Trace-Id``
response header.

The trace is **not** embedded in the response body. That is the central design decision
(ADR-0013): the reference implementation shipped its developer-insight payload inline on
every response, which put prompt text and retrieved context on the hot path in
production. Here the response carries a 16-character header, and the panel fetches the
full trace on demand only when a developer opens it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.devinsight import (
    Span,
    SpanKind,
    SpanStatus,
    TraceRecorder,
    TraceStore,
    bind_recorder,
    reset_recorder,
)

TRACE_HEADER = "X-Trace-Id"


class DevInsightMiddleware(BaseHTTPMiddleware):
    """Binds a trace recorder for the duration of each request."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        store: TraceStore,
        max_spans: int,
        capture_sensitive: bool,
    ) -> None:
        super().__init__(app)
        self._store = store
        self._max_spans = max_spans
        self._capture_sensitive = capture_sensitive

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started_at = datetime.now(UTC)
        recorder = TraceRecorder(
            label=f"{request.method} {request.url.path}",
            max_spans=self._max_spans,
            capture_sensitive=self._capture_sensitive,
        )
        token = bind_recorder(recorder)

        try:
            response = await call_next(request)
        except Exception:
            # Store the failed trace before re-raising — a trace of a crash is the most
            # useful trace there is.
            trace = recorder.finish(SpanStatus.ERROR)
            trace.spans.insert(0, self._http_span(request, None, started_at, trace.duration_ms))
            self._store.add(trace)
            raise
        finally:
            reset_recorder(token)

        status = SpanStatus.ERROR if response.status_code >= 500 else SpanStatus.OK
        trace = recorder.finish(status)
        # Inserted first so the panel shows the request as the root of the timeline,
        # even though its duration is only known at the end.
        trace.spans.insert(0, self._http_span(request, response, started_at, trace.duration_ms))
        self._store.add(trace)

        response.headers[TRACE_HEADER] = trace.trace_id
        return response

    @staticmethod
    def _http_span(
        request: Request,
        response: Response | None,
        started_at: datetime,
        duration_ms: float,
    ) -> Span:
        """The root span describing the request itself."""
        status_code = response.status_code if response is not None else 500
        return Span(
            kind=SpanKind.HTTP,
            name=f"{request.method} {request.url.path}",
            started_at=started_at,
            duration_ms=duration_ms,
            status=SpanStatus.ERROR if status_code >= 500 else SpanStatus.OK,
            attributes={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
            },
        )


__all__ = ["TRACE_HEADER", "DevInsightMiddleware"]
