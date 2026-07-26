# ADR-0004 — Tiered Engine Analysis Policy at Baseline Depth 12

- **Status**: Accepted
- **Date**: 2026-07-25
- **Phase**: 0
- **Deciders**: Project owner

## Context

Engine analysis is the dominant compute cost. A 40-move game is 80 positions; importing 60
games is roughly 4,800 positions. Analysing every position deeply is slow and expensive,
but analysing everything shallowly misses the positions that actually matter.

The reference application used a flat depth of 16 for every position.

## Decision

**Tiered analysis.**

1. **Sweep pass** — every ply at `ENGINE_DEPTH`, default **12**. Produces evaluations,
   best moves, and eval swings for the whole game.
2. **Deep pass** — only positions flagged as candidate critical moments, at
   `ENGINE_DEEP_DEPTH`, default 18. A position is a candidate when its eval swing exceeds
   `CRITICAL_SWING_CP`, or when the position transitions between winning and non-winning.

Determinism requirements: `ENGINE_THREADS=1`, fixed hash size, fixed depth. No time-based
limits, which are not reproducible across machines or load conditions.

Move classification thresholds start at the reference application's values — inaccuracy
50cp, mistake 100cp, blunder 300cp — and are revisited at Phase 5 against real
distributions.

Every value is configuration. No engine constant appears as a literal in code.

## Rationale

Depth 12 was chosen by the owner as a starting point, and it is a sound one. It is deep
enough to catch material blunders and most tactical errors — the class of mistake a club
player most needs surfaced — while being several times faster than depth 16.

The tiering is what makes the shallow baseline acceptable. The positions where depth
actually matters are precisely the ones where the evaluation moved sharply, and those are
identifiable from the cheap pass. Spending the expensive analysis only there gives most of
the accuracy of a uniform deep analysis at a fraction of the cost.

Single-threaded is not a performance oversight. Multi-threaded Stockfish is
non-deterministic across runs because thread scheduling affects the search, and Phase 5's
exit criterion requires identical classifications on repeated runs. Throughput comes from
running multiple games in parallel workers, not multiple threads per position.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Flat depth 16 everywhere, as in the reference app | Roughly 3–4× the cost for accuracy that matters at only a handful of positions per game |
| Time-based limits (`movetime`) | Not reproducible; violates the determinism requirement |
| Node-count limits | More reproducible than time but less intuitive to reason about and tune |
| Deep analysis only, no sweep | Cannot identify critical moments without first evaluating everything |
| Multi-threaded for speed | Non-deterministic; breaks the Phase 5 exit criteria |

## Consequences

### Positive
- Substantially lower cost per game than uniform deep analysis
- Reproducible classifications
- Depth is tunable per environment without code changes
- Deep analysis concentrated where it changes conclusions

### Negative
- Two-pass logic is more complex than one loop
- A quiet positional error with a small eval swing may be missed by the sweep and never reach the deep pass
- Depth 12 may misjudge deep tactical sequences; accepted as a documented limitation

### Follow-up required
- Phase 5: measure cost per game and classification stability; revisit thresholds against real distributions
- Phase 5: document known limitations of depth 12 for the evaluation record

## References
- `final_docs/v2/configuration.md` — engine variables
- Decision D-010
