# ADR-0013 — Developer Insight via Out-of-Band Tracing

- **Status**: Accepted
- **Date**: 2026-07-26
- **Phase**: 1a
- **Deciders**: Project owner

## Context

The owner asked for a developer insight surface — logs, agent calls, workflow navigation
— modelled on the one built in the sibling project, with two explicit constraints:
**tracking must not introduce latency, and must not cost LLM calls.**

The reference implementation (`grandmate/frontend/src/components/DevInsights.tsx`, backed
by `DeveloperInsight` in `schemas/models.py`) is a good idea with a structural problem. Its
payload — including `raw_prompt`, `rag_context`, `stockfish_raw`, and `agent_steps` — is
embedded inline in every `/analyze` and `/chat` response, and reconstructed by hand at two
separate call sites in `app.py` (lines 305 and 416).

That means prompt text and retrieved user context are serialised and sent to the browser on
every request, in every environment, whether or not anyone is looking at them. The
duplicated construction is also the kind of thing that drifts between endpoints.

## Decision

**Record in process, read out of band.**

1. **Recorder.** A `contextvars`-bound `TraceRecorder` collects spans. Recording a span is
   a `perf_counter()` read and a list append — no I/O, no serialisation, no network.
2. **Transport.** Responses carry only an `X-Trace-Id` header. The full trace is fetched
   on demand from `GET /api/v1/dev/traces/{id}`. Nothing rides the response body.
3. **Null object when disabled.** `get_recorder()` returns a `NullRecorder` whose `span()`
   is a `nullcontext`. Instrumentation is therefore written unconditionally at call sites,
   with no `if enabled` guards scattered through domain code.
4. **Zero LLM cost.** The recorder stores only data the system already produced. Token
   counts come from the provider's own `usage` field in a response already paid for —
   never from a local tokenizer, never from a separate count-tokens call.
5. **Two independent switches.** `DEV_INSIGHT_ENABLED` controls recording of names,
   timings, and counts. `DEV_INSIGHT_CAPTURE_PROMPTS` controls capture of prompt and
   context *text*, and is off by default everywhere.
6. **Production is hard-gated.** `Settings.dev_insight_active` and
   `dev_insight_capture_sensitive` both return `False` in production regardless of the
   environment. The dev routes are not mounted, and the middleware is not installed.
7. **Bounded.** A ring buffer of `DEV_INSIGHT_MAX_TRACES`, a per-trace span cap, and
   attribute truncation at 2000 characters.
8. **Redaction by attribute name.** Attributes whose names contain `prompt`, `context`,
   `message`, `content`, `answer`, or `query` are replaced with a length marker unless
   capture is explicitly enabled.

## Rationale

The out-of-band transport is the whole decision. A closed panel issues no requests, so the
feature is genuinely free for a developer who is not using it — which is what satisfies the
"no latency" constraint honestly rather than by assertion. It also removes the reference
implementation's data-exposure surface entirely: there is no path by which prompt text
reaches a production response body, because production has no trace endpoint at all.

The null-object pattern is what makes unconditional instrumentation acceptable. If call
sites had to guard every span, the guards would be forgotten inconsistently and the
instrumentation would rot. A no-op recorder costs an attribute lookup, which is cheap
enough that the guard is not worth writing.

Redaction preserves the value's *length* rather than dropping the key. When debugging
prompt construction, "a 4,812-character system prompt was sent" is usually the diagnostic
fact you need; the text itself is rarely necessary and is the part that carries risk.

Two switches rather than one because the two categories of data carry very different risk.
Span names, durations, and token counts are safe to record routinely. Prompt text can
contain a user's game history and coaching notes, so it needs its own explicit opt-in and
must not be reachable in production even by misconfiguration.

Traces live in memory rather than Postgres because they are a debugging aid, not a system
of record. Persisting them would put a write on the request path purely for developer
convenience, and losing them on restart is fine.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Inline `developer_insight` on every response, as in the reference app | Prompt text and context on the hot path in every environment; payload cost paid whether or not anyone looks |
| OpenTelemetry with an external collector | Correct for Phase 17 production observability; far too much setup for a local debugging panel, and requires a running collector |
| Log-scraping into a viewer | Loses structure and parent/child relationships; forces string parsing to recover what the recorder has natively |
| Persist traces to Postgres | A database write per request for developer convenience |
| One enable switch | Conflates safe metadata with user content; either over-restricts timings or under-protects prompts |
| Guarded instrumentation (`if enabled:` at call sites) | Guards get forgotten inconsistently; the null object makes them unnecessary |

## Consequences

### Positive
- Closed panel costs nothing; no request-path overhead
- No prompt text can reach production, structurally
- One instrumentation API for HTTP, engine, retrieval, LLM, graph nodes, and agents
- Token accounting is free and lands in the same place as timings
- Later phases add spans as they are written, rather than tracing being retrofitted
- The panel groups by span kind, so new span types appear automatically instead of needing a tab declared in advance

### Negative
- Traces are lost on restart
- A second fetch is needed to view a trace, unlike an inline payload
- Redaction is name-based heuristics; an attribute named unusually could slip through, which is why capture is off by default rather than relying on the heuristic
- In-memory storage does not survive multiple worker processes — a trace is only visible on the process that served the request

### Follow-up required
- Phase 5: engine spans
- Phase 7: retrieval spans with bucket and hit counts
- Phase 10: LLM spans with token usage; prompt capture used locally when debugging
- Phase 13: agent and trajectory spans, feeding the multi-agent evaluation
- Phase 17: production observability with real tracing behind auth; revisit whether the dev endpoints should exist there at all — **resolved by [ADR-0017](0017-langsmith-tracing-and-langgraph-studio.md)**

## Relationship to ADR-0017

[ADR-0017](0017-langsmith-tracing-and-langgraph-studio.md) adds LangSmith as the
production agent-tracing backend. It **complements this decision and does not supersede
it**: dev-insight remains the zero-cost, zero-egress local surface answering "what did
*this* request just do," while LangSmith answers "why does this class of turn fail," with
durable retention this ADR's 50-trace in-memory ring buffer deliberately does not
provide.

The redaction discipline decided here is load-bearing there. ADR-0017 requires reusing
this module's existing sanitiser rather than writing a second one, and requires prompt
and retrieved-context text to ship only behind an explicit, default-off switch —
the same posture `DEV_INSIGHT_CAPTURE_PROMPTS` already takes, now applied to a strictly
larger disclosure, since that data leaves our infrastructure entirely.

## References
- `backend/app/core/devinsight/`
- `frontend/src/features/devinsight/`
- Reference implementation: `grandmate/frontend/src/components/DevInsights.tsx`
- [ADR-0017](0017-langsmith-tracing-and-langgraph-studio.md) — production agent tracing
