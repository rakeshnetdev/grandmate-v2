# Phase 11 Report — Long-Term Memory and Profile-Aware Chat

**Date**: 2026-07-28
**Status**: Complete, pending sign-off
**Branch**: `P11-long-term-memory`

## Goal

Remember durable preferences and recurring profile facts across sessions — the
long-term layer ADR-0005's three-layer memory model always specified, with the exact
retention/conflict-resolution detail D-013 deliberately deferred until there was real
chat behaviour to reason about. Phase 10 gave this phase that chat.

## Scope decisions confirmed before implementation

Three defaults confirmed with the owner before coding, all approved as proposed (full
reasoning in D-026):

1. **Write trigger**: silent, confidence-gated — not a confirmation prompt. The
   confidence floor (`MEMORY_WRITE_CONFIDENCE_FLOOR`, default 0.7) is the whole
   enforcement mechanism for "only durable facts persist."
2. **Retention window**: no automatic expiry. An entry persists until superseded by a
   new one or manually deleted — staleness is handled by write policy, not a timer.
3. **`coach_note` scope**: deferred entirely, not even the data model. There is no
   coach-viewing feature for it to attach to yet (ADR-0012 still defers cross-account
   viewing).

## Design

- **Two stores, one write path.** `long_term_memory` (Alembic-owned, audited, what the
  UI lists and deletes from) and a LangGraph `AsyncPostgresStore` (what the chat agent's
  `recall_memory` tool actually reads during a conversation) — ADR-0005's "deliberate
  extra cost" of a dual write, paid once in `MemoryService.write_candidate_memories`
  rather than left for every caller to reason about keeping the two in sync. The
  store's own tables are, like Phase 10's checkpointer tables, deliberately **not** an
  Alembic migration — library-owned DDL, versioned by the package's own `.setup()`. A
  new `alembic/env.py` `include_object` filter (prefix-matching `checkpoint`/`store`)
  means this reasoning is now applied once, not re-litigated by hand in every future
  migration that happens to autogenerate alongside those tables — a real gap the first
  Phase 11 migration attempt surfaced (autogenerate proposed dropping Phase 10's
  checkpointer tables outright).
- **A third graph node, `write_memory`**, after `run_agent`, before `END`. Reads the
  turn's `(question, answer)` pair, makes one small LLM extraction call
  (`domain/memory/prompts.py`, same "explicit statement only, never inferred, empty
  list is the normal answer" discipline as intent classification), and persists
  whatever clears the confidence floor. Deliberately its own node, not folded into
  `run_agent`: extraction can never change what the user was already told, and a
  failure there does not fail the turn — two responsibilities that must never entangle
  get two places to change independently.
- **Supersession policy**: `preference`/`goal` are single-current-value-per-profile — a
  new one supersedes whatever was active. `recurring_finding` accumulates instead
  (deduplicated only against an exact repeat), since a player can genuinely have
  several distinct recurring weaknesses at once. A real semantic "does this update an
  existing entry" judgment is not attempted this phase — D-026 records why.
- **`recall_memory`** joins the chat agent's tool set (an 8th tool) — retrieval exposed
  to the agent, not a fixed context-injection step, the same posture every other
  capability in this project takes (rule 12).
- **Audit UI** (`features/memory/`, `/memory`): lists active and superseded entries —
  superseded ones shown dimmed with "No longer active," not hidden, since the entire
  point of superseding rather than overwriting is that a wrong memory stays traceable.
  A delete button on active entries only; deleting is a real removal from both stores,
  a different guarantee than the system's own superseding.

## Completed

| Deliverable | Status |
|-------------|--------|
| Long-term memory store via a LangGraph store (`AsyncPostgresStore`) | ✅ |
| Memory write policy with a confidence floor | ✅ |
| Memory audit surface in the UI (list + delete) | ✅ |
| Preference retention | ✅ |
| Recurring pattern retention | ✅ |
| Coach notes | Deferred (D-026) |
| Memory retrieval scoped by profile (`recall_memory` tool) | ✅ |
| Approval rules for memory writes (confidence floor, silent) | ✅ |
| Deterministic memory-quality evaluation, run for real against `gpt-4o-mini` | ✅ |
| Verified live end to end in a real browser: stated a preference in chat, saw it in the audit list, deleted it | ✅ |

## Files created or changed

**Backend**

```
backend/app/
  db/models/memory.py             new — LongTermMemory, MemoryKind
  domain/memory/                   new — prompts (extraction), service, queries
  domain/chat/service.py          +opens the store alongside the checkpointer per turn
  orchestration/store.py          new — AsyncPostgresStore lifecycle
  orchestration/graphs/chat.py    +write_memory node, +ChatGraphDeps.memory
  orchestration/tools/context.py  +store field (optional, Phase 10 tools unaffected)
  orchestration/tools/memory_tools.py  new — recall_memory
  api/routes/memory.py            new — list, delete
  schemas/memory.py               new
backend/alembic/
  env.py                          +include_object filter (checkpoint*/store* table prefixes)
  versions/..._long_term_memory.py  new migration
backend/.env.example              +MEMORY_WRITE_CONFIDENCE_FLOOR
backend/tests/  (3 new files, 24 new tests; +5 more in existing tool/graph test files)
  test_memory_extraction.py, test_memory_service.py, test_memory_routes.py
backend/evals/
  datasets/golden/memory_retention.jsonl        new — 10 synthetic scenarios
  harness/memory_dataset.py, memory_eval.py      new
  suites/memory_quality/test_memory_quality.py   new
  runs/..._memory_quality.json                   new — real run, gpt-4o-mini
final_docs/v2/configuration.md    +Long-term memory section
final_docs/v2/evaluation-strategy.md  +cross-profile leak rate note
final_docs/v2/decisions-log.md    +D-026
```

**Frontend**

```
frontend/src/features/memory/
  api/memory.ts, hooks/useMemory.ts    new
  components/MemoryList.tsx, MemoryPanel.tsx (+test)   new
  index.ts                              new
frontend/src/shared/lib/api-client.ts  +delete method (first DELETE caller in the app)
frontend/src/pages/MemoryPage.tsx      new
frontend/src/app/router/index.tsx      +/memory route
frontend/src/app/layouts/RootLayout.tsx  +Memory nav link
```

## Tests

- Backend: 679 passing (29 new: 24 across three dedicated memory test files, 3
  `recall_memory` tool tests, 2 `write_memory` graph-integration tests), `mypy app`
  clean, `ruff check`/`ruff format --check` clean.
- Frontend: 64 passing (6 new: 2 for the new `apiClient.delete`, 4 for `MemoryPanel`),
  `tsc`, `oxlint`, `prettier` clean.
- Evaluation: `uv run pytest evals/suites/memory_quality` — 2 passed, 1 skipped (the
  reviewed-set-gated retention-rate assertion, per the golden-vs-synthetic rule).

## Evaluation — real run against `gpt-4o-mini`

Recorded at `evals/runs/20260728T204941Z_memory_quality.json` (10 synthetic scenarios,
real extraction calls, plus a real-Postgres structural check):

| Metric | Score | Gate |
|--------|-------|------|
| `retention_true_positive_rate` | **100%** (10/10) | Soft until the golden set is human-reviewed |
| `retention_true_negative_rate` | **100%** (10/10) | Soft until the golden set is human-reviewed |
| `staleness_resolved` | **True** | Hard, structural — real Postgres, not a fake |
| `cross_profile_isolated` | **True** | Hard, structural — real Postgres, not a fake |

The retention set deliberately included an adversarial case
(`never-extract-from-assistant-words-alone`: the assistant's own reply says "I will
remember that you want to focus on defense," the player's message is just "ok") to
check the extraction prompt does not attribute a durable statement to the wrong
speaker. It scored correctly, along with every other scenario — a clean 10/10, not
selectively reported.

## Known gaps

- **Retention rates are soft-gated on an unreviewed golden set** — same documented
  pattern as every prior phase's initial golden set.
- **No semantic conflict resolution** — supersession is same-kind-replaces-same-kind
  for `preference`/`goal`, exact-string dedup for `recurring_finding`. Two goals worded
  differently that mean the same thing both stay active. D-026 records this as an
  intentional MVP simplification, not an oversight.
- **`coach_note` is out of scope** — confirmed with the owner; no coach-viewing feature
  exists yet for it to serve.
- **No memory-aware persona-fidelity check** — Phase 9 built dedicated persona-fidelity
  scoring for reports; chat's persona voice already existed at Phase 10, and this phase
  did not extend fidelity scoring to cover recalled-memory phrasing specifically.

## Recommendation

Ready for sign-off. Both structural guarantees (staleness resolution, cross-profile
isolation) are enforced in code and verified against real Postgres, not a fake; the one
LLM-judgment-dependent metric (retention accuracy) scored perfectly on a real run
including an adversarial case designed to catch a real failure mode; and live testing
confirmed the full loop — state a preference in chat, see it audited, delete it — works
against the real stack, not just in tests.
