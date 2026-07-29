# RAG and Agent Architecture

Phase 0 design note. Implemented across Phases 7, 10, 11, 12, and 13.

RAG is a first-class subsystem in GrandMate, not a helper around the chat feature. This
document explains the shape and, more importantly, why each piece is shaped that way.

---

## 1. The governing constraint

Chess truth is computed, not retrieved.

Stockfish says a move lost 280 centipawns. That is a fact with a provenance, and no amount
of retrieval or generation may contradict it. Retrieval supplies *explanatory* knowledge —
what a fork is, what the plan in a Catalan usually looks like, what the FIDE rule on
touch-move actually says. Generation supplies *phrasing*.

So the system has three information sources with different trust levels:

| Source | Trust | Example |
|--------|-------|---------|
| Deterministic analysis | Authoritative | "Eval went from +0.3 to −2.5 at ply 45" |
| Retrieved corpus | Reference | "A fork is a single piece attacking two targets" |
| Model generation | Untrusted alone | The sentence tying those together |

Every claim in a delivered answer must trace to one of the first two. That is what the
grounding guardrail and the critic agent enforce.

---

## 2. Multi-RAG: why buckets

A single undifferentiated index would be a mistake here, because the corpus contains
material with genuinely different retrieval characteristics.

| Bucket | Content | Chunking | Retrieval bias | Scope |
|--------|---------|----------|----------------|-------|
| `rules` | FIDE Laws of Chess, engine semantics | Small, clause-level | Sparse-leaning; rules queries are keyword-heavy | Global |
| `openings` | Opening names, ideas, typical plans | Medium, per opening family | Hybrid | Global |
| `tactics` | Motif definitions and recognition cues | Small, one motif per chunk | Dense-leaning; queries are conceptual | Global |
| `strategy` | Pawn structures, plans, endgame principles | Larger, thematic | Dense-leaning | Global |
| `analysis` | The user's own game objects and aggregates | Structured, per game or per finding | Metadata-filtered first | **Per profile** |

Two observations drive this design.

A rules query like "is castling through check legal" wants exact clause matching, and
dense embeddings blur exactly the distinctions that matter in legal text. A strategy query
like "how do I play against an isolated queen's pawn" wants semantic similarity, because
the user will not phrase it the way the corpus does. One retrieval strategy cannot serve
both well.

And the `analysis` bucket is not really a document corpus at all — it is structured data
projected into retrievable form. Its dominant filter is metadata (which game, which
profile, which ply range), with similarity as a secondary ranking. Treating it identically
to prose would waste the structure that makes it precise.

---

## 3. Hybrid retrieval

Each bucket combines a dense pgvector search and a sparse BM25 search, fused with
reciprocal rank fusion:

```
score(d) = Σ_r  1 / (RETRIEVAL_FUSION_K + rank_r(d))
```

RRF is chosen over score normalisation because dense and sparse scores are not on
comparable scales, and normalising them requires calibration that drifts as the corpus
grows. Rank-based fusion sidesteps that entirely.

Phase 7 measures dense-only, sparse-only, and fused retrieval on the same evaluation set
and records the result. **If hybrid does not beat both baselines, the simpler retriever
ships.** Complexity has to earn itself with a number.

---

## 4. Why agentic rather than a fixed chain

Consider two questions a user will genuinely ask:

> "Why was 23...Nxe4 bad?"

> "What's the general plan in the Catalan?"

The first needs the `analysis` bucket, filtered to one game and one ply range, plus
possibly `tactics` to explain the mechanism. The second needs `openings` and `strategy`
and touches the user's games not at all.

A fixed retrieve-then-generate chain must either retrieve from everything (diluting
context and burning tokens) or guess a single strategy (wrong half the time). Modelling
retrieval as **tools the agent calls** lets the agent pick, and lets it retrieve again when
the first attempt was insufficient.

That is the whole argument for agentic RAG here. It is not sophistication for its own sake;
it is that the query distribution is genuinely heterogeneous.

### The tool set

| Tool | Purpose |
|------|---------|
| `search_knowledge(bucket, query)` | Retrieve from a global corpus bucket |
| `get_game_analysis(game_id)` | Fetch the canonical analysis object |
| `list_critical_moments(game_id)` | The pivotal plies with eval swings |
| `get_profile_aggregate(profile_id, window)` | Cross-game patterns |
| `lookup_opening(epd)` | ECO and opening name |
| `validate_line(fen, moves)` | Legality check via python-chess |

`validate_line` exists specifically because models invent plausible-looking illegal moves.
It is cheap, deterministic, and catches a whole class of embarrassing errors before they
reach a user.

These same implementations back the MCP server (Phase 12). One capability, one
implementation, two surfaces.

---

## 5. Profile isolation

The `analysis` bucket contains one user's games. A retrieval that crosses a profile
boundary is a privacy breach, not a relevance bug.

Isolation is enforced **at the retriever interface**, not at the caller:

```
AnalysisRetriever.search(query, *, profile_id)   # profile_id is required, not optional
```

The filter is applied inside, unconditionally. A caller cannot forget it because there is
no code path that omits it. Cross-profile access requires an explicit permission grant
resolved from `profile_relationships`, and it emits an audit event.

This is enforced in one place and tested in CI as a dedicated isolation suite.

---

## 6. Grounding guardrail

Before an answer reaches the user:

1. Extract chess claims — move references, evaluations, motif assertions.
2. Check every referenced move exists at the cited ply in the game record.
3. Check every referenced variation is legal via `validate_line`.
4. Check numeric evaluations against `move_evaluations`.
5. On failure, regenerate once with the violation fed back; on second failure, degrade to
   a deterministic factual summary rather than delivering an ungrounded answer.

Degrading is deliberate. A boring correct answer beats a fluent wrong one, particularly for
the kid persona where the reader cannot detect the error.

---

## 7. Multi-agent design (Phase 13)

A supervisor routes to specialists:

| Agent | Responsibility | Tools |
|-------|---------------|-------|
| Supervisor | Intent classification, routing, assembly | none |
| Retriever | Corpus search and reranking | `search_knowledge`, `search_analysis` |
| Chess analyst | Analysis interpretation | `get_game_analysis`, `list_critical_moments`, `get_profile_aggregate`, `lookup_opening` |
| Coach | Persona-appropriate phrasing, recommendations | none |
| Critic | Verifies the draft against deterministic truth | `validate_line`, `get_game_analysis` |

**Implementation note (Phase 13):** `search_analysis` was added to the Retriever's tool
set, not left with the Chess analyst — this table predates that tool's Phase 10 build.
It groups by retrieval *mechanism* rather than subject matter: `search_analysis` is
`domain/retrieval`'s hybrid search over the user's own games, the same machinery
`search_knowledge` uses over the general corpus, while every Chess analyst tool is a
structured deterministic lookup (`domain/analysis`/`domain/analytics`/`domain/patterns`)
with no ranking or semantic matching involved. The critic's tools are reached via
`validate_answer`, reused unchanged from Phase 10, not a second implementation.

The critic is the agent that justifies the pattern. Separating drafting from verification
means the verifier is not invested in the draft it is checking, which is measurably better
at catching fabrication than asking one model to self-check.

**This phase must prove itself.** Phase 13's exit criterion is that the multi-agent path
beats the Phase 10 single-agent baseline on the evaluation set. If it does not, that result
is recorded and the simpler architecture stays. Multi-agent orchestration costs latency and
tokens; it needs to buy something.

**Status:** built and evaluated at Phase 13. See
`final_docs/v2/phase-reports/phase-13-multi-agent-orchestration.md` and
`evals/runs/` for the recorded exit-criterion result.

---

## 8. Memory boundaries

Three stores, never merged:

| Store | Mechanism | Lifetime | Contains |
|-------|-----------|----------|----------|
| Short-term | LangGraph checkpointer | Thread | Active game, persona, recent turns |
| Long-term | LangGraph store + audited Postgres mirror | Cross-session | Preferences, goals, confirmed recurring findings |
| Analysis truth | Postgres | Permanent | Games, evaluations, aggregates |

Long-term memory writes are gated: only explicit preferences, confirmed goals, and
aggregation findings above a confidence floor. Entries supersede rather than overwrite, so
a wrong memory can be traced. Everything is visible and deletable in the audit surface.

The failure mode being designed against is a coaching assistant that confidently repeats
something the user said once, six months ago, that was never true.

---

## 9. Corpus provenance

Every document records source, URL, licence, retrieval date, and reviewer before it enters
a bucket. No provenance, no ingestion.

Two reasons. Legally, shipping unlicensed text is a real risk. Practically, when a
retrieval returns something wrong, the first question is always "where did that come
from?" — and a corpus that cannot answer it cannot be repaired.

Reused material from `grandmate/` is re-verified rather than trusted, and recorded in
`changes/0001-reuse-ledger.md`.
