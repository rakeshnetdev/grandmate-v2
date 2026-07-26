# ADR-0008 — Agentic, Multi-Bucket, Hybrid RAG

- **Status**: Proposed — pending owner sign-off (expands the approved plan)
- **Date**: 2026-07-25
- **Phase**: 0, implemented in Phases 7, 10, 13
- **Deciders**: Project owner

## Context

The owner's requirement: *"RAG is very important, have proper corpus and leverage corpus
as part of the plan. Retrieve knowledge corpus wherever it's needed, chat example. This
project is agentic RAG along with it should use concepts like RAG, multi-RAG, MCP, evals,
synthetic dataset/goldenset, finetuning, agents, multi-agents, langgraph."*

The original plan treated retrieval as optional — "pgvector in Postgres if semantic
retrieval is needed later" — and described chat as analysis-context injection rather than
retrieval. That framing does not support the requirement.

## Decision

**Multi-bucket corpus.** Five buckets with distinct chunking and retrieval strategies:
`rules`, `openings`, `tactics`, `strategy`, and the per-profile `analysis` bucket.

**Hybrid retrieval.** Dense pgvector plus sparse BM25 per bucket, fused with reciprocal
rank fusion. Phase 7 measures dense-only, sparse-only, and fused on the same evaluation
set; if fusion does not beat both baselines, the simpler retriever ships.

**Agentic retrieval.** Retrieval is exposed to the agent as tools — one per bucket, plus
analysis lookup and move validation — rather than run as a fixed prefix step. The agent
selects strategy per query and may retrieve iteratively.

**Isolation at the interface.** The `analysis` retriever requires `profile_id` as a
non-optional argument and applies the filter internally. No caller can omit it.

**Grounding.** Every claim traces to a deterministic analysis record or a retrieved chunk.
Enforced by the guardrail (Phase 10) and the critic agent (Phase 13).

**Provenance.** Every corpus document records source, URL, licence, retrieval date, and
reviewer before entering a bucket.

## Rationale

The buckets exist because the corpus genuinely contains material with different retrieval
characteristics. A rules query — "is castling through check legal" — wants exact clause
matching, and dense embeddings blur precisely the distinctions legal text depends on. A
strategy query — "how do I play against an isolated queen's pawn" — wants semantic
similarity, because the user will not phrase it the way the corpus does. One index cannot
serve both well.

The agentic part follows from the query distribution. "Why was 23...Nxe4 bad?" needs the
`analysis` bucket filtered to one game and ply range. "What's the plan in the Catalan?"
needs `openings` and `strategy` and touches the user's games not at all. A fixed chain must
either retrieve from everything, diluting context and burning tokens, or guess one strategy
and be wrong much of the time. Tools let the agent choose.

Isolation is enforced inside the retriever rather than at call sites because caller-side
enforcement fails the first time someone adds a new call site and forgets. There is no code
path that omits the filter, so there is nothing to forget.

Provenance is required for two reasons: shipping unlicensed text is a legal risk, and when
a retrieval returns something wrong the first question is always where it came from. A
corpus that cannot answer that cannot be repaired.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Single undifferentiated vector index | Cannot serve keyword-exact rules queries and semantic strategy queries with one strategy |
| Fixed retrieve-then-generate chain | Query distribution is heterogeneous; one strategy is wrong much of the time |
| Dense-only retrieval | Weak on rules and exact terminology; measured at Phase 7 rather than assumed |
| Analysis context injected directly, no retrieval | Does not scale past a single game; cannot answer cross-game questions |
| Isolation enforced by callers | Fails the first time a new call site forgets |
| External vector database | Synchronisation burden against the analysis rows it projects |

## Consequences

### Positive
- Retrieval strategy matches the material in each bucket
- Agent handles both game-specific and general-knowledge questions well
- Profile isolation enforced in exactly one place and testable
- Corpus is auditable and legally defensible
- MCP (ADR-0010) reuses the same tools with no duplication

### Negative
- Considerably more machinery than a single index
- Phase 7 is a substantial new phase
- Agentic retrieval costs more tokens and latency than a fixed chain
- Corpus curation with provenance is slow, manual work
- Bucket routing is a new failure mode: right answer, wrong bucket

### Follow-up required
- Phase 7: build corpus, retrievers, router, and the RAGAS retrieval harness
- Phase 7: record the dense vs sparse vs hybrid comparison and ship the simpler option if it wins
- Phase 10: agent tools, grounding guardrail, answer-quality harness
- Phase 13: critic agent; prove multi-agent beats the single-agent baseline or defer it

## References
- `final_docs/v2/rag-architecture.md`
- `final_docs/v2/evaluation-strategy.md`
- Decisions D-015, D-016
