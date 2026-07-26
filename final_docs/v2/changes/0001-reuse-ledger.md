# Reuse Ledger — `grandmate/` → `grandmate-v2/`

Required by `claude.md`: any code, data, or logic adapted from the reference application
must be recorded here.

## Rules

- `grandmate/` is read-only. It is never modified.
- Reuse is intentional, never accidental. Nothing is copied because it happened to be
  there.
- Anything adapted is reviewed, renamed to match the v2 architecture, and re-tested.
- The v2 architecture's boundaries win. The reference app was more monolithic; adapted code
  is split to fit the domain module structure.
- Where the reference implementation conflicts with the v2 plan, the plan wins.

## Status legend

**Planned** — identified, not yet ported · **Ported** — adapted and merged · **Rejected** —
evaluated and not used

---

## Data and corpus

| Item | Reference path | v2 destination | Phase | Status | Notes |
|------|---------------|----------------|-------|--------|-------|
| Carlsen PGN collection (75 of 7,818 games) | `backend/data/pgn/Carlsen.pgn` | `backend/tests/fixtures/pgn/` | 4 | Ported (trimmed) | Volume and realistic master play. Does not cover edge cases — see `edge_cases.pgn` below. Trimmed from the full 7,818-game file to the first 75 per the owner's request to keep MVP fixture footprint small — see D-009 amendment in `decisions-log.md`. Runs in the default test suite; no separate slow tier. |
| Praggnanandhaa PGN collection (75 of 2,775 games) | `backend/data/pgn/Praggnanandhaa.pgn` | `backend/tests/fixtures/pgn/` | 4 | Ported (trimmed) | Same trimming, same reason. |
| Curated edge-case PGN set (8 games: RAV variations, comments, NAGs, minimal/missing headers, aborted games, non-standard time controls, `%clk` annotations) | — (new, not reused) | `backend/tests/fixtures/pgn/edge_cases.pgn` | 4 | Ported | Self-authored per D-009's instruction to add a curated edge-case set; no external source. |
| Tactical motif notes | `backend/data/corpus/strategies/tactics.md` | `corpus/tactics/` | 7 | Planned | Good quality prose, one motif per section. Seeds the `tactics` bucket and the taxonomy in `glossary.md`. Needs provenance and licence review. |
| Concept notes (tactics) | `backend/data/corpus/rules/concept_notes_tactics.md` | — | 7 | **Rejected** | Byte-identical duplicate of `tactics.md`. Ingesting both would double-weight the same content in retrieval. |
| FIDE Laws of Chess PDF | `backend/data/corpus/rules/FIDE - LawsOfChess.pdf` | `corpus/rules/` | 7 | Planned | Authoritative. Verify the edition and re-download from FIDE rather than trusting the vendored copy. |
| Stockfish notes | `backend/data/corpus/rules/stockfish.md` | `corpus/rules/` | 7 | Planned | Engine semantics. Review for accuracy against the current Stockfish version. |
| Openings TSV (65 rows) | `backend/data/corpus/strategies/openings.tsv` | partial | 6, 7 | **Rejected as identification data** | Too small and not authoritative; replaced by the Lichess CC0 dataset per ADR-0009. The prose descriptions are still useful and move into the `openings` corpus bucket as explanatory text. |

## Logic

| Item | Reference path | v2 destination | Phase | Status | Notes |
|------|---------------|----------------|-------|--------|-------|
| Stockfish UCI adapter | `backend/src/coach/analysis/engine.py` | `backend/app/integrations/engine/` | 5 | Planned | Adapt behind an interface. Must add the tiered depth policy and pin `ENGINE_THREADS=1` for determinism — neither is in the original. |
| Move classification thresholds | `backend/src/coach/analysis/classify.py` | `backend/app/domain/analysis/` | 5 | Planned | Threshold values (50/100/300 cp) reused as starting points. Logic rewritten to read from configuration rather than module constants. |
| Analysis pipeline | `backend/src/coach/analysis/pipeline.py` | `backend/app/domain/analysis/` | 5 | Planned | Reference for sequencing only. Structure does not survive: v2 splits this across domain modules and workers. |
| Theme detection | `backend/src/coach/analysis/themes.py` | `backend/app/domain/patterns/` | 6 | Planned | Review heuristics individually. Each detector becomes a separately testable unit with a confidence score. |
| Legal-move guardrail | `backend/src/coach/tools/legal_moves.py` | `backend/app/orchestration/tools/` | 10 | Planned | Becomes the `validate_line` tool. Good idea, straightforward logic. |
| Lichess fetcher | `backend/src/coach/ingestion/lichess.py` | `backend/app/integrations/lichess/` | 14 | Planned | Export logic reusable. Auth changes completely: v2 uses the logged-in user's OAuth token per ADR-0007. |
| Chess.com fetcher | `backend/src/coach/ingestion/chesscom.py` | `backend/app/integrations/chesscom/` | 14 | Planned | Monthly archive traversal reusable as-is in shape. |
| PGN ingestion | `backend/src/coach/ingestion/pgn.py` | `backend/app/domain/imports/` | 3 | Planned | Reference for parsing policy. v2 adds content-hash deduplication and a structured failure taxonomy. |
| Guardrails | `backend/src/coach/guardrails.py` | `backend/app/domain/chat/` | 10 | Planned | Review before adapting. v2's grounding guardrail is stricter and checks against the analysis record. |
| LLM gateway (litellm) | `backend/src/coach/llm/gateway.py` | — | 6 | **Rejected** | v2 uses an owned provider interface per ADR-0006. The gateway pattern informed the design; the code is not carried over. |
| RAG loader / vector DB / pipeline | `backend/src/coach/rag/` | — | 7 | **Rejected as code** | Chroma/Qdrant-based; v2 uses pgvector with multi-bucket hybrid retrieval. Useful as reference for chunking decisions only. |
| Agent graph and memory | `backend/src/coach/agent/` | — | 10, 11 | **Rejected as code** | v2's three-layer memory model and agentic tool design differ substantially. Read for LangGraph patterns. |

## Evaluation

| Item | Reference path | v2 destination | Phase | Status | Notes |
|------|---------------|----------------|-------|--------|-------|
| RAGAS test harness | `evals/test_rag.py` | `evals/harness/` | 7 | Planned | Harness shape is a useful starting point. v2 adds the score ledger, versioning, and threshold gating that the original lacks. |
| Retriever comparison script | `evals/compare_retrievers.py` | `evals/suites/retrieval/` | 7 | Planned | Directly relevant to the dense vs sparse vs hybrid comparison. |
| Grounding tests | `evals/test_grounding.py` | `evals/suites/answer_quality/` | 10 | Planned | Review and extend. |
| Detection tests | `evals/test_detection.py` | `evals/suites/chess_correctness/` | 6 | Planned | |
| Synthetic generator | `evals/generate_synthetic.py` | `evals/harness/` | 16 | Planned | v2 derives reference answers from deterministic analysis rather than from a model — see `evaluation-strategy.md`. |

## Not carried over

| Item | Reason |
|------|--------|
| Flat `src/coach/` package structure | v2 uses domain modules per `project-plan.md` |
| Flat `frontend/src/components/` layout | v2 uses feature-driven structure |
| SQLite persistence (`coach.db`) | v2 uses Supabase Postgres per ADR-0002 |
| Chroma / Qdrant vector stores | v2 uses pgvector per ADR-0002 and ADR-0008 |
| `render.yaml`, `fly.toml` | Hosting deferred to Phase 17; not coupling to old deployment assumptions |
| Gemini-primary model configuration | v2 defaults to `gpt-4o-mini` per ADR-0006 |

## Review requirement

Nothing on this ledger moves from Planned to Ported without being read in full, adapted to
the v2 module structure, renamed to v2 conventions, and covered by tests written against
v2 expectations. The reference implementation is a starting point for thinking, not a
source of trusted code.
