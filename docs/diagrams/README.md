# Diagrams

Every Mermaid diagram referenced from [`../ARCHITECTURE.md`](../ARCHITECTURE.md) and
[`../Deliverables.md`](../Deliverables.md), as standalone files. Each carries a back-link
to the section it came from, plus reading notes that would clutter the parent document.

GitHub renders these natively — no image build step, and the diagram source stays
reviewable in a pull request.

| Diagram | What it shows | Referenced from |
|---|---|---|
| [`user-workflow-pain-points.md`](user-workflow-pain-points.md) | How a player tries to learn from their games today, and where that loop fails | `Deliverables.md` §1.3 |
| [`system-infrastructure.md`](system-infrastructure.md) | The stack, one box per piece of infrastructure, with a one-sentence justification per choice | `Deliverables.md` §2.2 · `ARCHITECTURE.md` §2 |
| [`component-architecture.md`](component-architecture.md) | Module-level view, and the one dependency edge that is a CI-enforced rule | `ARCHITECTURE.md` §2 |
| [`agent-workflow.md`](agent-workflow.md) | The chat graph that serves production traffic — three nodes, eight tools, guardrail loop | `ARCHITECTURE.md` §4.1 · `Deliverables.md` §2.3 |
| [`multi-agent-graph.md`](multi-agent-graph.md) | The five-agent supervisor graph: built and evaluated, deliberately not routed | `ARCHITECTURE.md` §4.2 |
| [`request-lifecycle.md`](request-lifecycle.md) | What one `POST /imports` triggers across a request, a background job, and a later chat turn | `ARCHITECTURE.md` §5 |
| [`grounding-guardrail.md`](grounding-guardrail.md) | How an unsupported claim is stopped before a reader sees it | `ARCHITECTURE.md` §9 |
| [`memory-layers.md`](memory-layers.md) | Three memory layers, and why they are not one | `ARCHITECTURE.md` §7 · ADR-0005 |
| [`deployment-topology.md`](deployment-topology.md) | The Fly + Vercel target — **planned, not deployed** | `ARCHITECTURE.md` §11 · `DEPLOYMENT.md` |

## Convention

A diagram lives inline in the document that argues from it, **and** here as a standalone
file. The duplication is deliberate: the parent document needs the diagram in context, and
a reader who wants only the picture should not have to scroll a 400-line architecture
reference to find it.

When a diagram changes, both copies change. There is no generator keeping them in sync —
Phase 17 adds a mermaid export from the compiled LangGraph graphs plus a drift test, which
will make `agent-workflow.md` and `multi-agent-graph.md` verifiable against the real
topology rather than hand-maintained.
