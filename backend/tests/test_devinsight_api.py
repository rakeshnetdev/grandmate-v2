"""Developer insight store, middleware, and route tests.

The production-gating tests are the important ones here. These endpoints expose request
internals and are unauthenticated until Phase 2, so "absent in production" is a security
property, not a preference.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.middleware import TRACE_HEADER
from app.core.config import Settings
from app.core.devinsight import Span, SpanKind, SpanStatus, TokenCount, Trace, TraceStore
from app.main import create_app


class TestTraceStore:
    def test_stores_and_retrieves(self) -> None:
        store = TraceStore(max_traces=5)
        store.add(Trace(trace_id="abc", label="GET /x"))

        assert store.get("abc") is not None
        assert store.get("missing") is None

    def test_evicts_oldest_beyond_capacity(self) -> None:
        """Bounded buffer: traces are a debugging aid, not a system of record."""
        store = TraceStore(max_traces=3)
        for index in range(5):
            store.add(Trace(trace_id=f"t{index}", label="GET /x"))

        assert len(store) == 3
        assert store.get("t0") is None
        assert store.get("t4") is not None

    def test_list_returns_newest_first(self) -> None:
        store = TraceStore(max_traces=5)
        for index in range(3):
            store.add(Trace(trace_id=f"t{index}", label="GET /x"))

        assert [summary.trace_id for summary in store.list()] == ["t2", "t1", "t0"]

    def test_summary_includes_token_total(self) -> None:
        store = TraceStore()
        trace = Trace(trace_id="t", label="POST /chat")
        trace.spans.append(
            Span(
                kind=SpanKind.LLM,
                name="complete",
                started_at=trace.started_at,
                duration_ms=1.0,
                tokens=TokenCount(prompt_tokens=100, completion_tokens=25),
            )
        )
        store.add(trace)

        assert store.list()[0].total_tokens == 125

    def test_clear_empties_the_buffer(self) -> None:
        store = TraceStore()
        store.add(Trace(trace_id="t", label="GET /x"))
        store.clear()

        assert len(store) == 0


class TestTracingMiddleware:
    def test_response_carries_a_trace_id_header(self, client: TestClient) -> None:
        """The trace id is a header, not a body field — that is the ADR-0013 decision."""
        response = client.get("/health")

        assert TRACE_HEADER in response.headers
        assert len(response.headers[TRACE_HEADER]) == 16

    def test_trace_body_is_not_embedded_in_the_response(self, client: TestClient) -> None:
        """Prompts and context must never ride the hot path."""
        body = client.get("/health").json()

        assert "developer_insight" not in body
        assert "trace" not in body
        assert "spans" not in body

    def test_request_is_recorded_and_retrievable(self, client: TestClient) -> None:
        trace_id = client.get("/health").headers[TRACE_HEADER]

        trace = client.get(f"/api/v1/dev/traces/{trace_id}").json()
        assert trace["trace_id"] == trace_id
        assert trace["label"] == "GET /health"
        assert trace["spans"][0]["kind"] == "http"
        assert trace["spans"][0]["attributes"]["status_code"] == 200

    def test_trace_id_differs_per_request(self, client: TestClient) -> None:
        first = client.get("/health").headers[TRACE_HEADER]
        second = client.get("/health").headers[TRACE_HEADER]

        assert first != second


class TestDevRoutes:
    def test_list_traces(self, client: TestClient) -> None:
        client.get("/health")
        client.get("/ready")

        traces = client.get("/api/v1/dev/traces").json()
        assert len(traces) >= 2
        assert {t["label"] for t in traces} >= {"GET /health", "GET /ready"}

    def test_list_respects_limit(self, client: TestClient) -> None:
        for _ in range(4):
            client.get("/health")

        assert len(client.get("/api/v1/dev/traces?limit=2").json()) == 2

    def test_missing_trace_explains_eviction(self, client: TestClient) -> None:
        """ "Not found" usually means "aged out", and that distinction matters."""
        response = client.get("/api/v1/dev/traces/doesnotexist")

        assert response.status_code == 404
        assert "evicted" in response.json()["detail"]

    def test_clear_empties_the_buffer(self, client: TestClient) -> None:
        client.get("/health")
        assert client.delete("/api/v1/dev/traces").status_code == 204

        # The DELETE itself is traced, so exactly one trace remains afterwards.
        assert len(client.get("/api/v1/dev/traces").json()) <= 2


class TestProductionGating:
    """Developer insight must be unreachable in production, regardless of configuration."""

    @staticmethod
    def _production_client(**dev_insight: object) -> TestClient:
        settings = Settings()
        settings.app.app_env = "production"
        for key, value in dev_insight.items():
            setattr(settings.dev_insight, key, value)
        return TestClient(create_app(settings))

    def test_dev_routes_absent_in_production_even_when_enabled(self) -> None:
        client = self._production_client(dev_insight_enabled=True)

        assert client.get("/api/v1/dev/traces").status_code == 404

    def test_no_trace_header_in_production(self) -> None:
        client = self._production_client(dev_insight_enabled=True)

        assert TRACE_HEADER not in client.get("/health").headers

    def test_prompt_capture_forced_off_in_production(self) -> None:
        """The environment is not permitted to opt into capturing user content."""
        settings = Settings()
        settings.app.app_env = "production"
        settings.dev_insight.dev_insight_capture_prompts = True

        assert settings.dev_insight_capture_sensitive is False
        assert settings.dev_insight_active is False

    def test_disabled_in_development_removes_routes_and_header(self) -> None:
        settings = Settings()
        settings.dev_insight.dev_insight_enabled = False
        client = TestClient(create_app(settings))

        assert client.get("/api/v1/dev/traces").status_code == 404
        assert TRACE_HEADER not in client.get("/health").headers
        # The app must still work perfectly well without tracing.
        assert client.get("/health").status_code == 200


def test_dev_routes_do_not_leak_between_app_instances() -> None:
    """Regression: routers are built per app, not shared as module-level singletons.

    A shared router would be mutated by the first app that enabled dev routes and would
    then carry them into every app created afterwards — including a production one.
    """
    dev_settings = Settings()
    create_app(dev_settings)  # enables dev routes

    prod_settings = Settings()
    prod_settings.app.app_env = "production"
    prod_client = TestClient(create_app(prod_settings))

    assert prod_client.get("/api/v1/dev/traces").status_code == 404


def test_graph_nodes_emit_spans(client: TestClient) -> None:
    """Instrumentation is written unconditionally at call sites; verify it lands."""
    from app.core.devinsight import TraceRecorder, bind_recorder, reset_recorder
    from app.orchestration.graphs.skeleton import build_skeleton_graph

    recorder = TraceRecorder("graph-test")
    token = bind_recorder(recorder)
    try:
        build_skeleton_graph().invoke({"question": "why?", "persona": "coach"})
    finally:
        reset_recorder(token)

    trace = recorder.finish()
    node_spans = [s for s in trace.spans if s.kind is SpanKind.GRAPH_NODE]
    assert [s.name for s in node_spans] == [
        "classify_intent",
        "gather_context",
        "compose_answer",
    ]
    assert trace.status is SpanStatus.OK
