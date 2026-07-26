"""Trace recorder tests.

The two properties that matter most are the ones the owner asked for: recording must not
cost an LLM call, and must not cost meaningful latency. Neither is directly assertable,
so they are protected structurally instead — the recorder has no provider dependency at
all, and the null recorder is verified to be a genuine no-op.

Redaction and bounding are asserted directly, because those are the ways this feature
could leak data or exhaust memory.
"""

from __future__ import annotations

import pytest

from app.core.devinsight import (
    NULL_RECORDER,
    SpanKind,
    SpanStatus,
    TraceRecorder,
    bind_recorder,
    get_recorder,
    reset_recorder,
)
from app.core.devinsight.recorder import MAX_ATTRIBUTE_CHARS


def test_span_is_recorded_with_duration() -> None:
    recorder = TraceRecorder("test")

    with recorder.span(SpanKind.ENGINE, "evaluate", ply=23):
        pass

    trace = recorder.finish()
    assert len(trace.spans) == 1
    span = trace.spans[0]
    assert span.kind is SpanKind.ENGINE
    assert span.name == "evaluate"
    assert span.attributes["ply"] == 23
    assert span.duration_ms >= 0


def test_handle_can_attach_attributes_discovered_during_the_work() -> None:
    """The point of the handle: record what you learn, not only what you knew."""
    recorder = TraceRecorder("test")

    with recorder.span(SpanKind.RETRIEVAL, "search") as span:
        assert span is not None
        span.set(hits=7, bucket="tactics")

    attributes = recorder.finish().spans[0].attributes
    assert attributes["hits"] == 7
    assert attributes["bucket"] == "tactics"


def test_token_usage_is_attached_to_the_span() -> None:
    recorder = TraceRecorder("test")

    with recorder.span(SpanKind.LLM, "complete") as span:
        assert span is not None
        span.set_tokens(prompt_tokens=1200, completion_tokens=300)

    trace = recorder.finish()
    assert trace.spans[0].tokens is not None
    assert trace.spans[0].tokens.total == 1500
    assert trace.total_tokens.total == 1500


def test_total_tokens_sums_across_spans() -> None:
    recorder = TraceRecorder("test")

    for prompt, completion in ((100, 20), (200, 50)):
        with recorder.span(SpanKind.LLM, "complete") as span:
            assert span is not None
            span.set_tokens(prompt_tokens=prompt, completion_tokens=completion)

    total = recorder.finish().total_tokens
    assert total.prompt_tokens == 300
    assert total.completion_tokens == 70
    assert total.total == 370


def test_nested_spans_record_parent_ids() -> None:
    recorder = TraceRecorder("test")

    with recorder.span(SpanKind.AGENT, "supervisor") as outer:
        assert outer is not None
        with recorder.span(SpanKind.RETRIEVAL, "search"):
            pass

    spans = recorder.finish().spans
    # Inner span completes first, so it is appended first.
    inner, outer_span = spans
    assert inner.name == "search"
    assert inner.parent_span_id == outer_span.span_id
    assert outer_span.parent_span_id is None


def test_exception_marks_the_span_as_error_and_still_propagates() -> None:
    """A trace of a failure is the most useful trace there is — but it must not swallow."""
    recorder = TraceRecorder("test")

    with pytest.raises(ValueError, match="boom"), recorder.span(SpanKind.ENGINE, "evaluate"):
        raise ValueError("boom")

    span = recorder.finish().spans[0]
    assert span.status is SpanStatus.ERROR
    assert span.error == "ValueError: boom"


def test_span_cap_truncates_rather_than_growing_without_bound() -> None:
    """A runaway agent loop must not be able to exhaust memory."""
    recorder = TraceRecorder("test", max_spans=3)

    handles = []
    for index in range(6):
        with recorder.span(SpanKind.GRAPH_NODE, f"node-{index}") as span:
            handles.append(span)

    trace = recorder.finish()
    assert len(trace.spans) == 3
    assert trace.truncated is True
    # Call sites past the cap receive None and must tolerate it.
    assert handles[:3] != [None, None, None]
    assert handles[3:] == [None, None, None]


class TestRedaction:
    """Sensitive text must not be captured unless explicitly enabled."""

    @pytest.mark.parametrize(
        "attribute",
        ["prompt", "system_prompt", "rag_context", "messages", "content", "answer", "user_query"],
    )
    def test_sensitive_attributes_are_redacted_by_default(self, attribute: str) -> None:
        recorder = TraceRecorder("test")

        with recorder.span(SpanKind.LLM, "complete", **{attribute: "secret user content"}):
            pass

        value = recorder.finish().spans[0].attributes[attribute]
        assert "secret user content" not in value
        assert "redacted" in value

    def test_redaction_preserves_length_which_is_the_useful_part(self) -> None:
        recorder = TraceRecorder("test")

        with recorder.span(SpanKind.LLM, "complete", prompt="x" * 42):
            pass

        assert "42 chars" in recorder.finish().spans[0].attributes["prompt"]

    def test_sensitive_attributes_are_kept_when_capture_is_enabled(self) -> None:
        recorder = TraceRecorder("test", capture_sensitive=True)

        with recorder.span(SpanKind.LLM, "complete", prompt="the actual prompt"):
            pass

        assert recorder.finish().spans[0].attributes["prompt"] == "the actual prompt"

    def test_non_sensitive_attributes_are_never_redacted(self) -> None:
        recorder = TraceRecorder("test")

        with recorder.span(SpanKind.ENGINE, "evaluate", depth=12, eval_cp=-280):
            pass

        attributes = recorder.finish().spans[0].attributes
        assert attributes["depth"] == 12
        assert attributes["eval_cp"] == -280

    def test_attributes_set_via_handle_are_also_redacted(self) -> None:
        """Redaction must cover the late path too, not only the constructor path."""
        recorder = TraceRecorder("test")

        with recorder.span(SpanKind.LLM, "complete") as span:
            assert span is not None
            span.set(prompt="leaked later")

        assert "leaked later" not in recorder.finish().spans[0].attributes["prompt"]


def test_long_values_are_truncated() -> None:
    recorder = TraceRecorder("test", capture_sensitive=True)

    with recorder.span(SpanKind.RETRIEVAL, "search", chunk="y" * (MAX_ATTRIBUTE_CHARS + 500)):
        pass

    value = recorder.finish().spans[0].attributes["chunk"]
    assert value.endswith("<truncated>")
    assert len(value) < MAX_ATTRIBUTE_CHARS + 100


class TestNullRecorder:
    """When disabled, instrumented code must pay essentially nothing."""

    def test_span_is_a_usable_no_op(self) -> None:
        with NULL_RECORDER.span(SpanKind.ENGINE, "evaluate", ply=1) as span:
            assert span is None

    def test_set_tokens_is_harmless(self) -> None:
        assert NULL_RECORDER.set_tokens(1, 2) is None

    def test_get_recorder_defaults_to_null_outside_a_request(self) -> None:
        """Scripts, workers, and tests must run without a bound recorder."""
        assert get_recorder() is NULL_RECORDER


def test_bind_and_reset_restore_the_previous_recorder() -> None:
    recorder = TraceRecorder("bound")

    token = bind_recorder(recorder)
    try:
        assert get_recorder() is recorder
    finally:
        reset_recorder(token)

    assert get_recorder() is NULL_RECORDER


def test_recorder_module_has_no_llm_dependency() -> None:
    """Structural guard on the owner's constraint that tracing must not cost LLM calls.

    If the recorder ever imports a provider, it becomes possible for it to make one.
    Keeping the dependency absent makes that impossible rather than merely discouraged.
    """
    import ast
    from pathlib import Path

    source = Path("app/core/devinsight/recorder.py").read_text()
    imported = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert not any("integrations" in module for module in imported)
    assert not any(module.startswith(("openai", "anthropic", "langchain")) for module in imported)
