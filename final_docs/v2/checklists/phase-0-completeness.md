# Phase 0 Completeness Checklist

Validation for the Phase 0 exit criteria: *"No major open product ambiguity remains."*

## Deliverables

| Deliverable | Artefact | Status |
|-------------|----------|--------|
| Product requirements document | `prd.md` | ✅ |
| Architecture decision records | `adr/0001`–`adr/0012` + template | ✅ |
| Domain glossary | `glossary.md` | ✅ |
| Starter motif taxonomy | `glossary.md` — 16 motifs | ✅ |
| Starter strategy taxonomy | `glossary.md` — 10 themes | ✅ |
| Data model draft | `data-model.md` | ✅ |
| Persona matrix | `persona-matrix.md` | ✅ |
| Configuration and secrets contract | `configuration.md` | ✅ |
| RAG and agent architecture | `rag-architecture.md` | ✅ |
| Evaluation strategy | `evaluation-strategy.md` | ✅ |
| Success metrics | `metrics.md` | ✅ |
| Risk register | `risk-register.md` | ✅ |
| Definition of done | `definition-of-done.md` | ✅ |
| Decision log | `decisions-log.md` | ✅ |
| Phase mapping | `phase-map.md` | ✅ |
| Reuse ledger | `changes/0001-reuse-ledger.md` | ✅ |
| Journey walkthrough | `checklists/user-journeys.md` | ✅ |

## Mandatory ask-before-decide topics

Every topic `claude.md` required be asked about before deciding.

| Topic | Status | Reference |
|-------|--------|-----------|
| PGN corpus | ✅ Answered | D-009 |
| Engine depth / time / node budget | ✅ Answered — depth 12, tiered | D-010, ADR-0004 |
| Opening data source | ✅ Answered — Lichess CC0, EPD-keyed | D-011, ADR-0009 |
| Tactical motif taxonomy | ✅ Drafted, confirmed at Phase 6 | D-012 |
| Strategic pattern taxonomy | ✅ Drafted, confirmed at Phase 6 | D-012 |
| MVP personas | ✅ Answered — self-learner, coach, kid | D-002, ADR-0011 |
| Permission policy for other profiles | ✅ Answered | D-004, ADR-0012 |
| Memory retention rules | ⏳ Principle locked, detail at Phase 11 | D-013, ADR-0005 |
| Report / export requirements | ✅ Answered — HTML, PDF deferred | D-014 |
| Hosting / deployment | ⏳ Deferred to Phase 17 by owner | D-006 |
| LLM provider and budget guardrails | ⚠️ Provider answered, spend ceiling open (Q-4) | D-005, ADR-0006 |
| Rate limits and ingestion quotas | ✅ Defaults set in configuration | `configuration.md` |

## Architecture review against non-negotiable rules

| Rule | Satisfied by |
|------|-------------|
| 1. Backend and frontend separate | ADR-0001 — independent toolchains, no shared dependency graph |
| 2. Modular, loosely coupled, debuggable | Domain modules in `project-plan.md`; service decomposition |
| 3. Feature-driven frontend | `frontend/src/features/*` structure |
| 4. No single-file complex features | Structure discipline; per-phase size review in DoD |
| 5. Comments on non-obvious behaviour | DoD checklist; commenting expectations in `claude.md` |
| 6. Every phase has impl, tests, eval, docs | `definition-of-done.md` |
| 7. No phase without sign-off | Phase gate rule; DoD sign-off section |
| 8. Deterministic analysis separate from LLM | ADR-0003, enforced by CI import lint from Phase 1 |
| 9. Personas do not alter chess truth | ADR-0011, fact-set invariance test, zero tolerance |
| 10. Short-term vs long-term memory distinct | ADR-0005 — three stores |
| 11. No hardcoded keys or constants | `configuration.md`, elevated to a non-negotiable rule |
| 12. Retrieval is first-class | ADR-0008, Phase 7, own domain modules |
| 13. One implementation per capability | ADR-0010 — shared tool layer, equality contract test |
| 14. `analysis` bucket profile-scoped | ADR-0008 — enforced at the retriever interface |

## Journey coverage

All nine journeys in `prd.md` walked step by step. One real gap found and fixed:

- **F-1**: no phase created `profile_relationships` rows, which would have made the
  coach-views-student journey unreachable. A linking flow was added to Phase 2 scope.

Details and the remaining caveats are in `checklists/user-journeys.md`.

## Deviations from the approved plan

Both require explicit owner sign-off before implementation proceeds.

| Deviation | ADR | Reason |
|-----------|-----|--------|
| Lichess OAuth replaces Supabase Auth | ADR-0007 | The owner's login requirement is incompatible with Supabase Auth, which has no Lichess provider |
| Three phases added, evaluation phase expanded | ADR-0008, ADR-0010 | The owner's agentic RAG, MCP, multi-agent, and fine-tuning requirements were absent from the original plan |

## Outstanding questions

| # | Question | Blocks |
|---|----------|--------|
| Q-1 | Confirm `gpt-4o-mini` (request read "gpt-40-min") | Phase 1 |
| Q-2 | Supabase local project details | Phase 2 |
| Q-3 | Email/password fallback for users with neither platform account? | Phase 2 |
| Q-4 | Monthly LLM spend ceiling | Phase 1 |
| Q-5 | Kid persona age band | Phase 9 |

None block Phase 1 except Q-1 and Q-4, both of which are needed at the point the `.env`
is populated.

## Exit criteria assessment

| Criterion | Assessment |
|-----------|-----------|
| No major open product ambiguity | **Met.** All mandatory topics answered or explicitly deferred with a phase attached. |
| Owner sign-off | **Pending.** |

**Recommendation**: ready for sign-off, conditional on the owner accepting the two
documented deviations (ADR-0007, ADR-0008) and answering Q-1.
