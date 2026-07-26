# ADR-0005 — Three-Layer Memory Model

- **Status**: Accepted (principle) — retention detail deferred to Phase 11
- **Date**: 2026-07-25
- **Phase**: 0
- **Deciders**: Project owner

## Context

`claude.md` rule 10 and the memory rules require that short-term thread state, long-term
profile memory, and analysis truth stay architecturally distinct. Collapsing them is the
default outcome if nobody actively prevents it, because "just put it all in the
conversation history" is always the easiest next step.

## Decision

Three stores, never merged.

| Layer | Mechanism | Lifetime | Contents |
|-------|-----------|----------|----------|
| Short-term thread state | LangGraph checkpointer | Thread | Active profile, active game, persona, recent turns, comparison context |
| Long-term profile memory | LangGraph store + audited Postgres mirror | Cross-session | Preferences, goals, confirmed recurring findings, coach notes |
| Analysis truth | Postgres | Permanent | Games, moves, evaluations, aggregates, reports |

**Write policy for long-term memory** (principle locked, thresholds set at Phase 11):
- Only explicit user preferences, confirmed goals, validated aggregation findings above a
  confidence floor, and role-appropriate notes.
- Never write raw conversation turns.
- Entries **supersede** rather than overwrite; `superseded_at` is set, the row remains.
- Every entry is visible in a user-facing audit surface and user-deletable.
- Scoped to `profile_id`. No cross-profile reads.

## Rationale

The three layers differ in lifetime, trust, and correction cost, which is why one store
cannot serve all three.

Analysis truth is derived and reproducible — if it is wrong, re-run the analysis. Long-term
memory is asserted and not reproducible — if it is wrong, it stays wrong until someone
notices. Short-term state is disposable.

The failure being designed against is specific: an assistant that keeps repeating something
the user said once, months ago, that was never true or is no longer true. Superseding
rather than overwriting means such an entry can be traced back to the message that created
it. The audit surface means the user can find it. Requiring a confidence floor means fewer
get in.

Mirroring the LangGraph store into Postgres is the deliberate extra cost here. A memory the
user cannot inspect is a memory the user cannot trust, and "the assistant knows things
about me that I cannot see or delete" is not an acceptable property for a coaching product.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Single conversation store with everything | Violates rule 10; no way to expire thread state without losing durable facts |
| Long-term memory in the LangGraph store only | Not inspectable or deletable by the user |
| Write every turn to long-term memory | Accumulates noise; makes retrieval worse over time, not better |
| Overwrite on conflict | Destroys the trail needed to explain a wrong memory |

## Consequences

### Positive
- Thread state can be discarded without losing durable facts
- Users can inspect and delete what is remembered
- Wrong memories are traceable to their source
- Profile isolation enforceable at one boundary

### Negative
- Two writes for a durable memory (store and mirror), needing consistency handling
- More moving parts than a single conversation log
- The confidence floor will reject some genuinely useful memories

### Follow-up required
- Phase 11: exact confidence floor, retention windows, conflict resolution rules
- Phase 11: memory audit UI
- Phase 11: cross-profile isolation test suite

## References
- `claude.md` — Memory Rules
- `final_docs/v2/data-model.md` — `long_term_memory`
- Decision D-013
