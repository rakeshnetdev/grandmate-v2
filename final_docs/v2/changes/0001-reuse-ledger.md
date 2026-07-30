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
| Tactical motif notes | `backend/data/corpus/strategies/tactics.md` | `backend/data/corpus/tactics/tactical_motifs.md` | 7 | Ported (rewritten) | Validated against for factual accuracy per motif (all 16 of `glossary.md`'s taxonomy, not just the 10 with shipped detectors), then written as original v2 prose rather than reused verbatim — the owner's explicit instruction was "validate against v1, then write original v2 content." Provenance recorded in `data/corpus/PROVENANCE.md`. |
| Concept notes (tactics) | `backend/data/corpus/rules/concept_notes_tactics.md` | — | 7 | **Rejected** | Byte-identical duplicate of `tactics.md`. Ingesting both would double-weight the same content in retrieval. |
| FIDE Laws of Chess PDF | `backend/data/corpus/rules/FIDE - LawsOfChess.pdf` | `backend/data/corpus/rules/FIDE_Laws_of_Chess.pdf` | 7 | Ported (as-is) | Vendored unmodified per an explicit owner decision, despite the source repo carrying no licence/attribution record. Recorded honestly as "licence unclear" in `data/corpus/PROVENANCE.md` rather than an invented value — not re-downloaded/re-verified against a fresh FIDE edition (owner accepted this as-is). |
| Stockfish notes | `backend/data/corpus/rules/stockfish.md` | `backend/data/corpus/rules/engine_and_evaluation_semantics.md` | 7 | Ported (rewritten) | Validated against for accuracy, then written as original v2 prose describing this project's own UCI/centipawn/tiered-depth pipeline (Phase 5), not a generic Stockfish tutorial. |
| Openings TSV (65 rows) | `backend/data/corpus/strategies/openings.tsv` | `backend/data/corpus/openings/opening_families.md` | 6, 7 | **Rejected as identification data**, prose **ported (rewritten, expanded)** | The 65 rows themselves are too small and not authoritative for EPD identification; replaced by the Lichess CC0 dataset per ADR-0009 (Phase 6). The prose descriptions were validated against for accuracy, then rewritten as ~28 original v2 family-level entries (grouped by ECO range rather than the v1 file's 65 specific lines), expanded to cover families the v1 file lacked entirely (King's Indian, Nimzo-Indian, Grünfeld, Catalan, English, Réti, Dutch) so real-corpus coverage (Phase 6's 150-game test corpus) is representative. |
| Strategic principles notes | — (no v1 equivalent existed) | `backend/data/corpus/strategy/strategic_principles.md` | 7 | New, not reused | No source existed anywhere in the reference app for a `strategy` bucket. Per the owner's instruction to source from an open-license reference rather than hand-author from nothing, this is original prose informed by general chess strategic theory as commonly described in open-licence references (e.g. CC BY-SA encyclopaedic overviews) — no text reproduced from any single source. Covers `glossary.md`'s 10 strategic themes plus four core plans (IQP, minority attack, opposition, passed-pawn technique). |

## Logic

| Item | Reference path | v2 destination | Phase | Status | Notes |
|------|---------------|----------------|-------|--------|-------|
| Stockfish UCI adapter | `backend/src/coach/analysis/engine.py` | `backend/app/integrations/engine/` | 5 | Ported (rewritten) | Reference used `SimpleEngine` (blocking); v2 uses `python-chess`'s async UCI API, since a blocking call inside a FastAPI background task would stall the whole server. Added the tiered depth policy, pinned `ENGINE_THREADS=1`, and stores `mate_in` as its own field rather than collapsing mate scores into a clamped fake cp value. |
| Move classification thresholds | `backend/src/coach/analysis/classify.py` | `backend/app/domain/analysis/classification.py` | 5 | Ported (extended) | Core `score_before - (-score_after)` centipawn-loss formula reused as-is — verified correct against the reference. Rewritten to read thresholds from `EngineSettings` instead of module constants, and extended from the reference's four buckets (`ok`/`inaccuracy`/`mistake`/`blunder`) to the project glossary's five (`best`/`good`/`inaccuracy`/`mistake`/`blunder`) — the reference collapsed "played the engine's exact move" and "played something else with ~0 loss" into one `ok` bucket. |
| Analysis pipeline | `backend/src/coach/analysis/pipeline.py` | `backend/app/domain/analysis/service.py` | 5 | Rejected as code | Read for sequencing ideas only, not adapted. The reference only analyses the user's own-colour moves and caches per-FEN evals across games; v2 analyses every ply of both colours (no user-colour filter exists at ingestion) and evaluates each of a game's N+1 positions exactly once per run rather than introducing a cross-game cache, which the tiered shallow/deep-pass design doesn't need at MVP scale. |
| Theme detection | `backend/src/coach/analysis/themes.py` | `backend/app/domain/patterns/` | 6 | Planned | Review heuristics individually. Each detector becomes a separately testable unit with a confidence score. |
| Opening/endgame ply heuristic | `backend/src/coach/analysis/themes.py::classify_theme` (ply<=12 "Opening"; combined Q/R/B/N count<=6 "Endgame") | `backend/app/domain/reports/game_phases.py` | 16b | Ported (repurposed) | The reference uses this only to tag one move's theme label. v2 reuses the same two thresholds to segment the *whole game* into ranges for the full game-story report's Opening/Middlegame/Endgame sections — a different purpose (narrative structuring vs. per-move tagging), independently reimplemented against v2's own `GameMove`/python-chess types, no code copied. |
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
| RAGAS test harness | `evals/test_rag.py` | `evals/harness/` | 10 | Planned | Read in full during Phase 7. It is answer-quality/chat-focused (LLM-judged faithfulness and coaching-quality over full agent-graph invocations), not retrieval-only — not applicable to Phase 7's retrieval-only harness. Revisit at Phase 10 once there is a generated answer to judge. |
| Retriever comparison script | `evals/compare_retrievers.py` | `backend/evals/harness/` | 7 | Ported (methodology only) | Read in full. The *code* is Chroma/custom-Hit-Rate-MRR-specific and not reused, but the query-generation methodology is: deriving queries from the corpus itself (a `lexical` query = the chunk's own title/name, a `semantic` query = its body with the name stripped out so exact-match can't trivially win, plus out-of-corpus `negative` queries) rather than hand-writing every golden query from scratch, and reporting bucketed vs. unbucketed retrieval separately so bucket-filtering's effect is visible rather than assumed. Rebuilt against pgvector/rank-bm25/RAGAS's non-LLM context precision/recall metrics per ADR-0008, not Chroma/BM25Okapi/Hit-Rate-MRR. |
| Grounding tests | `evals/test_grounding.py` | `evals/suites/answer_quality/` | 10 | Planned | Review and extend. |
| Detection tests | `evals/test_detection.py` | `evals/suites/chess_correctness/` | 6 | Planned | |
| Synthetic generator | `evals/generate_synthetic.py` | `evals/harness/` | 16 | Planned | v2 derives reference answers from deterministic analysis rather than from a model — see `evaluation-strategy.md`. |

## Design and frontend patterns

Visual/CSS patterns noticed while reviewing the sibling `grandmate/frontend` app for
inspiration, per the Phase 16a instruction to look at it without copying from it. No
component code, markup, or data is carried over in this section — only a described visual
formula, independently re-implemented against v2's own Tailwind theme tokens.

| Item | Reference path | v2 destination | Phase | Status | Notes |
|------|---------------|----------------|-------|--------|-------|
| Classification pill-badge coloring | `grandmate/frontend` (move-classification badges) | `frontend/src/shared/lib/classification.ts`, `frontend/src/shared/components/ui/classification-badge.tsx` | 16a | Ported (pattern only) | The "10%-opacity background / full-opacity text / 20%-opacity border" Tailwind color formula was noticed in the reference app's badge styling and re-implemented from scratch as `CLASSIFICATION_BADGE_CLASS`, using v2's own Tailwind color scale and dark-mode variants. No CSS, class strings, or component code were copied. |
| Chess-notation highlighting in prose | `grandmate/frontend` (analysis/report text rendering) | `frontend/src/shared/lib/prose.tsx` | 16a | Ported (pattern only) | The general idea of visually distinguishing SAN moves and classification words (blunder/mistake/inaccuracy/best) inline within prose was inspired by the reference app's report styling. The implementation — a `react-markdown` wrapper with a named-capture-group regex applied via component overrides — is new, written for v2's markdown-based analysis/report/chat text rather than adapted from any reference source. |

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
