# ADR-0017 — LangSmith for Production Agent Tracing, LangGraph Studio for Graph Development

- **Status**: Accepted
- **Date**: 2026-07-29
- **Phase**: 17 (with the related evaluation gap assigned to Phase 16)
- **Deciders**: Project owner

## Context

Phases 10, 11, and 13 built real LangGraph orchestration: a three-node chat graph
(`classify_intent → run_agent → write_memory`) and a five-node supervisor graph
(`supervisor`, `retriever`, `chess_analyst`, `coach`, `critic`) with four conditional
edges and a `critic → coach` retry loop. Both are instrumented with ADR-0013's
dev-insight spans — `GRAPH_NODE`, `AGENT`, `GROUNDING`, `LLM`.

Three real gaps follow from that, and they only become visible when you try to deploy or
to diagnose an evaluation failure.

**1. There is no agent observability in production, by design.** ADR-0013 hard-gates the
dev-insight surface off whenever `APP_ENV=production` — routes not mounted, middleware
not installed, `dev_insight_capture_sensitive` forced `False` regardless of
configuration. That was the correct call for an unauthenticated surface that can carry a
user's game history. It also means that on any hosted deployment, the agent runs
completely unobserved. Dev-insight is additionally an in-memory ring buffer
(`DEV_INSIGHT_MAX_TRACES=50`) with no persistence, no cross-process view, and no
sampling — it was never built to be the production answer.

**2. There is no way to see the graph.** No `langgraph.json` exists, so LangGraph Studio
has never been run against either graph. Nothing calls `get_graph().draw_mermaid()`
either, so the state diagram exists only as `add_node`/`add_edge` calls in source. The
sibling project (`grandmate/langgraph.json`) has had Studio wired since early on; this
project does not.

**3. Evaluation failures cannot currently be diagnosed from evidence.** Phase 10 recorded
Faithfulness at 0.70 against a 0.85 target and explained the gap by *reasoning* about
what RAGAS measures — correctly, on inspection, but by argument rather than by trace.
Phase 16 consolidates evaluation into a gating system, which makes "why did this scenario
score badly" a question that must be answerable from recorded evidence rather than from
re-reading ten answers by hand.

Separately, comparison against the sibling project surfaced an evaluation gap that is
**not** an observability problem and is recorded here only so the two are not conflated:
`grandmate` measures its move classifier against an *independent* Stockfish run at a
deeper setting than production uses (detection F1 0.9294, severity accuracy 0.9073).
GrandMate v2 evaluates retrieval, persona fidelity, chat grounding, memory retention,
agent trajectory, and training fidelity — but has never validated the move classifier
that every one of those layers depends on.

## Decision

**Three decisions, one context.**

1. **LangSmith is the production agent-tracing backend.** Not LangTrace, not a
   self-hosted OpenTelemetry stack.
2. **LangGraph Studio is wired via `backend/langgraph.json`**, as a development tool
   only, never mounted or reachable in production.
3. **Both land in Phase 17**, not in a new sub-phase. The classifier-accuracy evaluation
   gap described above is assigned to **Phase 16**, where evaluation consolidation
   already lives.

**ADR-0013's dev-insight surface is not replaced and not deprecated.** The two answer
different questions and the distinction is deliberate:

| | Dev-insight (ADR-0013) | LangSmith (this ADR) |
|---|---|---|
| Environment | Development only | Production, and development when enabled |
| Cost | Zero — a `perf_counter()` read and a list append | Per-trace, external |
| Data egress | None — never leaves the process | Prompt and context text leaves our infrastructure |
| Retention | 50 traces, in memory, lost on restart | Durable, searchable, trended |
| Question it answers | "What did *this* request just do?" | "Why does this class of turn fail?" |

## Rationale

**LangSmith over LangTrace, on three grounds.**

*It is already installed.* `langsmith 0.10.10` is present in `uv.lock` today as a
transitive dependency of `langchain-core`. Adopting it adds configuration, not supply
chain. LangTrace would add a new direct dependency plus an OpenTelemetry collector to
run, configure, and host.

*The integration is native and node-aware.* LangSmith understands LangGraph's execution
model directly — per-node spans, state snapshots at each step, and the same account that
serves Studio. An OTel-based tracer sees generic spans and would need our own
instrumentation to recover the graph semantics we would be paying for.

*The vendor-neutrality argument is weaker here than it first appears.* The instinct to
prefer OpenTelemetry comes from ADR-0006's provider-abstraction posture — and that
posture is correct for the *LLM provider*, which sits behind a `Protocol` precisely so it
can be swapped. But LangGraph is not behind such an abstraction and never was: it is a
structural, accepted dependency at the core of `orchestration/`. Refusing vendor coupling
to LangChain's observability while the orchestration layer *is* LangChain buys
portability we have no plan to exercise. If a second orchestration framework ever
appears, this decision gets revisited — that is what supersession is for.

**Phase 17 over a new sub-phase.** Phase 17 is already "Observability, Security, and
Production Hardening," and already carries "tracing across API, worker, and agent
boundaries" as a deliverable. Agent tracing *is* that deliverable, made specific. Adding
a `P15a` would have split one concern across two phases and left Phase 17's tracing line
item ambiguous about whether it had been satisfied.

**Studio in the same phase, despite being a development tool.** It shares the
`langgraph.json` and graph-factory work that production tracing needs — the same
refactor makes both possible, and doing it once is the point.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| **LangTrace** (OpenTelemetry-based, self-hostable) | Genuinely better on data sovereignty and portability, and it was the initial recommendation. Rejected because it costs a collector to operate and custom instrumentation to recover graph semantics, in exchange for portability away from a framework we are not planning to leave. Revisit if orchestration ever moves off LangChain, or if the privacy consequence below proves unacceptable. |
| **Extend dev-insight to production** | It is an in-memory ring buffer with unauthenticated routes, no persistence, no cross-process view, and no sampling. Making it production-grade means rebuilding LangSmith badly. ADR-0013 chose to build precisely because the alternative was *inline payloads in every response* — a different problem with a different answer. |
| **A new `P15a` sub-phase** | Duplicates Phase 17's existing tracing deliverable and fragments one concern. |
| **No production tracing** | Deploying a multi-agent system with a grounding guardrail and a token budget, and no way to see either behave, is not defensible. |
| **Fold the classifier-accuracy eval into the tracing work** | Unrelated. It is an evaluation-coverage gap, not an observability gap; Phase 16 owns evaluation. Keeping them apart is what stops "we added tracing" from being mistaken for "we validated the classifier." |

## Consequences

### Positive

- The agent is observable in production for the first time — node timings, tool
  selection, budget exhaustion, guardrail retries, and fallback activations.
- Phase 16 can diagnose evaluation failures from recorded traces rather than by
  re-reading answers, which is what makes a gating threshold defensible.
- Studio gives an interactive state diagram for both graphs, and the same work yields a
  committed mermaid diagram — closing the "no architecture diagrams anywhere in
  `final_docs/`" gap found in the sibling-project comparison.
- Graph topology becomes reviewable, so a routing change shows up in review rather than
  only in behaviour.

### Negative

- **User game history and prompt text leave our infrastructure.** This is the real cost
  and it must not be understated. ADR-0013 declined to send this data even to the user's
  *own browser* by default; sending it to a third party is a strictly larger disclosure
  and needs the same redaction discipline plus an explicit privacy statement.
- Vendor coupling to LangChain's hosted service, on top of the framework coupling.
- An ongoing per-usage cost, which needs the same ceiling treatment
  `LLM_DAILY_TOKEN_CEILING` already gets.
- Studio requires zero-argument graph factories, which risks a second wiring path
  diverging from `ChatService` — directly against rule 13.

### Follow-up required

1. **Redaction before egress.** Reuse dev-insight's existing sanitiser rather than
   writing a second one. Nothing containing raw prompt or retrieved-context text ships to
   LangSmith unless a separate, explicit switch is on — mirroring
   `DEV_INSIGHT_CAPTURE_PROMPTS`, which is off by default everywhere.
2. **Configuration, not literals.** `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`,
   `LANGSMITH_TRACING`, and a sampling rate all live in `.env` and a typed settings group
   (rule 11). Tracing defaults **off**, so an unconfigured deploy sends nothing.
3. **One wiring path.** Studio's graph factory and `ChatService` must share a single
   `build_graph_deps(settings)` helper. A test should assert both resolve the same
   dependency set.
4. **Privacy disclosure** in `configuration.md` and the deployment documentation, stating
   plainly what is transmitted and how to turn it off.
5. **Spend guard** consistent with the existing daily token ceiling.

## References

- [ADR-0013](0013-developer-insight-tracing.md) — developer insight via out-of-band
  tracing; complemented, not superseded, by this decision
- [ADR-0006](0006-llm-provider-abstraction.md) — the provider-abstraction posture, and
  why it does not extend to the orchestration framework
- [ADR-0008](0008-agentic-rag-architecture.md) — the agent architecture being observed
- `final_docs/v2/decisions-log.md` — D-033
- `project-plan.md` — Phase 16 and Phase 17 deliverables
- Sibling project: `grandmate/langgraph.json`, `grandmate/evals/fetch_langsmith_feedback.py`
