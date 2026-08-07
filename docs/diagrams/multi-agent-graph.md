# Multi-agent supervisor graph

Referenced from [`ARCHITECTURE.md` §4.2](../ARCHITECTURE.md#42-multi-agent-supervisor-graph--built-evaluated-rejected-on-the-evidence).

Five agents under a supervisor, with a critic that loops back. **Built, tested, evaluated
head-to-head against the single agent — and not adopted.** It lost on both pre-declared
metrics, so it is not wired to any API route: `USE_MULTI_AGENT=false`.

```mermaid
flowchart TD
    S([Turn]) --> SUP{"<b>supervisor</b><br/>plans the route in one shot"}

    SUP -- "needs knowledge" --> RET["<b>retriever</b><br/>bucket-routed hybrid retrieval"]
    SUP -- "needs engine facts" --> CA["<b>chess_analyst</b><br/>deterministic analysis lookups"]
    SUP -- "neither" --> CO["<b>coach</b><br/>drafts the answer in persona voice"]

    RET -- "facts needed too" --> CA
    RET -- "enough context" --> CO
    CA --> CO

    CO --> CR{"<b>critic</b><br/>verifies claims against<br/>deterministic analysis"}
    CR -- "grounded" --> E([END])
    CR -- "ungrounded" --> CO
    CO -- "budget exhausted" --> E

    classDef budget fill:#fff8e1,stroke:#f90;
    class SUP,RET,CA,CO,CR budget
```

## Reading notes

**Every node checks the budget before doing work.** `MULTI_AGENT_MAX_STEPS`,
`MULTI_AGENT_MAX_TOOL_CALLS`, and `MULTI_AGENT_TOKEN_BUDGET` are separate from — and larger
than — the single-agent ceilings, because this budget is spent across up to five agents in
one turn rather than one. A node that finds the budget exhausted records
`skipped="budget_exhausted"` in its span and returns, rather than silently overrunning.

**The critic is a separate agent, not a regex.** It is the multi-agent analogue of the
chat graph's deterministic guardrail — but note that the *deterministic* guardrail is the
one that actually gates delivery. An LLM critic that approves an ungrounded claim must not
be the only thing standing between a model and a reader.

**Why it is not routed.** Whether multi-agent orchestration ships was scoped to be decided
on evidence, with the exit criterion declared before the run. The trajectory
evaluation runs both graphs against the same seeded scenarios and scores them identically:
single-agent faithfulness 0.600 / relevancy 0.406, multi-agent 0.504 / 0.118. It did not
clear the bar. The recorded run is in
[`evaluation_report.md`](../evaluation_report.md); the transcript analysis of *why* — the
`coach` node never touches a tool, so a thin handoff makes a zero-citation hedge its
cheapest grounded answer — is in
[`production_and_experiments.md`](../production_and_experiments.md) §2.1.

The graph stays built and tested. One environment variable flips it back on, which is what
makes this a recorded decision rather than a dead end.
