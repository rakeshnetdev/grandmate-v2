# Definition of Done

Applies to every phase from 1 to 18. A phase is not done because the code runs. It is done
when all of the following hold.

## Universal checklist

### Implementation
- [ ] Approved scope complete; nothing silently narrowed or widened
- [ ] Structure matches `project-plan.md`: domain logic in domain modules, thin routes, repositories encapsulating persistence, integrations behind adapters
- [ ] No file has grown oversized or taken on unrelated responsibilities (reviewed explicitly, refactored before sign-off if so)
- [ ] Comments present on orchestration flows, engine policies, detector heuristics, memory write rules, permission-sensitive code, and complex hooks
- [ ] No hardcoded secrets; no hardcoded tunables
- [ ] `.env.example` updated with any new keys

### Tests
- [ ] Unit tests for core logic, schemas, detectors, aggregators, transformations
- [ ] Integration tests for API + DB, API + worker, adapters with mocks, LangGraph flows where relevant
- [ ] E2E coverage added or extended when the phase introduces a user-visible workflow
- [ ] All tests pass; results pasted into the phase report, not summarised as "passing"
- [ ] CI green

### Evaluation
- [ ] Evaluation criteria defined for the phase
- [ ] Deterministic evaluation set exists, however small
- [ ] Outputs verified against underlying analysis truth
- [ ] From Phase 7: RAGAS run, scores recorded to `evals/runs/` and `eval_runs`
- [ ] Deltas from the previous run reported; regressions flagged
- [ ] Hard thresholds met, or the phase is reported as failed rather than closed

### Documentation
- [ ] README updated
- [ ] Architecture notes updated
- [ ] ADR written for any significant decision
- [ ] Setup and test instructions current
- [ ] Any deviation from `project-plan.md` documented with its reason
- [ ] Any reuse from `grandmate/` recorded in `changes/`

### Branch and PR
- [ ] Work was done on a `P{N}-{slug}` branch, not on `main`
- [ ] Phase report written to `final_docs/v2/phase-reports/`
- [ ] Owner asked **"Phase N: {name} completed. Shall we check in?"** and answered
- [ ] Commit made only after that approval, with no failing tests and no secrets
- [ ] PR opened with `gh pr create`, titled `P{N} — {Phase name}`, linking the report
- [ ] PR settled before the next phase begins

### Sign-off
- [ ] Phase report produced: completed tasks, files changed, tests and results, evaluation performed, known gaps, readiness recommendation
- [ ] Result explained clearly to the owner
- [ ] Owner explicitly approves before the next phase begins

## Phase report template

```markdown
# Phase N Report — <name>

## Completed
## Files created or changed
## Tests added
## Test results          <- actual output, including failures
## Evaluation performed  <- scores, thresholds, deltas
## Deviations from plan  <- with reasons
## Reuse from grandmate/ <- with ledger references
## Known gaps
## Risks
## Recommendation        <- ready for sign-off, or not, and why
```

## Rules that override convenience

**Failing tests are reported, not hidden.** If a phase ends with a failing test, the report
says so with the output. Reporting a phase complete with known failures is a worse outcome
than reporting it incomplete.

**Threshold failures stop the phase.** If Faithfulness or Answer Accuracy falls below the
gate, the phase is presented as failed. Not "complete with a caveat".

**A locked decision that turns out to be wrong gets raised, not worked around.** Silently
routing around a decision in `decisions-log.md` is not acceptable; say it is wrong and ask.

**No phase begins without sign-off on the previous one.**
