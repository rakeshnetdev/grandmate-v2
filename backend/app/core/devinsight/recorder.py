"""Trace recording.

Design constraints, both stated by the project owner:

1. **No LLM cost.** The recorder only stores data the system already produced — node
   names, durations, retrieval hit counts, and the provider's own reported token usage.
   It never calls a model, never runs a tokenizer, and never estimates anything.
2. **No meaningful latency.** Recording a span is a ``perf_counter()`` read and a list
   append. Nothing is serialised, nothing touches I/O, nothing crosses the network on the
   request path. Traces are serialised only when someone opens the panel and fetches one.

When disabled, ``get_recorder()`` returns a null object whose ``span()`` is a
``nullcontext``, so instrumented call sites cost an attribute lookup and nothing else.
That is why call sites can be written unconditionally, without ``if enabled`` guards
scattered through domain code.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol

from app.core.devinsight.models import Span, SpanKind, SpanStatus, TokenCount, Trace

# Attribute values longer than this are truncated. Prevents a stray prompt or a large
# retrieval payload from pinning memory in the ring buffer.
MAX_ATTRIBUTE_CHARS = 2000

# Attribute names treated as potentially sensitive. Redacted unless prompt capture is
# explicitly enabled. Matched as substrings, so `system_prompt` and `rag_context` match.
SENSITIVE_ATTRIBUTE_HINTS = ("prompt", "context", "message", "content", "answer", "query")


class SpanRecorder(Protocol):
    """What instrumented code may assume about a recorder."""

    def span(
        self, kind: SpanKind, name: str, **attributes: Any
    ) -> AbstractContextManager[SpanHandle | None]: ...

    def set_tokens(self, prompt_tokens: int, completion_tokens: int) -> None: ...


class SpanHandle:
    """Handle yielded by :meth:`TraceRecorder.span`.

    Lets a call site attach information discovered *during* the work — a hit count, a
    token usage, a chosen model — rather than only what was known up front.
    """

    def __init__(self, span: Span) -> None:
        self._span = span

    def set(self, **attributes: Any) -> None:
        self._span.attributes.update(attributes)

    def set_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        self._span.tokens = TokenCount(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        )


class TraceRecorder:
    """Collects spans for a single trace.

    Not thread-safe by design: one recorder belongs to one request, bound through a
    contextvar. Sharing one across threads would mean sharing a request, which would be a
    bug regardless.
    """

    def __init__(
        self,
        label: str,
        *,
        trace_id: str | None = None,
        max_spans: int = 200,
        capture_sensitive: bool = False,
    ) -> None:
        self.trace = Trace(trace_id=trace_id or uuid.uuid4().hex[:16], label=label)
        self._max_spans = max_spans
        self._capture_sensitive = capture_sensitive
        self._started = perf_counter()
        self._stack: list[str] = []

    # -- recording ---------------------------------------------------------

    @contextmanager
    def span(self, kind: SpanKind, name: str, **attributes: Any) -> Iterator[SpanHandle | None]:
        """Measure a block of work.

        Yields ``None`` once the span cap is reached, so a runaway loop cannot exhaust
        memory. Call sites must tolerate a ``None`` handle — hence the
        ``if handle: handle.set(...)`` pattern at instrumentation points.
        """
        if len(self.trace.spans) >= self._max_spans:
            self.trace.truncated = True
            yield None
            return

        # Attributes are stored raw here and sanitised exactly once when the span closes.
        # Sanitising at both ends would double-process: a redacted value would itself be
        # re-redacted, reporting the marker's length instead of the original's.
        span = Span(
            parent_span_id=self._stack[-1] if self._stack else None,
            kind=kind,
            name=name,
            started_at=datetime.now(UTC),
            duration_ms=0.0,
            attributes=dict(attributes),
        )
        handle = SpanHandle(span)
        self._stack.append(span.span_id)
        start = perf_counter()

        try:
            yield handle
        except Exception as exc:
            span.status = SpanStatus.ERROR
            span.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            span.duration_ms = (perf_counter() - start) * 1000
            # Single sanitisation point, covering both constructor attributes and
            # anything added later through the handle.
            span.attributes = self._sanitise(span.attributes)
            self._stack.pop()
            self.trace.spans.append(span)

    def set_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Attach token usage to the most recently completed span."""
        if self.trace.spans:
            self.trace.spans[-1].tokens = TokenCount(
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
            )

    def finish(self, status: SpanStatus = SpanStatus.OK) -> Trace:
        """Close the trace and return it."""
        self.trace.duration_ms = (perf_counter() - self._started) * 1000
        self.trace.status = status
        return self.trace

    # -- redaction ---------------------------------------------------------

    def _sanitise(self, attributes: dict[str, Any]) -> dict[str, Any]:
        """Truncate long values and redact sensitive ones.

        Redaction replaces the value with a length marker rather than dropping the key,
        so the panel still shows that a prompt was sent and how large it was — which is
        usually the diagnostically useful part anyway.
        """
        clean: dict[str, Any] = {}
        for key, value in attributes.items():
            if not self._capture_sensitive and self._is_sensitive(key):
                length = len(value) if isinstance(value, str) else None
                clean[key] = f"<redacted{f', {length} chars' if length is not None else ''}>"
                continue

            if isinstance(value, str) and len(value) > MAX_ATTRIBUTE_CHARS:
                clean[key] = f"{value[:MAX_ATTRIBUTE_CHARS]}… <truncated>"
            else:
                clean[key] = value
        return clean

    @staticmethod
    def _is_sensitive(key: str) -> bool:
        lowered = key.lower()
        return any(hint in lowered for hint in SENSITIVE_ATTRIBUTE_HINTS)


class NullRecorder:
    """No-op recorder used when developer insight is disabled.

    Every method is trivial so instrumented code pays effectively nothing in production.
    """

    def span(
        self, kind: SpanKind, name: str, **attributes: Any
    ) -> AbstractContextManager[SpanHandle | None]:
        return nullcontext(None)

    def set_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        return None


NULL_RECORDER = NullRecorder()

# Bound per request by the tracing middleware. Defaults to the null recorder so code
# running outside a request — a script, a test, a worker without tracing — works
# unchanged.
_current_recorder: ContextVar[SpanRecorder] = ContextVar("devinsight_recorder")


def get_recorder() -> SpanRecorder:
    """Return the recorder for the current context, or a no-op one."""
    return _current_recorder.get(NULL_RECORDER)


def bind_recorder(recorder: SpanRecorder) -> object:
    """Bind a recorder to the current context. Returns a token for :func:`reset_recorder`."""
    return _current_recorder.set(recorder)


def reset_recorder(token: object) -> None:
    """Restore the previous recorder."""
    _current_recorder.reset(token)  # type: ignore[arg-type]


__all__ = [
    "MAX_ATTRIBUTE_CHARS",
    "NULL_RECORDER",
    "NullRecorder",
    "SpanHandle",
    "SpanRecorder",
    "TraceRecorder",
    "bind_recorder",
    "get_recorder",
    "reset_recorder",
]
