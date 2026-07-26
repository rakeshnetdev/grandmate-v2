"""Developer insight trace models.

A trace is one request (or one background job). A span is one measured step inside it —
an engine evaluation, a retrieval, an LLM call, a graph node.

These models deliberately do **not** import from ``app.integrations.llm``. Token counts
are declared locally so the dependency points one way: the LLM adapter records into
devinsight, never the reverse.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SpanKind(StrEnum):
    """What kind of work a span measured.

    Drives the tab grouping in the frontend panel. Values are added as the phases that
    produce them land.
    """

    HTTP = "http"
    DB = "db"
    ENGINE = "engine"
    RETRIEVAL = "retrieval"
    LLM = "llm"
    GRAPH_NODE = "graph_node"
    AGENT = "agent"
    GROUNDING = "grounding"
    JOB = "job"


class SpanStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class TokenCount(BaseModel):
    """Token usage as reported by the provider.

    These numbers come from the provider's own response — they are never estimated with a
    local tokenizer, and never fetched with a separate API call. Measuring token usage
    must not itself cost tokens.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class Span(BaseModel):
    """One measured step."""

    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_span_id: str | None = None
    kind: SpanKind
    name: str
    started_at: datetime
    duration_ms: float
    status: SpanStatus = SpanStatus.OK
    error: str | None = None
    # Bounded at record time — see recorder._sanitise.
    attributes: dict[str, Any] = Field(default_factory=dict)
    tokens: TokenCount | None = None


class Trace(BaseModel):
    """One request or job, and everything measured inside it."""

    trace_id: str
    label: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = 0.0
    status: SpanStatus = SpanStatus.OK
    spans: list[Span] = Field(default_factory=list)
    # Set when the span cap is hit, so a truncated trace never looks complete.
    truncated: bool = False

    @property
    def total_tokens(self) -> TokenCount:
        """Sum token usage across every LLM span in the trace."""
        total = TokenCount()
        for span in self.spans:
            if span.tokens is not None:
                total.prompt_tokens += span.tokens.prompt_tokens
                total.completion_tokens += span.tokens.completion_tokens
        return total


class TraceSummary(BaseModel):
    """Listing entry. Deliberately small — the list endpoint must stay cheap."""

    trace_id: str
    label: str
    started_at: datetime
    duration_ms: float
    status: SpanStatus
    span_count: int
    total_tokens: int


__all__ = [
    "Span",
    "SpanKind",
    "SpanStatus",
    "TokenCount",
    "Trace",
    "TraceSummary",
]
