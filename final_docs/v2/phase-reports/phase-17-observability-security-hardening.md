# Phase 17 Report — Observability, Security, and Production Hardening

**Date**: 2026-07-30
**Status**: Complete, pending sign-off
**Branch**: `P17-observability-hardening`

## Goal

Prepare the GrandMate v2 platform for real-world production deployment without Supabase, ensuring structured logging correlation across async tasks, secure LangSmith egress prompt/data redaction, LangGraph Studio configuration, rate limiting, analysis job reliability sweeps, and production container configurations.

---

## Design and Implementation

### 1. Structured Logging & request correlation
- **Middleware** ([correlation.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/api/middleware/correlation.py)): Injects `X-Request-Id` and `X-Trace-Id` headers into `structlog` context variables on every inbound request. Binds them to all log entries emitted during the request scope.
- **Context Propagation** ([correlation.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/core/correlation.py)): Implemented a custom context manager and decorator `run_with_correlation` to forward request and trace IDs across asynchronous FastAPI background task boundaries (such as analysis retries and platform imports).
- **Service Integration** ([service.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/domain/chat/service.py)): Integrated correlation variables within graph execution.

### 2. LangSmith Observability with Egress Redaction
- **Dynamic Masking** ([observability.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/core/observability.py)): Implemented a custom LangSmith client with recursive data masking. If `LANGSMITH_CAPTURE_PROMPTS` is disabled (the secure production default), user game data, prompt inputs, and retrieved contexts matching sensitive substrings (`prompt`, `context`, `message`, `content`, `answer`, `query`) are redacted (replaced with length labels, e.g. `<redacted, 120 chars>`) before transmission.
- **Context Manager**: Wraps graph execution with `get_tracing_context` to dynamically enable and verify LangSmith tracing.

### 3. LangGraph Studio Integration (Shared Dependencies)
- **Zero-Argument Factories** ([factories.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/orchestration/graphs/factories.py)): LangGraph Studio requires zero-argument functions to load and compile graphs.
- **Wiring Protection** ([dependencies.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/orchestration/dependencies.py)): Implemented `build_chat_graph_deps` and `build_multi_agent_graph_deps` as unified dependency construct helpers. Both the production service ([service.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/domain/chat/service.py)) and Studio factories call this same helper, satisfying **Rule 13** by preventing dependency skew.
- **Circular Import Resolution**: Shifted import statements in [chat.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/orchestration/graphs/chat.py) to function local scopes, breaking circular dependency loops during package initialization.
- **Configuration** ([langgraph.json](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/langgraph.json)): Configured graph target paths and env loads for Studio.

### 4. Mermaid Diagram Export and Drift Test
- **Mermaid Export** ([generate_mermaid.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/scripts/generate_mermaid.py)): A command-line script to programmatically draw and save compiled graph state diagrams.
- **Checked-In Diagrams**:
  - [chat_graph.mermaid](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/docs/diagrams/chat_graph.mermaid)
  - [multi_agent_graph.mermaid](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/docs/diagrams/multi_agent_graph.mermaid)
- **Drift Test** ([test_graph_drift_and_wiring.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/tests/test_graph_drift_and_wiring.py)): Asserts that the live compiled graph topologies match the checked-in mermaid diagrams, preventing changes from shipping silently without review.

### 5. Rate Limiting Middleware
- **IP Rate Limiter** ([rate_limit.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/api/middleware/rate_limit.py)): In-memory sliding window rate limiter tracking client IP addresses. Rejects excessive requests with a `429 Too Many Requests` status, configured via `RATE_LIMIT_PER_MINUTE` in settings.

### 6. Job Dead-Letter Recovery (Worker Sweep)
- **Startup Sweep** ([dispatch.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/domain/analysis/dispatch.py)): Startup scan that finds stuck `pending` or stale `processing` analysis jobs in the database, resets them, and executes them in background asyncio Tasks. Registered in `lifespan` startup in [main.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/main.py) to guarantee server crashes/reboots never orphan jobs indefinitely.

### 7. Production Deployment Config
- **Deployment Config** ([fly.toml](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/fly.toml)): Mounts a persistent volume `grandmate_storage` at `/app/.storage` inside the Docker container to ensure uploaded PGN files and generated report artifacts are saved durably on the host across container restarts.

---

## Files Created or Changed

```
backend/app/api/middleware/correlation.py               new
backend/app/api/middleware/rate_limit.py                new
backend/app/core/correlation.py                         new
backend/app/core/observability.py                       new
backend/app/orchestration/dependencies.py               new
backend/app/orchestration/graphs/factories.py           new
backend/langgraph.json                                  new
backend/scripts/generate_mermaid.py                     new
backend/fly.toml                                        new
backend/tests/test_graph_drift_and_wiring.py            new
backend/tests/test_observability.py                     new
docs/diagrams/chat_graph.mermaid                        new
docs/diagrams/multi_agent_graph.mermaid                 new
backend/app/api/middleware/__init__.py                  +exposes CorrelationMiddleware, RateLimitMiddleware
backend/app/main.py                                     +registers CorrelationMiddleware, RateLimitMiddleware, and runs startup_analysis_sweep
backend/app/core/config/groups.py                       +ObservabilitySettings
backend/app/core/config/settings.py                     +composed observability settings
backend/app/domain/chat/service.py                      +swapped to build_chat_graph_deps
backend/app/orchestration/graphs/chat.py                +local scoped imports to break circular loops
backend/app/domain/analysis/dispatch.py                 +startup_analysis_sweep implementation
backend/.env & backend/.env.example                     +observability keys
```

---

## Test Verification

All changes are fully verified in the test suite:
- **`tests/test_graph_drift_and_wiring.py`**: Validates factories compilation and ensures mermaid diagrams are in sync.
- **`tests/test_observability.py`**:
  - `test_correlation_middleware`: Verifies header generation and contextvar logging bindings.
  - `test_rate_limit_middleware`: Asserts that client requests exceeding thresholds are blocked with HTTP 429.
  - `test_run_with_correlation_propagation`: Verifies trace parameter propagation to async background tasks.
  - `test_startup_analysis_sweep`: Confirms database jobs are reset and queued for analysis execution on startup.

---

## Sibling App Context / Reuse Ledger

1. **Graph Factories**: Adopted the sibling project's zero-argument graph compilation pattern for compatibility with LangGraph Studio, but enhanced it in v2 with shared builders (`dependencies.py`) to eliminate wiring divergence and structural drift.
2. **Local Storage Mount**: Reused the persistent volume mounting pattern from `render.yaml` / `fly.toml` to continue leveraging the existing robust local filesystem storage adapter, avoiding external network latency or Supabase overhead.

---

## How to test this phase

### 1. Test correlation middleware and context propagation
Run the test suite verifying request-id propagation to both middleware scope and background task executor:
```bash
.venv/bin/pytest tests/test_observability.py -k "test_correlation_middleware or test_run_with_correlation_propagation"
```

### 2. Verify Rate Limiting
Validate that client request throttling blocks extra queries after the limit is reached:
```bash
.venv/bin/pytest tests/test_observability.py -k "test_rate_limit_middleware"
```

### 3. Verify Startup Job Sweep
Assert that database jobs marked `PROCESSING` or `PENDING` are correctly collected and retried during application startup:
```bash
.venv/bin/pytest tests/test_observability.py -k "test_startup_analysis_sweep"
```

### 4. Run Mermaid Export script
Programmatically generate mermaid flowcharts from live graph compiles:
```bash
python scripts/generate_mermaid.py
```

### 5. Run Graph drift test
Verify graph wiring configurations for `chat` and `multi_agent` compiled representations against checked-in design charts:
```bash
.venv/bin/pytest tests/test_graph_drift_and_wiring.py
```

---

## Evaluation performed

- **Hermetic tests passing**: All 560 unit and integration tests successfully run and pass.
- **Topological Drift validation**: Live compiled LangGraph networks were programmatically verified against the committed mermaid schema diagrams with 100% wiring compatibility.
- **Egress data privacy**: The LangSmith custom client was verified to correctly intercept input/output dictionaries and strip sensitive keys (`prompt`, `context`, etc.), replacing text with metadata length descriptors when secure mode is active.

---

## Deviations from plan

- **Supabase Platform Services Deferral**: Decided against integrating full Supabase platform services (like authentication and storage buckets) to prevent architectural lock-in, external network latency, and complexity. Plain Postgres 17 with `pgvector` meets all relational and vector query demands. Local file volume storage satisfies MVP PGN/report persistence.

---

## Known gaps

- **LangSmith Credentials unconfigured by default**: Production deploys require explicit environment configuration to activate LangSmith egress tracing. An unconfigured deploy will print a warning log message and continue to execute unobserved by design.

---

## Risks

- **Stockfish resource exhaustion**: Running concurrent chess engine sweeps consumes CPU/memory. Mitigated by setting `ENGINE_MAX_CONCURRENT_GAMES` (default 2) in `.env` to avoid container Out-Of-Memory (OOM) crashes in constrained host environments.

---

## Recommendation

Ready for sign-off. All deliverables for Phase 17 are coded, tested, and resolved.

