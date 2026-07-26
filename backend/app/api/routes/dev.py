"""Developer insight routes.

Registered **only** when developer insight is active, which
``Settings.dev_insight_active`` forces off in production. These endpoints expose request
internals and are unauthenticated until Phase 2 adds an auth layer, so they must not be
reachable on a deployed environment.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.devinsight import Trace, TraceStore, TraceSummary

router = APIRouter(prefix="/dev", tags=["developer-insight"])


def _store(request: Request) -> TraceStore:
    """The store built in ``create_app``, reachable from app state."""
    store: TraceStore = request.app.state.trace_store
    return store


@router.get("/traces", response_model=list[TraceSummary])
async def list_traces(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TraceSummary]:
    """Recent traces, newest first.

    Returns summaries rather than full traces so opening the panel does not serialise
    every span of every retained request.
    """
    return _store(request).list(limit=limit)


@router.get("/traces/{trace_id}", response_model=Trace)
async def get_trace(request: Request, trace_id: str) -> Trace:
    """One full trace, including every span."""
    trace = _store(request).get(trace_id)
    if trace is None:
        # Traces live in a bounded ring buffer, so "not found" usually means "aged out"
        # rather than "never existed". Say so, since the distinction matters to whoever
        # is debugging.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found. It may have been evicted from the buffer.",
        )
    return trace


@router.delete("/traces", status_code=status.HTTP_204_NO_CONTENT)
async def clear_traces(request: Request) -> None:
    """Empty the buffer. Useful before reproducing a specific problem."""
    _store(request).clear()


__all__ = ["router"]
