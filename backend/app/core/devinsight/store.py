"""In-memory trace store.

A bounded ring buffer. Traces are a debugging aid, not a system of record — losing old
ones on restart is fine and expected, and keeping them out of Postgres avoids putting a
write on the request path purely for developer convenience.

Persistent tracing, if it is ever wanted, is a Phase 17 concern with a real backend
behind it.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock

from app.core.devinsight.models import Trace, TraceSummary


class TraceStore:
    """Fixed-capacity, thread-safe trace buffer.

    The lock is held only for the O(1) insert and lookup, which happen once per request,
    so contention is negligible even under load.
    """

    def __init__(self, max_traces: int = 50) -> None:
        self._max = max_traces
        self._traces: OrderedDict[str, Trace] = OrderedDict()
        self._lock = Lock()

    def add(self, trace: Trace) -> None:
        with self._lock:
            self._traces[trace.trace_id] = trace
            self._traces.move_to_end(trace.trace_id)
            while len(self._traces) > self._max:
                self._traces.popitem(last=False)

    def get(self, trace_id: str) -> Trace | None:
        with self._lock:
            return self._traces.get(trace_id)

    def list(self, limit: int = 50) -> list[TraceSummary]:
        """Most recent traces first."""
        with self._lock:
            traces = list(self._traces.values())

        return [
            TraceSummary(
                trace_id=trace.trace_id,
                label=trace.label,
                started_at=trace.started_at,
                duration_ms=trace.duration_ms,
                status=trace.status,
                span_count=len(trace.spans),
                total_tokens=trace.total_tokens.total,
            )
            for trace in reversed(traces[-limit:])
        ]

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._traces)


__all__ = ["TraceStore"]
