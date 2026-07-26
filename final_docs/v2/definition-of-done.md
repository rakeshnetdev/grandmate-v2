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

### Manual verification
- [ ] The phase report includes a **"How to test this phase"** section the owner can run
  themselves — concrete commands or click-through steps, not "tested manually"
- [ ] At least one example per surface the phase changed: a `curl` call for a new/changed
  API route, a UI click-through for a new page or flow, a CLI invocation for a new script
- [ ] Examples use real values (a real sample PGN, a real username) so they can be pasted
  and run as-is, not filled in with placeholders first
- [ ] For UI changes: confirmed in an actual browser, not just component tests — see
  `claude.md`'s rule on this

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
## Test results              <- actual output, including failures
## How to test this phase    <- runnable commands / click-through steps, with examples (see below)
## Evaluation performed      <- scores, thresholds, deltas
## Deviations from plan      <- with reasons
## Reuse from grandmate/     <- with ledger references
## Known gaps
## Risks
## Recommendation            <- ready for sign-off, or not, and why
```

### "How to test this phase" — worked examples

This section is for the owner, not for CI — something to paste into a terminal or click
through in a browser to see the phase's own claims for themselves, independent of the
automated suite. One example per surface the phase touched.

**New or changed API route** — a real `curl` call with real example data, plus the
expected shape of the response:

```bash
curl -X POST localhost:7575/api/v1/imports \
  -b cookies.txt \
  -F 'pgn_text=[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0'
# -> 201, {"status": "done", "progress": {"imported": 1, "duplicates": 0, "rejected": []}, ...}
```

**New or changed UI flow** — numbered click-through steps against the running dev
servers, ending in what the owner should see:

```
1. docker compose up -d postgres
2. uv run python -m app          (backend/)
3. npm run dev                   (frontend/)
4. Open http://localhost:3535/login, log in with a real Lichess username
5. Go to /imports, paste a short PGN, click "Import games"
6. Expect: status turns "Done", with "1 imported · 0 duplicates · 0 rejected"
```

**New script or CLI entry point** — the exact invocation and expected exit code / output:

```bash
uv run alembic upgrade head
# -> exits 0, logs "Running upgrade ... -> ..., <migration name>"
```

Use real values throughout (a real sample PGN, a real username, a real migration name) —
a reader should be able to copy the block and run it, not fill in placeholders first.

## Rules that override convenience

**Failing tests are reported, not hidden.** If a phase ends with a failing test, the report
says so with the output. Reporting a phase complete with known failures is a worse outcome
than reporting it incomplete.

**Threshold failures stop the phase.** If Faithfulness or Answer Accuracy falls below the
gate, the phase is presented as failed. Not "complete with a caveat".

**A locked decision that turns out to be wrong gets raised, not worked around.** Silently
routing around a decision in `decisions-log.md` is not acceptable; say it is wrong and ask.

**No phase begins without sign-off on the previous one.**
