# GrandMate v2 — Documentation

Everything needed to review this project. Self-contained: no document here depends on a
repository you cannot see.

## Start here

| Document | What it answers |
|---|---|
| [`production_and_experiments.md`](production_and_experiments.md) | **Read first.** What runs live, what was built and deliberately not shipped, and how to read the evaluation numbers |
| [`Deliverables.md`](Deliverables.md) | The complete certification submission: problem, solution, data, prototype, evals, improvements, next steps |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How the system is built: invariants, components, both graphs, request lifecycle, memory, RAG, grounding, observability |
| [`evaluation_report.md`](evaluation_report.md) | Measured results across eight suites — **generated from recorded runs**, never hand-written |
| [`evaluation_data_design.md`](evaluation_data_design.md) | What test data each suite uses, how it is built, and what it cannot prove |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | How the live deployment was built, the seven problems hit on the way, and what was verified against it |
| [`diagrams/`](diagrams/) | Every Mermaid diagram as a standalone file, with reading notes |

## Three things to know before reading

**The application is deployed.** Frontend at https://grandmate.vercel.app, backend at
https://grandmate-v2-backend.fly.dev, Neon Postgres behind it. `DEPLOYMENT.md` §9 records
what was verified against the live stack, and §0 records the seven problems in the way —
three of which were only findable by deploying, and one of which was introduced by the fix
for another.

**One hard-gated evaluation metric is currently failing.** `fact_invariance_rate` is 94.4%
against a zero-tolerance target of 1.0. It is reported as a failure in the generated
evaluation report and in
[`production_and_experiments.md`](production_and_experiments.md) §4, which also explains
why `faithfulness` sits at 0.70 while `grounded_rate` is 100% — the question this
documentation set gets asked most.

**Some things were built and not shipped.** Multi-agent orchestration lost a head-to-head
against the single agent and is not routed; fine-tuning was evaluated and declined; the MCP
server was deferred. Each decision has a recorded run behind it, in
[`production_and_experiments.md`](production_and_experiments.md) §2.

All three are stated here because a documentation set that requires a reader to hunt for
its own gaps is not honest documentation.

## Regenerating the evaluation report

```bash
cd backend
uv run pytest -q evals/            # run the suites — needs OPENAI_API_KEY + ingested corpus
uv run python -m evals.report      # rewrite docs/evaluation_report.md from runs/
```

Every figure in that report is read out of a run record under `backend/evals/runs/`. If a
suite has no recorded run, the report says so rather than omitting the row.

## Conventions

- A diagram lives **inline** in the document that argues from it and **standalone** in
  `diagrams/`. The duplication is deliberate; both copies change together.
- Numbers in `evaluation_report.md` are generated. Numbers quoted in prose elsewhere are
  transcribed from it, and should be re-checked against it after any evaluation run.
- Anything unverified says so at the point of the claim, not in a footnote.

## Elsewhere in the repository

| | |
|---|---|
| [`../README.md`](../README.md) | Setup, commands, and layout |
| [`../backend/README.md`](../backend/README.md) · [`../frontend/README.md`](../frontend/README.md) | Per-side setup and module layout |
| [`../backend/evals/`](../backend/evals/) | Datasets, harnesses, suites, and the raw run records behind every number |

The internal engineering record — 17 ADRs, the product decisions log, and the
delivery reports — lives in a separate private repository. It is the audit trail for how
the project was built, not a prerequisite for understanding what it is; the decisions that
matter to a reader are restated here.
