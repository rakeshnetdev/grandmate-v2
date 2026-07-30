# GrandMate v2 — Documentation

Submission and architecture documentation. For the engineering record — ADRs, the decisions
log, per-phase reports — see [`../final_docs/v2/`](../final_docs/v2/).

## Start here

| Document | What it answers |
|---|---|
| [`Deliverables.md`](Deliverables.md) | The complete certification submission: problem, solution, data, prototype, evals, improvements, next steps |
| [`grading-rubric.md`](grading-rubric.md) | Per-criterion self-assessment with evidence links — including the two criteria scored below full marks |
| [`demo-script.md`](demo-script.md) | Shot-by-shot script for the 3-minute demo video, with staging checklist and real figures |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How the system is built: invariants, components, both graphs, request lifecycle, memory, RAG, grounding, observability |
| [`evaluation_report.md`](evaluation_report.md) | Measured results across eight suites — **generated from recorded runs**, never hand-written |
| [`evaluation_data_design.md`](evaluation_data_design.md) | What test data each suite uses, how it is built, and what it cannot prove |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | The Fly + Vercel target and the four blockers in the way — **planned, not yet verified** |
| [`diagrams/`](diagrams/) | Every Mermaid diagram as a standalone file, with reading notes |

## Two things to know before reading

**The application is not deployed.** It is built, tested, and verified running locally end
to end. Hosting was deferred to Phase 17 by a Phase 0 decision. `DEPLOYMENT.md` documents
the target and the blockers rather than implying a deployment exists.

**One hard-gated evaluation metric is currently failing.** `fact_invariance_rate` is 94.4%
against a zero-tolerance target of 1.0. It is reported as a failure in the generated
evaluation report, in the deliverables, and in the rubric self-assessment.

Both are stated here because a documentation set that requires a reader to hunt for its own
gaps is not honest documentation.

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

## Related

| | |
|---|---|
| [`../final_docs/v2/README.md`](../final_docs/v2/README.md) | The engineering documentation index |
| [`../final_docs/v2/adr/`](../final_docs/v2/adr/) | 17 architecture decision records |
| [`../final_docs/v2/decisions-log.md`](../final_docs/v2/decisions-log.md) | Every product decision, locked or open |
| [`../final_docs/v2/features-and-use-cases.md`](../final_docs/v2/features-and-use-cases.md) | What works today, with runnable steps |
| [`../final_docs/v2/phase-reports/`](../final_docs/v2/phase-reports/) | Phase-by-phase delivery record |
| [`../project-plan.md`](../project-plan.md) | The 19-phase build plan |
