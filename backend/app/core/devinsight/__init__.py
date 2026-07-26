"""Developer insight: in-process request tracing for debugging.

Instrument any code path like this — no ``if enabled`` guard needed, because the recorder
is a no-op object when disabled:

    from app.core.devinsight import SpanKind, get_recorder

    with get_recorder().span(SpanKind.ENGINE, "evaluate", ply=23) as span:
        result = engine.analyse(position)
        if span:
            span.set(eval_cp=result.score)

See ADR-0013 for the design and its constraints.
"""

from app.core.devinsight.models import (
    Span,
    SpanKind,
    SpanStatus,
    TokenCount,
    Trace,
    TraceSummary,
)
from app.core.devinsight.recorder import (
    NULL_RECORDER,
    NullRecorder,
    SpanHandle,
    SpanRecorder,
    TraceRecorder,
    bind_recorder,
    get_recorder,
    reset_recorder,
)
from app.core.devinsight.store import TraceStore

__all__ = [
    "NULL_RECORDER",
    "NullRecorder",
    "Span",
    "SpanHandle",
    "SpanKind",
    "SpanRecorder",
    "SpanStatus",
    "TokenCount",
    "Trace",
    "TraceRecorder",
    "TraceStore",
    "TraceSummary",
    "bind_recorder",
    "get_recorder",
    "reset_recorder",
]
