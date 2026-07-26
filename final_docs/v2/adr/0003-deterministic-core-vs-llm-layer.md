# ADR-0003 — Deterministic Chess Core Separate from the LLM Layer

- **Status**: Accepted
- **Date**: 2026-07-25
- **Phase**: 0
- **Deciders**: Project owner

## Context

`claude.md` rule 8 requires deterministic chess analysis to stay separate from LLM
explanation logic. This ADR records what that means concretely, because the rule is easy
to agree with and easy to violate incrementally.

The pressure to violate it is real: it is always tempting to let the model "just decide"
whether a move was a blunder when the classification code is inconvenient to reach.

## Decision

Two layers with a one-way dependency.

**Deterministic core** — `domain/games`, `domain/analysis`, `domain/patterns`,
`domain/aggregation`. Uses python-chess and Stockfish. Produces the canonical game object
and profile aggregates. Contains no prompts, no model calls, no LLM library imports.

**Explanation layer** — `domain/chat`, `domain/reports`, `orchestration/`. Consumes the
core's output through repositories and tools. Contains no chess computation.

The dependency points one way: the explanation layer reads the core. The core never
imports from the explanation layer.

Enforcement: an import-linting rule in CI from Phase 1, so violations fail the build
rather than relying on review.

## Rationale

The two layers have incompatible engineering properties. The core must be reproducible —
the same game at the same depth must classify identically every run, which is why
`ENGINE_THREADS` is pinned to 1. The explanation layer is inherently stochastic.

Mixing them makes the deterministic layer untestable, because you can no longer assert an
exact output. It also makes the stochastic layer unaccountable, because there is no fixed
ground truth to check an answer against. The grounding guardrail only works because there
is a deterministic record to check claims against; if the model produced the classification
too, there would be nothing to verify against.

There is a product argument as well. Chess truth is the thing users must be able to rely
on. A model that decides a move was a blunder is an opinion; an engine that measures a
280-centipawn loss is a fact.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Let the LLM classify moves directly | Not reproducible, not verifiable, and wrong often enough to matter |
| Blend engine output with LLM judgement into one score | Destroys the audit trail; no way to say which part was wrong |
| Keep the separation as convention only | Erodes under delivery pressure; enforced in CI instead |

## Consequences

### Positive
- Core is fully unit-testable with exact assertions
- Grounding guardrail has something real to check against
- Engine or model can be swapped independently
- Failures are attributable to one layer

### Negative
- Some duplication of chess vocabulary across the boundary
- The explanation layer cannot answer questions the core does not compute, which surfaces as feature requests on the core
- An extra hop for simple questions

### Follow-up required
- Phase 1: import-linting rule in CI
- Phase 10: grounding guardrail implementation
- Phase 13: critic agent verification pass

## References
- `claude.md` non-negotiable rules 8 and 9
- `final_docs/v2/rag-architecture.md` §1
