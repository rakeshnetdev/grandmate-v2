# Phase 7 Report — Knowledge Corpus and RAG Foundation

**Date**: 2026-07-27
**Status**: Complete, pending sign-off

## Completed

| Deliverable | Status |
|-------------|--------|
| Preliminary fix: Phase 5 background-job race (background analysis jobs never completing via the real server) | ✅ |
| Curated, provenance-tracked knowledge corpus — `rules`, `openings`, `tactics`, `strategy` buckets | ✅ |
| Corpus ingestion pipeline: provenance validation, per-bucket chunking, embedding, idempotent persistence | ✅ |
| pgvector dense retrieval, BM25 sparse retrieval, reciprocal rank fusion hybrid retrieval | ✅ |
| Heuristic bucket router (`select_buckets`) | ✅ |
| Profile-scoped `analysis` bucket: DB schema, retriever, per-game content projector | ✅ |
| OpenAI embedding adapter (`EmbeddingProvider`) and pgvector similarity-search adapter | ✅ |
| RAGAS (non-LLM) retrieval evaluation harness, run for real against a real, ingested corpus, including MRR | ✅ |
| Golden retrieval dataset (41 queries) — drafted, **not yet human-reviewed** | ⚠️ pending owner spot-check |
| `analysis`-bucket profile-isolation test suite | ✅ |
| `GET /dev/search` — manual HTTP retrieval testing, added post-hoc at owner request (see Deviations) | ✅ |

## Files created or changed

**Backend**

```
backend/
  app/
    api/routes/imports.py, analysis.py          +explicit commit before scheduling
                                                  background task (Phase 5 fix)
    core/config/groups.py                       +RetrievalSettings.corpus_data_dir,
                                                  retrieval_bm25_k1/b
    db/models/knowledge.py                       KnowledgeBucket, KnowledgeDocument,
                                                  KnowledgeChunk, AnalysisKnowledgeChunk
    domain/knowledge/
      provenance.py                              header parsing/validation
      chunking.py                                heading-based + token-window chunkers
      ingestion.py                               KnowledgeIngestionService
      analysis_projection.py                     AnalysisProjectionService
    domain/retrieval/
      interfaces.py                              RetrievedChunk
      dense.py, sparse.py, fusion.py, hybrid.py   the three strategies + RRF
      router.py                                   select_buckets heuristic
      analysis_retriever.py                       AnalysisRetriever (profile-scoped)
    integrations/llm/openai_provider.py           OpenAIEmbeddingProvider
    integrations/vectorstore/pgvector_store.py    search_knowledge_chunks,
                                                    search_analysis_chunks
    api/routes/dev.py                             +GET /dev/search (post-hoc addition,
                                                    see Deviations)
  alembic/versions/..._knowledge_corpus_and_retrieval.py
  data/corpus/                                    rules/, openings/, tactics/, strategy/
                                                    + PROVENANCE.md
  evals/
    datasets/golden/retrieval.jsonl               41 golden queries
    harness/ragas_compat.py, dataset.py,
             retrieval_eval.py                     the harness itself
    suites/retrieval/test_retrieval_quality.py     pytest wrapper (run via `pytest evals/`)
    runs/                                          1 recorded run (earlier iterative
                                                     debugging runs from this session
                                                     removed before commit)
  scripts/ingest_corpus.py                        one-shot ingestion runner
  .env.example, configuration.md                   Retrieval section keys
  pyproject.toml                                   openai, pgvector, rank-bm25, pypdf,
                                                     tiktoken, ragas (<0.4), rapidfuzz
  tests/
    fake_embeddings.py                             deterministic FakeEmbeddingProvider
    test_import_analysis_dispatch_integration.py   1 test — Phase 5 fix regression
    test_dev_search_routes.py                       6 tests — GET /dev/search
    test_knowledge_provenance.py                  13 tests
    test_knowledge_chunking.py                     8 tests
    test_knowledge_ingestion.py                     4 tests
    test_knowledge_analysis_projection.py           5 tests
    test_retrieval_dense.py                         4 tests
    test_retrieval_sparse.py                        4 tests
    test_retrieval_fusion.py                        6 tests
    test_retrieval_hybrid.py                        2 tests
    test_retrieval_router.py                        7 tests
    test_retrieval_analysis_isolation.py            5 tests
    db_fixtures.py                                  +join_transaction_mode fix,
                                                     +CREATE EXTENSION vector
```

## Test results

```
466 passed (64 Phase-7-specific, across the files above)
  ruff check    All checks passed!
  ruff format   210 files already formatted
  mypy (strict) Success: no issues found in 135 source files (app/ only, matching
                 Phase 6's own scoping — evals/ and scripts/ are outside app/)
```

`evals/` is a separate suite by design — needs a real `OPENAI_API_KEY` and an ingested
corpus, run via `uv run pytest evals/`, not part of the hermetic default `uv run pytest`.

## Evaluation

### RAGAS retrieval harness — run for real

Corpus ingested for real (`uv run python -m scripts.ingest_corpus`, from `backend/`):
5 documents, 92 chunks (30 from the vendored FIDE PDF, token-windowed; 62 from the four
authored markdown documents, heading-chunked). Harness run for real
(`uv run python -m evals.harness.retrieval_eval`) against the real corpus with real
`text-embedding-3-small` embeddings, scored with RAGAS's `NonLLMContextPrecisionWithReference`
and `NonLLMContextRecall`:

| Strategy | Context Precision | Context Recall | MRR | Hit rate (lexical / semantic) | Negative FP rate |
|----------|-------------------|-----------------|-----|-------------------------------|-------------------|
| Dense    | 0.907              | 0.951           | 0.914 (1.00 / 0.837)          | 100% / 94.7%                  | 100% |
| Sparse   | 0.927              | 0.983           | 0.921 (0.931 / 0.912)         | 100% / 100%                   | 100% |
| Hybrid   | 0.936              | 0.977           | **0.949** (1.00 / 0.904)      | 100% / 100%                   | 100% |

All three clear `EvaluationSettings`' soft thresholds (0.75 for both metrics) by a wide
margin. MRR (Mean Reciprocal Rank — rank-sensitive, unlike the boolean hit-rate)
included per the reuse ledger's own note that it was adapting
`compare_retrievers.py`'s Hit-Rate/MRR methodology; it was missing from the first draft
of this report and added on request. Full record:
`evals/runs/20260727T235633Z_retrieval.json` (dataset version `v1-2026-07-27`,
retriever version `phase-7-v1`).

**Three honest findings, not defects:**

1. **Hybrid does not beat both baselines on RAGAS context precision/recall** — sparse
   alone matches or slightly exceeds hybrid on those two metrics at this corpus size (92
   chunks). Per `rag-architecture.md` section 3's own explicit rule ("if hybrid does not
   beat both baselines, the simpler retriever ships"), this is the honest, recorded
   outcome, not something to paper over.
2. **But hybrid has the best MRR of the three (0.949)** — a genuinely nuanced result,
   not a contradiction of finding 1: RAGAS's context precision is a set-overlap-style
   average, while MRR asks a narrower question ("how far down the list is the *first*
   relevant hit"), and hybrid wins specifically on that question. Likely cause for both
   findings together: hand-written "semantic" queries still retain some literal
   vocabulary overlap with their target chunk, which structurally favours BM25's overall
   precision/recall — the exact caveat `grandmate/evals/compare_retrievers.py` documented
   about its own extractive query set (see the reuse ledger) — while fusion still reliably
   pulls the single best answer to the top. Which metric should decide the shipped
   default is a product call for Phase 10, not something this report decides unilaterally;
   hybrid retrieval stays fully implemented and available regardless, since Phase 10's
   agent tool can choose per query anyway.
3. **Negative (out-of-corpus) queries have a 100% "false positive" rate at every
   strategy** — expected given `RETRIEVAL_MIN_SCORE` defaults to `0.0`: every retriever
   always returns its `top_k` nearest results regardless of how irrelevant they are,
   since there is no absolute cutoff at the default setting. Not a bug; a direct,
   measured consequence of the current default threshold, worth knowing before Phase 10
   builds an agent on top of this.

### Golden dataset — drafted, not yet reviewed

41 queries (17 lexical, 19 semantic, 5 negative) across all four static buckets, derived
from the corpus itself (lexical = heading/title verbatim, semantic = a hand-written
paraphrase with the heading name avoided) — methodology adapted from
`grandmate/evals/compare_retrievers.py` per the reuse ledger. **`reviewed_by` is `null`
on every entry.** Per `evaluation-strategy.md`'s golden-vs-synthetic rule, these scores
are informative only until a human spot-checks the set — the harness and its pytest
wrapper both print/skip accordingly rather than silently treating them as authoritative.
**This is the one explicit ask back to the owner from this phase**: please spot-check a
sample of `evals/datasets/golden/retrieval.jsonl` and confirm it can be marked reviewed.

**Deviation from `evaluation-strategy.md`'s stated target**: that document targets ~80
queries for `golden/retrieval` long-term. 41 was proposed and flagged in the approved
Phase 7 plan as more proportionate to this phase's MVP-sized corpus (92 chunks) — padding
to 80 against a corpus this size would mean many low-signal queries. Growing the set
alongside the corpus in later phases is the intended path, not a permanently accepted
shortfall.

## Decisions honoured

| Decision | How |
|----------|-----|
| Rules bucket / FIDE PDF licence (owner decision, this phase) | Vendored as-is; licence recorded honestly as "unclear" in `data/corpus/PROVENANCE.md`, not invented |
| Strategy bucket sourcing (owner decision, this phase) | Original prose informed by general, openly-described chess theory; no text reproduced from any single source |
| Reuse of GrandMate v1 corpus content (owner decision, this phase) | Validated against v1's `tactics.md`/`stockfish.md`/`openings.tsv` for accuracy, then rewritten as original v2 prose — never copied verbatim. Recorded in `final_docs/v2/changes/0001-reuse-ledger.md` |
| Phase 5 defect (owner decision, this phase) | Fixed as the first commit on this branch; regression test exercises the real `BackgroundTasks` + dual-session path, not just direct service calls |
| Rule 12 (retrieval is first-class, not a helper) | `domain/retrieval` and `domain/knowledge` are dedicated domain modules with their own tests and their own recorded evaluation |
| Rule 13 (one implementation per capability) | `hybrid_search` is the single dense+sparse+fusion implementation every future caller (Phase 10 agent tool, Phase 12 MCP server) shares |
| Rule 14 / rag-architecture.md §5 (analysis bucket profile isolation) | `AnalysisRetriever.search` requires `profile_id` as a keyword-only argument; `analysis_knowledge_chunks` requires it as a `NOT NULL` column; dedicated adversarial isolation test suite |
| Rule 11 (no hardcoded tunables) | All new knobs (`corpus_data_dir`, BM25 k1/b) live in `RetrievalSettings`, sourced from `.env` |
| RAGAS requirement (`claude.md`) | Real `ragas` library, non-LLM context precision/recall metrics, run against a real corpus with real embeddings — not hand-rolled equivalents under a different name |

## Deviations from plan

- **Golden set size (41, not ~80)** — flagged above and in the approved plan itself.
- **`final_docs/v2/changes/phase-07-corpus.md` was not created** — the existing
  `0001-reuse-ledger.md` already had rows for exactly this content, planned for Phase 7;
  updating it in place is more consistent with the project's own established convention
  than creating a duplicate file. Reuse notes live there instead.
- **`AnalysisProjectionService` is not wired into `domain/analysis/dispatch.py`'s
  background job** — see Known gaps below.
- **`GET /dev/search` added after initial sign-off review** — the plan explicitly
  scoped Phase 7 to no new routes (retrieval was meant to stay internal until Phase
  10's agent tool). The owner asked mid-review for a way to exercise retrieval over
  HTTP now rather than wait; a small dev-gated route (registered only when
  `dev_insight_active`, same production-lockout as every other `/dev/*` route,
  4xx in production) was the proportionate answer rather than building out anything
  resembling a real, versioned API surface ahead of Phase 10. Excludes the `analysis`
  bucket deliberately — it is profile-scoped and this route has no auth.
- **`scripts/project_analysis.py` added after initial sign-off review** — the owner
  asked how to test the `analysis` bucket's tie to a specific imported PGN, which
  surfaced that the projector has no automatic trigger yet (see the known gap below)
  and no manual one either. A one-shot script (`uv run python -m
  scripts.project_analysis <game_id>`, mirroring `scripts/ingest_corpus.py`) was the
  proportionate answer. Verified live against a real imported game (Ruy Lopez test
  game from this session): 6 chunks projected (1 opening, 2 motif, 3 theme), correct
  `profile_id`, confirmed idempotent on re-run (still 6 rows, not 12).

## Known gaps

| Gap | Resolution |
|-----|-----------|
| Golden retrieval dataset is entirely self-authored, `reviewed_by` unset on every entry | Explicit ask to the owner above; harness and pytest suite both treat this as informative-only until reviewed, per `evaluation-strategy.md` |
| `AnalysisProjectionService.project_game` is not called automatically after analysis/pattern detection completes | Deliberate MVP scope boundary — it requires a real embedding call per game, and this phase's scope is the retrieval substrate itself. The service is complete, independently tested, and callable manually (`scripts/project_analysis.py`, verified live); wiring it into the live background job is a small, well-contained follow-up, not a redesign |
| Hybrid retrieval does not measurably beat sparse alone at this corpus size | Recorded finding, not a defect (see Evaluation above); revisit as the corpus grows |
| `RETRIEVAL_MIN_SCORE=0.0` default means out-of-corpus queries always return something | Same — a measured consequence of the current default, worth considering before Phase 10 builds an agent on top of this retrieval layer |
| No games-list route yet | Same gap noted in Phase 4-6 reports; still out of scope here |

## Structure review

Largest new file is `evals/harness/retrieval_eval.py` at 262 lines (dataset loading +
three retrieval strategies + RAGAS scoring + run-record writing — one cohesive
orchestration responsibility, same shape as Phase 5/6's own service-file precedent).
`domain/knowledge/analysis_projection.py` at 212 lines is the next largest (four small
projection functions + one service class). No file takes on multiple unrelated
responsibilities; no refactor needed before sign-off.

## How to test this phase, live

```bash
cd backend
docker compose up -d postgres
uv run alembic upgrade head

# Ingest the real corpus (needs OPENAI_API_KEY in .env)
uv run python -m scripts.ingest_corpus

# Run the RAGAS harness for real
uv run python -m evals.harness.retrieval_eval

# Automated regression check (hermetic, no API key needed)
uv run pytest -q
# -> 466 passed

# The eval suite specifically (needs OPENAI_API_KEY + the corpus already ingested)
uv run pytest -q evals/

# Manual retrieval over HTTP (dev-only, needs the server running and dev insight active)
uv run python -m app &
curl "localhost:7575/api/v1/dev/search?bucket=tactics&query=fork&strategy=hybrid" | python3 -m json.tool
```

## Recommendation

Ready for sign-off on Phase 7's own scope, with one explicit item outstanding: **please
spot-check a sample of the 41-query golden set** (`evals/datasets/golden/retrieval.jsonl`)
and confirm it can be marked reviewed, per the golden-vs-synthetic rule. Implementation,
tests (466 passing, including 64 Phase-7-specific), lint/type checks, and evaluation
(RAGAS harness run for real against a real ingested corpus, including MRR, with three
honestly-recorded findings rather than a table that only shows what looks good) are
complete and documented above. The Phase 5 background-job race, discovered during
Phase 6's own manual testing and deferred at the time, is fixed and regression-tested
on this branch per your explicit decision to fold it in here.
