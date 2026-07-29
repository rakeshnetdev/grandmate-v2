# GrandMate v2 — Features and Use Cases by Phase

**As of**: 2026-07-28 · Phases 0–11 complete (branch `P11-long-term-memory`)

## How to read this document

The phase reports in [`phase-reports/`](phase-reports/) answer *"was this phase built
correctly"* — deliverables, tests, bugs found, gaps. This document answers the inverse:
**"given everything built so far, what can someone actually do, and how do they do it?"**

Every use case below is a concrete, runnable scenario with the exact surface (UI route or
API call) and the expected result. Each carries an honest status.

| Status | Meaning |
|--------|---------|
| ✅ | Works end to end today, verified against the real stack |
| ⚠️ | Works, but with a caveat stated inline that a user would notice |
| ⛔ | Not available yet — the phase that delivers it is named |

> **Not to be confused with** [`checklists/user-journeys.md`](checklists/user-journeys.md).
> That is a **Phase 0 planning artifact**: it maps nine hypothetical journeys to the phases
> that were *supposed* to cover them, written before any code existed. It is partly stale
> (it still describes J1 as Lichess OAuth2 PKCE, which ADR-0014 replaced with username-claim
> login). For "what works today", this document supersedes it.

### Standing prerequisites

Every use case assumes the stack is up. Stated once here; not repeated per use case.

```bash
# 1. Database
docker compose up -d postgres
cd backend && uv run alembic upgrade head

# 2. Backend  ->  http://localhost:7575   (API prefix: /api/v1)
uv run python -m app

# 3. Frontend ->  http://localhost:3535
cd ../frontend && npm run dev

# 4. Session cookie for every API example below
curl -c cookies.txt -X POST localhost:7575/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"provider":"lichess","username":"DrNykterstein"}'
```

Phases 9–11 additionally need a real `OPENAI_API_KEY` in `backend/.env`. Phase 7's
retrieval needs the corpus ingested once (`uv run python -m scripts.ingest_corpus`).

### Profile scoping (applies from Phase 8b onward)

`games`, `analysis`, `patterns`, `analytics`, `reports`, `chat`, and `memory` all accept an
optional `?profile_id=<uuid>` query param. Omitted, they read your **own** (`self`) profile;
given your **study** profile's id, they read imported material that isn't yours. A
profile id you don't own returns 404, identically to one that doesn't exist
(`api/dependencies/profile_scope.py`). In the UI this is the "My games / Study games"
toggle, carried as `?profile=` across `/games`, `/games/:id`, and `/dashboard`.

---

## Capability summary

| Phase | Capability added | Primary surface | Status |
|-------|-----------------|-----------------|--------|
| 1 | Health/readiness, typed config, dev request tracing | `/health`, `/ready`, `/api/v1/dev/traces` | ✅ |
| 2 | Login by chess-platform username, session cookie, profile bootstrap | `/login` | ⚠️ no ownership proof |
| 3 | PGN ingest — paste, file, batch — with dedup and job tracking | `/imports` | ✅ |
| 4 | Canonical game object: full replay, per-ply FEN/EPD, focus colour | (feeds everything downstream) | ✅ |
| 5 | Stockfish analysis, tiered depth, 5-way move classification | `/games/:id` · `GET /analysis/games/{id}` | ✅ |
| 6 | Opening/ECO detection, 10 tactical motifs, 10 strategic themes | `/games/:id` · `GET /patterns/games/{id}` | ✅ |
| 7 | Knowledge corpus, hybrid retrieval, RAGAS eval harness | `GET /dev/search` (dev-only) | ⚠️ dev surface only |
| 8a | Games list and single-game analysis UI | `/games`, `/games/:gameId` | ✅ |
| 8 | Multi-game aggregation, recurring weaknesses, trends | `/dashboard` | ✅ |
| 8b | Private study profiles — own games vs studied games | profile toggle on all pages | ✅ |
| 9 | Persona reports (self-learner / coach / kid) over identical facts | `/games/:id` report panel | ✅ needs API key |
| 10 | Agentic RAG chat with tools, citations, thread memory | `/chat` | ✅ needs API key |
| 11 | Long-term memory: durable preferences, recall, audit + delete | `/memory` | ✅ needs API key |

---

## Phase 1 — Engineering Foundation

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| FastAPI app factory, health + readiness probes | `app/api/routes/health.py` | `GET /health`, `GET /ready` |
| Typed settings — every tunable from `.env`, zero hardcoded values | `app/core/config/` | `GET /ready` reports missing config |
| Structured logging (structlog) | `app/core/logging.py` | stdout |
| Developer insight tracing — spans recorded in-process, read out of band | `app/api/routes/dev.py` | `GET /api/v1/dev/traces`, dev-gated |
| React 19 + Vite + Tailwind v4 + shadcn/ui app shell | `frontend/src/app/` | `http://localhost:3535` |

### Use cases

#### UC-1.1 — Confirm the stack is correctly configured before doing anything else
**Actor**: developer · **Status**: ✅ works end to end
**Surface**: `GET /health`, `GET /ready`

```bash
curl localhost:7575/health
# {"status":"ok","service":"grandmate-backend","version":"0.1.0"}

curl localhost:7575/ready
# {"status":"ready","environment":"development","missing_configuration":[],
#  "checks":{"stockfish_binary":true,"llm_configured":true}}
```

**Expected**: `missing_configuration` is empty and both checks are `true`. A `false` on
`stockfish_binary` means Phase 5 analysis will fail; `llm_configured: false` means Phases
9–11 will fall back or error.
**Why this is the right first check**: readiness resolves settings from the *running app's*
state, not the cached global — a Phase 1 bug fix that makes this probe trustworthy.

#### UC-1.2 — Inspect what a request actually did, without paying for it
**Actor**: developer debugging a slow or wrong response · **Status**: ✅ works end to end
**Surface**: `GET /api/v1/dev/traces`, `GET /api/v1/dev/traces/{trace_id}`

1. Make any API request; read the `X-Trace-Id` response header
2. `curl -b cookies.txt localhost:7575/api/v1/dev/traces` to list recent traces
3. `curl -b cookies.txt localhost:7575/api/v1/dev/traces/<trace-id>` for the span tree

**Expected**: span timings, and (in development) prompt/retrieval payloads for LLM paths.
**Caveat worth knowing**: these routes are hard-gated off in production three ways — routes
not mounted, middleware not installed, and sensitive capture forced `false` regardless of
environment (ADR-0013). They are also **unauthenticated** in development.

### Not available yet at this phase

Nothing user-facing — Phase 1 is foundation only.

---

## Phase 2 — Local Postgres Foundation and Identity

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Login by naming a Lichess or Chess.com account, checked for real existence | `domain/auth/service.py`, `integrations/platforms.py` | `POST /api/v1/auth/login` |
| Signed session JWT in an httpOnly cookie | `domain/auth/session.py` | cookie |
| Automatic account + self-profile bootstrap on first login | `domain/auth/service.py` | — |
| Current user / logout | `api/routes/auth.py` | `GET /auth/me`, `POST /auth/logout` |
| Login page, header auth state, personalised home | `features/auth/` | `/login` |

### Use cases

#### UC-2.1 — Log in and get a working session
**Actor**: any user · **Status**: ⚠️ works, with a real security caveat
**Surface**: UI `/login` · API `POST /api/v1/auth/login`

1. Open `http://localhost:3535/login`
2. Toggle Lichess ↔ Chess.com, type a real username on that platform, submit

**Expected**: redirect to the home page with "Welcome back, *username*", header shows the
logged-in state. API returns the user plus a bootstrapped `self` profile.
**⚠️ Caveat (ADR-0014)**: this proves the *account exists*, not that **you own it**. Anyone
can log in as any real username. Accepted for MVP because the system analyses public games
and holds nothing private — **must** be closed before any private-data feature ships.

#### UC-2.2 — A username that doesn't exist is rejected cleanly
**Actor**: any user · **Status**: ✅ works end to end
**Surface**: `POST /api/v1/auth/login`

```bash
curl -X POST localhost:7575/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"provider":"lichess","username":"nonexistent-zzz"}'
# 404 — the UI renders "No Lichess account named ..." inline
```

**Expected**: 404, not a 500. A *network* failure reaching the platform returns 502, not a
masked CORS error — that distinction was a real bug fixed in Phase 3.

#### UC-2.3 — Session survives, then ends on logout
**Actor**: any user · **Status**: ✅ works end to end

```bash
curl -b cookies.txt localhost:7575/api/v1/auth/me      # 200, same identity
curl -b cookies.txt -X POST localhost:7575/api/v1/auth/logout   # 204
curl -b cookies.txt localhost:7575/api/v1/auth/me      # 401
```

### Not available yet at this phase

⛔ **Coach–student linking**. The `profile_relationships` table exists and cross-profile
permissions are designed (ADR-0012), but no flow creates a relationship row and no
`/players/:profileId` page exists. **Delivered by**: a future phase — see the consolidated
list at the end.

---

## Phase 3 — Ingestion MVP

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| One endpoint for pasted text, one file, many files, or a mix | `api/routes/imports.py` | `POST /api/v1/imports` |
| Any file may hold one game or many concatenated games | `domain/imports/parsing.py` | — |
| Content-hash dedup (movetext + result + players + date), per profile | `domain/imports/parsing.py` | — |
| Structured rejection reasons — one bad game never sinks the batch | `domain/imports/service.py` | job `progress.rejected[]` |
| Job tracking and polling | `db/models/imports.py` | `GET /imports/{id}`, `GET /imports` |
| Upload form + live job status UI | `features/imports/` | `/imports` |

### Use cases

#### UC-3.1 — Import a game by pasting PGN
**Actor**: club player · **Status**: ✅ works end to end
**Surface**: UI `/imports` · API `POST /api/v1/imports`

```bash
curl -b cookies.txt -X POST localhost:7575/api/v1/imports \
  -F 'pgn_text=[Event "Test"]
[White "DrNykterstein"]
[Black "Hikaru"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 O-O 1-0'
```

**Expected**: `201`, `{"status":"done","progress":{"total":1,"imported":1,"duplicates":0,
"rejected":[]}}`. In the UI the status card shows **"1 imported · 0 duplicates · 0
rejected"**.
**What happens behind that single response**: the game is parsed, deduplicated, stored,
fully canonicalized (Phase 4), opening-matched (Phase 6), and an engine-analysis job is
queued (Phase 5) — all before the response returns.

#### UC-3.2 — Re-importing the same game is caught, not duplicated
**Actor**: club player who exported twice · **Status**: ✅ works end to end

Re-run UC-3.1's exact command.

**Expected**: `201` with `{"imported":0,"duplicates":1}`.
**Why it catches more than you'd expect**: the hash is over *normalised* movetext, so the
same game re-exported with different comments or clock annotations still deduplicates.
**Known limit**: a genuinely transposed move order is not caught — content-based, not
semantic.

#### UC-3.3 — A malformed game is reported, not a crash
**Actor**: anyone with a messy export · **Status**: ✅ works end to end

```bash
curl -b cookies.txt -X POST localhost:7575/api/v1/imports \
  -F 'pgn_text=[White "A"]
[Black "B"]
[Result "1-0"]

1. e4 e5 2. Qxd8 1-0'
```

**Expected**: `201` (not an error) with `progress.rejected[0].reason == "malformed_pgn"`.
The UI lists the per-game reason so you can fix and re-submit.

#### UC-3.4 — Batch upload a season's worth of games
**Actor**: club player · **Status**: ✅ works end to end
**Surface**: UI `/imports` (multi-file picker) · API `POST /imports` with repeated `-F files=@...`

**Expected**: one job covering every game across every file, with a single
imported/duplicates/rejected tally.
**Bounded by**: `MAX_GAMES_PER_IMPORT` (default 60) and `MAX_PGN_UPLOAD_MB`, both checked
*before* any writes — an oversized submission fails fast with no partial import.

#### UC-3.5 — Check on a past import
**Actor**: club player · **Status**: ✅ works end to end

```bash
curl -b cookies.txt localhost:7575/api/v1/imports              # recent jobs
curl -b cookies.txt localhost:7575/api/v1/imports/<job-id>     # one job
```

---

## Phase 4 — Canonical Game Object

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Full `python-chess` replay: SAN, UCI, FEN before/after, EPD, clock — per ply | `domain/games/parsing.py` | `game_moves` table |
| Focus-colour and opponent resolution from your linked usernames | `domain/games/normalization.py` | `games.focus_color`, `opponent_name` |
| Structured canonicalization failure taxonomy (`UNPARSEABLE`, `REPLAY_ERROR`) | `domain/games/parsing.py` | `games.parse_error` |
| Idempotent re-canonicalization | `domain/games/service.py` | — |

Phase 4 has no user-facing surface of its own — it is the substrate Phases 5, 6, 8, and 10
all read. It runs automatically inside the same request as UC-3.1.

### Use cases

#### UC-4.1 — Confirm a game was fully replayed, with the right side identified as yours
**Actor**: developer / verifier · **Status**: ✅ works end to end
**Surface**: database (no dedicated route — the data reaches you via Phases 5/6/8a)

```bash
docker compose exec postgres psql -U grandmate -d grandmate -c \
  "SELECT focus_color, opponent_name, canonicalized_at FROM games ORDER BY created_at DESC LIMIT 1;"
# focus_color=white, opponent_name=Hikaru, canonicalized_at set

docker compose exec postgres psql -U grandmate -d grandmate -c \
  "SELECT ply, san, fen_after FROM game_moves
   WHERE game_id = (SELECT id FROM games ORDER BY created_at DESC LIMIT 1) ORDER BY ply;"
```

**Expected**: one row per ply with SAN and the resulting FEN.
**Measured reliability**: 99.991% parse accuracy over a 10,594-game real corpus (the single
failure is a zero-move forfeit that ingestion rejects earlier anyway → effectively 100% of
what reaches this stage), ~33ms per game.
**⚠️ Caveat on focus resolution**: matching is exact and case-insensitive, never fuzzy. A
display-name variant leaves the game *unresolved* rather than mismatched — the safer failure,
and the trigger for study-profile routing in Phase 8b.

---

## Phase 5 — Engine Analysis Core

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Async Stockfish UCI adapter behind an `EngineAdapter` interface | `integrations/engine/` | — |
| Tiered policy: depth-12 sweep every ply, depth-18 deep pass on critical moments only | `domain/analysis/service.py` | — |
| Five-way move classification (best / good / inaccuracy / mistake / blunder) | `domain/analysis/classification.py` | — |
| Critical-moment extraction with correct swing propagation | `domain/analysis/service.py` | — |
| Background dispatch, bounded concurrency, per-job failure isolation | `domain/analysis/dispatch.py` | — |
| Versioned analysis runs + manual retry | `db/models/analysis.py` | `POST /analysis/games/{id}/retry` |
| Job and result polling | `api/routes/analysis.py` | `GET /analysis/games/{id}`, `GET /analysis/jobs/{id}` |

### Use cases

#### UC-5.1 — Get an engine-backed evaluation of every move in a game
**Actor**: club player · **Status**: ✅ works end to end
**Surface**: UI `/games/:gameId` (Phase 8a) · API `GET /api/v1/analysis/games/{game_id}`

1. Import a game (UC-3.1)
2. Poll — the analysis runs in the background, not in the import request

```bash
GAME_ID=$(docker compose exec -T postgres psql -U grandmate -d grandmate -tA -c \
  "SELECT id FROM games ORDER BY created_at DESC LIMIT 1;")

curl -b cookies.txt "localhost:7575/api/v1/analysis/games/$GAME_ID"
# 404 while the job is pending, then 200 with per-ply eval + classification
```

**Expected**: an accuracy figure, per-ply centipawn evaluations, classifications, and
best-move suggestions.
**Timing**: ~7s for a typical 40-ply game. A 60-game batch finishes in ~1.75 minutes at
`ENGINE_MAX_CONCURRENT_GAMES=4`, entirely in the background — the import response itself
stays sub-second.
**Why 404 first is correct, not a bug**: results genuinely don't exist until the job
completes; the UI polls and shows "Analyzing…".

#### UC-5.2 — Re-run analysis on a game without losing the previous run
**Actor**: developer, or a user after a config change · **Status**: ✅ works end to end

```bash
curl -b cookies.txt -X POST "localhost:7575/api/v1/analysis/games/$GAME_ID/retry"
# 201 — a new pending job
```

**Expected**: a *new* versioned `GameAnalysis` run. The previous one is kept, not
overwritten — the same versioning philosophy as reports and aggregates.

#### UC-5.3 — A failed analysis is visible and recoverable
**Actor**: developer · **Status**: ✅ works end to end

**Expected**: a failed job is marked `FAILED` with a reason on its own row; the rest of the
batch continues; UC-5.2's retry endpoint recovers it.
**⚠️ Caveat**: there is no automatic retry/backoff — recovery is manual by design at MVP
scale.

### Not available yet at this phase

⚠️ **Games imported before Phase 5 shipped are never retroactively analysed.** No bulk
backfill job exists; UC-5.2 works per game.

---

## Phase 6 — Opening Detection and Chess Intelligence Tags

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Opening/ECO tagging from the vendored `lichess-org/chess-openings` dataset, EPD-keyed, deepest match, transposition-safe | `domain/patterns/opening_lookup.py` | `GET /patterns/games/{id}` |
| 10 tactical motif detectors: fork, pin, skewer, discovered attack, double check, back-rank mate, smothered mate, hanging piece, removing the defender, x-ray | `domain/patterns/motifs/` | same |
| 10 strategic theme detectors: weak king safety, pawn-structure damage, passed pawn, piece-activity imbalance, bad bishop, open file, centre control, space advantage, development lag, time-trouble collapse | `domain/patterns/themes/` | same |
| Confidence scoring with engine corroboration where it matters | `domain/patterns/confidence.py` | `confidence` on each finding |
| Training-theme mapping (motif/theme → coaching theme) | `domain/patterns/training_map.py` | feeds Phases 9–10 |

### Use cases

#### UC-6.1 — Identify the opening of a game, immediately
**Actor**: club player · **Status**: ✅ works end to end
**Surface**: UI `/games/:gameId` · API `GET /api/v1/patterns/games/{game_id}`

1. Import the Ruy Lopez PGN from UC-3.1
2. Query patterns straight away — no waiting

```bash
curl -b cookies.txt "localhost:7575/api/v1/patterns/games/$GAME_ID" | python3 -m json.tool
```

**Expected**:
```json
{"opening": {"eco": "C88", "opening_name": "Ruy Lopez: Closed",
             "epd": "r1bq1rk1/2ppbppp/p1n2n2/1p2p3/4P3/1B3N2/PPPP1PPP/RNBQR1K1 w - -",
             "matched_ply": 13},
 "motifs": [], "themes": []}
```

**Why no waiting**: opening lookup runs *inline* during canonicalization — it needs no
engine. `motifs`/`themes` are empty until the Phase 5 background job finishes.
**Measured accuracy**: 0 no-matches across a real 150-game corpus; 79.3% exact ECO match,
18.7% same-family, 2.0% cross-family. The mismatches are largely the detector being *more*
specific (deepest EPD match) than the exporting tool, and cluster in genuinely
transposition-ambiguous zones (English ↔ Réti, Catalan ↔ QGD).

#### UC-6.2 — Two different move orders reaching the same opening resolve identically
**Actor**: opening-conscious player · **Status**: ✅ works end to end

Import the same opening via a transposed move order.

**Expected**: the same ECO and opening name. Matching is on **position (EPD)**, not move
sequence — a locked decision (D-011 / ADR-0009) with a dedicated regression test.

#### UC-6.3 — See the tactics and strategic problems in a game
**Actor**: club player, or a coach preparing a lesson · **Status**: ✅ works end to end
**Surface**: UI `/games/:gameId` · API `GET /patterns/games/{game_id}`

1. Import a game containing a real tactic or blunder (a hanging piece is easiest to trigger)
2. Wait for `GET /analysis/games/{id}` to return 200 (UC-5.1)
3. Re-query patterns

**Expected**: `motifs` and `themes` populated, each with `ply`, `side`, `confidence`, and
`evidence`. Detection rides along in the same background job, immediately after analysis
succeeds.
**Measured precision/recall**: 20/20 recall and 0/10 false positives against real,
independently tagged Lichess puzzles (CC0) — external ground truth, not the detector
grading its own homework. Finding this bar caught a real skewer-detector bug.
**⚠️ Caveat**: structural motifs without engine corroboration (skewer, fork, x-ray) can
flag geometrically real but practically minor patterns — e.g. a bishop skewering behind a
single pawn. Only `hanging_piece` and `removing_the_defender` get engine corroboration, by
design (`confidence.py` explains why).

> **Note on the Phase 6 report's own caveat**: it records that background analysis jobs
> never completed via the live server (a Phase 5 transaction race). **That was fixed in
> Phase 7** — an explicit commit before scheduling the background task, with a regression
> test exercising the real `BackgroundTasks` path. UC-6.3 works end to end today.

### Not available yet at this phase

⛔ **6 high-difficulty motifs**: deflection, decoy, overloading, interference, zwischenzug,
windmill. Deliberately withheld (D-012) — they need engine corroboration to ship without
misleading a learner.

---

## Phase 7 — Knowledge Corpus and RAG Foundation

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Provenance-tracked corpus in 4 static buckets: `rules`, `openings`, `tactics`, `strategy` | `backend/data/corpus/` | — |
| Ingestion pipeline: provenance validation, per-bucket chunking, embedding, idempotent persistence | `domain/knowledge/` | `scripts/ingest_corpus.py` |
| Dense (pgvector), sparse (BM25), and hybrid (reciprocal rank fusion) retrieval | `domain/retrieval/` | shared by Phase 10's agent tools |
| Heuristic bucket router | `domain/retrieval/router.py` | — |
| Profile-scoped `analysis` bucket — your own games as retrievable knowledge | `domain/retrieval/analysis_retriever.py` | Phase 10 `search_analysis` tool |
| RAGAS retrieval evaluation harness with recorded, versioned runs | `backend/evals/` | `uv run pytest evals/` |
| Manual retrieval testing over HTTP | `api/routes/dev.py` | `GET /api/v1/dev/search` (dev-only) |

### Use cases

#### UC-7.1 — Ingest the knowledge corpus
**Actor**: developer, one-time setup · **Status**: ✅ works end to end

```bash
cd backend && uv run python -m scripts.ingest_corpus
```

**Expected**: 5 documents → 92 chunks (30 token-windowed from the FIDE rules PDF, 62
heading-chunked from four authored markdown documents). Re-running is idempotent.
**Needs**: a real `OPENAI_API_KEY` — this makes real embedding calls.

#### UC-7.2 — Search the knowledge corpus by hand
**Actor**: developer verifying retrieval · **Status**: ⚠️ dev-only surface
**Surface**: `GET /api/v1/dev/search?bucket=&query=&strategy=`

```bash
curl "localhost:7575/api/v1/dev/search?bucket=tactics&query=fork&strategy=hybrid" \
  | python3 -m json.tool
```

**Expected**: ranked chunks with scores. `strategy` ∈ `dense | sparse | hybrid`;
`bucket` ∈ `rules | openings | tactics | strategy`.
**⚠️ Caveat**: dev-gated (4xx in production) and unauthenticated, so it deliberately
**excludes** the profile-scoped `analysis` bucket. Real access to `analysis` arrives
authenticated via Phase 10's chat tools.

#### UC-7.3 — Score retrieval quality and record the run
**Actor**: developer / reviewer · **Status**: ✅ works end to end

```bash
uv run python -m evals.harness.retrieval_eval    # writes evals/runs/<timestamp>_retrieval.json
uv run pytest evals/                              # the gated suite
```

**Expected** (real recorded run, 41-query golden set, real embeddings):

| Strategy | Context precision | Context recall | MRR |
|----------|------------------|----------------|-----|
| Dense | 0.907 | 0.951 | 0.914 |
| Sparse | 0.927 | 0.983 | 0.921 |
| Hybrid | 0.936 | 0.977 | **0.949** |

**Three honest findings recorded rather than smoothed over**: hybrid does *not* beat sparse
on RAGAS precision/recall at this corpus size (92 chunks) though it does win on MRR; and
with `RETRIEVAL_MIN_SCORE=0.0`, out-of-corpus queries always return *something*.

#### UC-7.4 — Make one game's analysis retrievable as knowledge
**Actor**: developer · **Status**: ⚠️ manual trigger only

```bash
uv run python -m scripts.project_analysis <game_id>
```

**Expected**: ~6 chunks for a typical analysed game (opening + motifs + themes), each
carrying the correct `profile_id`. Idempotent on re-run.
**⚠️ Caveat**: `AnalysisProjectionService` is **not** wired into the background job — it
costs a real embedding call per game, deliberately left out of the automatic path at MVP
scale. Phase 10's `search_analysis` tool only sees games you've projected.

#### UC-7.5 — Confirm one profile can never retrieve another's analysis
**Actor**: reviewer / security · **Status**: ✅ works end to end

```bash
uv run pytest -q tests/test_retrieval_analysis_isolation.py
```

**Expected**: pass. `AnalysisRetriever.search` requires `profile_id` as a keyword-only
argument and the table's column is `NOT NULL` — isolation is enforced at the retriever
interface, in one place (rule 14), not at each caller.

### Not available yet at this phase

⚠️ The golden retrieval dataset (41 queries) is **self-authored and unreviewed**
(`reviewed_by` unset), so its scores are informative rather than gating.

---

## Phase 8a — Single-Game UI

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| List your games, most recent first | `domain/games/queries.py` | `GET /api/v1/games` · `/games` |
| Single game lookup, profile-scoped | same | `GET /api/v1/games/{id}` · `/games/:gameId` |
| Analysis view: accuracy, move table, classification badges, opening, motifs, themes | `features/games/` | `/games/:gameId` |

### Use cases

#### UC-8a.1 — Browse your imported games
**Actor**: club player · **Status**: ✅ works end to end
**Surface**: UI `/games` · API `GET /api/v1/games`

**Expected**: your games only (profile-scoped), most recent first. Each entry carries its
source, the raw PGN `headers` (White, Black, Result, Event, Date), and `canonicalized_at` —
`null` there means Phase 4 replay hasn't succeeded, so analysis and patterns will have
nothing to show.

#### UC-8a.2 — Review one game move by move
**Actor**: club player · **Status**: ⚠️ works, with a notation caveat
**Surface**: UI `/games/:gameId`

1. Open a game from `/games`
2. Watch it go from "Analyzing…" to a rendered result

**Expected**: accuracy percentage, move count, opening name and ECO, tactical motif count,
strategic theme count, and a full move-by-move evaluation table with classification badges.
**⚠️ Caveat**: the analysis endpoint returns ply, evaluation, classification, and
best-move-in-**UCI** — not SAN. Moves are labelled by number and side (`12.` / `12…`) and
best moves show as `e2e4` rather than `Nf3`.

---

## Phase 8 — Multi-Game Aggregation and Profile Analytics

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Last-10 / 30 / 60-game windows | `domain/analytics/service.py` | `GET /analytics/profile?window=` |
| Recurring weakness detection, polarity-correct | `domain/analytics/metrics.py` + `domain/patterns/polarity.py` | `/dashboard` |
| Opening-family performance | `domain/analytics/metrics.py` | `/dashboard` |
| Colour and time-control segmentation | same | `/dashboard` |
| Progress deltas (current window vs previous) | `domain/analytics/service.py` | `/dashboard` |
| Versioned aggregate snapshots — never updated in place | `db/models/analytics.py` | — |
| Small-sample guard | `ANALYTICS_MIN_GAMES_FOR_TREND` (default 5) | banner on `/dashboard` |

### Use cases

#### UC-8.1 — See what you keep getting wrong across many games
**Actor**: club player · **Status**: ✅ works end to end
**Surface**: UI `/dashboard` · API `GET /api/v1/analytics/profile?window=30`

```bash
curl -b cookies.txt "localhost:7575/api/v1/analytics/profile?window=30" | python3 -m json.tool
```

**Expected**: overall accuracy, classification-rate table, opening-family records,
colour split, time-control split, and a recurring-weakness list.
**The load-bearing correctness detail**: findings are polarity-aware. Creating a fork
against your opponent is an *achievement*, not a weakness; `hanging_piece` is the one motif
where being the mover *is* the problem; and `passed_pawn_creation`, `open_file_control`,
`centre_control`, `space_advantage` are achievements even though they are "themes". Getting
this backwards would have told players their own successful tactics were weaknesses. Live
verification confirmed `open_file_control` correctly excluded from the same game's weakness
list that correctly included `bad_bishop` and `development_lag`.

#### UC-8.2 — Compare recent form against your previous window
**Actor**: club player tracking improvement · **Status**: ✅ works end to end

Switch windows with the `10 / 30 / 60` selector on `/dashboard`.

**Expected**: each metric carries a delta against the equivalent previous window.
`window` must be one of the configured sizes or the API returns 422.

#### UC-8.3 — Know when not to trust a trend
**Actor**: club player with few games · **Status**: ✅ works end to end

**Expected**: with fewer than 5 analysed games (`ANALYTICS_MIN_GAMES_FOR_TREND`), the
dashboard shows a sample-size banner and trends/weaknesses are caveated rather than
asserted. This is a feature — it is what stops two games from reading as a habit.

#### UC-8.4 — Find which openings actually work for you
**Actor**: club player choosing a repertoire · **Status**: ✅ works end to end

**Expected**: an opening-family table with win/draw/loss per family, derived from Phase 6's
ECO tagging.

#### UC-8.5 — Segment performance by colour and time control
**Actor**: club player · **Status**: ⚠️ colour ✅, time control caveated

**⚠️ Caveat**: the `TimeControl` PGN header is rarely present in manually pasted games, so
that table will mostly read "Unknown" until Lichess/Chess.com imports (Phase 14) supply real
values. The bucketing logic itself is tested and correct.

### Not available yet at this phase

⚠️ **No snapshot-history endpoint.** Every request recomputes and persists a new version,
but nothing reads *past* versions yet — "progress deltas" compare current vs previous
*window*, not two historical dashboard views. Versioned storage exists so this is additive
later, not a redesign.
⚠️ **No LLM narrative over aggregates** — the dashboard is deterministic-only. Persona
reports (Phase 9) are per-game.

---

## Phase 8b — Private Study Profiles

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Every account gets a second "Study games" profile at first login | `domain/auth/service.py` | `GET /api/v1/profiles` |
| Automatic per-game import routing: header matches your username → My games, otherwise → Study games | `domain/imports/service.py`, `domain/games/normalization.py` | `/imports` |
| `?profile_id=` on every profile-scoped route, ownership-checked in one place | `api/dependencies/profile_scope.py` | all read routes |
| "My games / Study games" toggle carried in the URL | `features/profiles/` | `/games`, `/games/:id`, `/dashboard` |

### Use cases

#### UC-8b.1 — Study a master game without polluting your own statistics
**Actor**: club player studying Carlsen · **Status**: ✅ works end to end
**Surface**: UI toggle on `/games` and `/dashboard`

1. Import a batch containing one of your own games and one between two unrelated players
2. Toggle between "My games" and "Study games"

**Expected**: the batch **splits automatically** — your game under My games, the other under
Study games. `/dashboard` under My games reports only your own win rate, accuracy, and
weaknesses.
**Why this exists**: without it, every studied game silently contaminated your own dashboard
— found while testing Phase 8 against real data, and in direct conflict with ADR-0012.
Resolved by ADR-0016 / D-021.

#### UC-8b.2 — Get the same full analysis on studied material
**Actor**: club player · **Status**: ✅ works end to end

**Expected**: full pipeline parity — studied games get canonicalization, engine analysis,
patterns, *and* their own aggregate dashboard. The separation is about *whose statistics*,
not about a reduced feature set.

#### UC-8b.3 — Analysing your own game where both sides are you
**Actor**: player reviewing a self-play game · **Status**: ✅ works end to end

**Expected**: routes to **My games**. Only a genuine no-match routes to the study profile.
An account with no linked usernames at all defaults everything to My games — the
pre-Phase-8b behaviour, not silently reinterpreted.

### Not available yet at this phase

⚠️ **No UI to rename or manage the study profile.** MVP scope is exactly own-vs-study
separation, not general multi-profile management.

---

## Phase 9 — Persona Layer and Report Generation

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Three personas over identical facts: self-learner, coach, kid | `domain/reports/prompts.py` | `GET /reports/games/{id}?persona=` |
| Structured, stably-IDed facts extracted from analysis + patterns | `domain/reports/facts.py` | — |
| Persona-specific ranking and capping (self ≤5, kid ≤3 + confidence floor, coach unbounded) | `domain/reports/selection.py` | — |
| Deterministic grounding critic — fact-id existence, caps, kid centipawn suppression | `domain/reports/critic.py` | — |
| Retry-then-deterministic-fallback: a reader never sees ungrounded text or an error | `domain/reports/service.py`, `fallback.py` | source badge in the UI |
| Atomic daily LLM token ceiling | `domain/llm_usage/` | `LLM_DAILY_TOKEN_CEILING` |
| Versioned report storage keyed by analysis version | `db/models/reports.py` | — |
| Persona switcher + report panel on the game page | `features/reports/` | `/games/:gameId` |

### Use cases

#### UC-9.1 — Read a plain-language explanation of your game
**Actor**: club player · **Status**: ✅ works end to end (needs `OPENAI_API_KEY`)
**Surface**: UI `/games/:gameId` report panel · API `GET /api/v1/reports/games/{id}?persona=self_learner`

```bash
curl -b cookies.txt \
  "localhost:7575/api/v1/reports/games/$GAME_ID?persona=self_learner" | python3 -m json.tool
```

**Expected**: a summary, findings tied to real fact ids, and recommendations — direct,
second-person, at most 5 findings. Generated on demand, then stored and reused until the
game's analysis version changes.
**Prerequisite**: the game must already have a completed analysis, otherwise 404 with "No
analysis found for this game yet".

#### UC-9.2 — Same game, coach's view
**Actor**: coach preparing a lesson · **Status**: ✅ works end to end
**Surface**: persona switcher, or `?persona=coach`

**Expected**: technical, third-person ("the student"), lesson-plan-shaped recommendations,
no cap on findings — **over exactly the same facts** as UC-9.1.

#### UC-9.3 — Same game, for a child
**Actor**: junior player (8–14) · **Status**: ✅ works end to end
**Surface**: `?persona=kid`

**Expected**: at most 3 findings, low-confidence findings suppressed, **no raw centipawn
numbers**. If the model produces anything ungrounded, one retry, then a deterministic
facts-only report — never an error, never ungrounded text shown to a child.
**Observed live, not simulated**: on a real game with a real `gpt-4o-mini` call, the kid
persona fell back after two ungrounded attempts while self-learner and coach succeeded —
the safety design behaving correctly under real model output.

#### UC-9.4 — Prove personas never change chess truth
**Actor**: reviewer · **Status**: ✅ works end to end

```bash
uv run pytest evals/suites/persona_fidelity
```

**Expected** (real recorded run against `gpt-4o-mini`, 5 scenarios × 3 personas):

| Metric | Score | Gate |
|--------|-------|------|
| `fact_invariance_rate` | **100%** | Hard — never below 1.0 |
| `kid_safety_rate` | **100%** | Hard — never below 1.0 |
| `grounded_rate` | 86.7% (13/15) | Informative |

The 13.3% that fell back were the single most complex scenario for the two *cap-constrained*
personas — the critic catching over-generation, which is the safety net working.

#### UC-9.5 — Know whether what you're reading came from the model or the fallback
**Actor**: any reader · **Status**: ✅ works end to end

**Expected**: the report panel carries a source-transparency badge. `grounded` is on the API
response too.

### Not available yet at this phase

⛔ **No profile-level (aggregate) persona reports** — Phase 8's dashboard stays
deterministic. Explicitly out of this phase's confirmed scope.
⚠️ **No per-profile rate limiting on report generation** — the daily token ceiling
(default 500,000) is the only spend guard.
⚠️ **One kid persona for the whole 8–14 range** — age banding stays deferred (D-024).

---

## Phase 10 — Agentic RAG Chat with Short-Term Memory

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Chat threads, persisted and listable | `db/models/chat.py`, `domain/chat/` | `POST/GET /api/v1/chat/threads` |
| LangGraph agent with tool calling | `orchestration/graphs/chat.py` | — |
| 7 agent tools wrapping existing services: `search_knowledge`, `search_analysis`, `get_game_analysis`, `list_critical_moments`, `get_profile_aggregate`, `lookup_opening`, `validate_line` | `orchestration/tools/` | — |
| Intent routing (explain / compare / summarise / train_next), LLM-classified | `orchestration/graphs/chat.py` | — |
| Grounding guardrail over 4 citation kinds: `move`, `evaluation`, `variation`, `opening` | `domain/chat/guardrail.py` | `citations`, `grounded` on each turn |
| Thread state surviving restart via a Postgres LangGraph checkpointer | `orchestration/checkpointer.py` | — |
| Chat UI: thread list, transcript, composer, persona switcher | `features/chat/` | `/chat` |

### Use cases

#### UC-10.1 — Ask a question about a specific game
**Actor**: club player · **Status**: ✅ works end to end (needs `OPENAI_API_KEY`)
**Surface**: UI `/games/:gameId` → "Ask about this game" → `/chat`

```bash
THREAD=$(curl -s -b cookies.txt -X POST localhost:7575/api/v1/chat/threads \
  -H 'Content-Type: application/json' -d "{\"active_game_id\":\"$GAME_ID\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

curl -b cookies.txt -X POST "localhost:7575/api/v1/chat/threads/$THREAD/messages" \
  -H 'Content-Type: application/json' \
  -d '{"message":"What was my opening in this game?","persona":"self_learner"}' \
  | python3 -m json.tool
```

**Expected**: a grounded answer with citations — e.g. *"Your opening in this game was the
Ruy Lopez: Marshall Attack, classified under ECO code C89."* — plus `grounded: true`.
**What the agent actually did**: chose its own tools. It is not a fixed
retrieve-then-generate chain; retrieval is exposed *as tools* so the agent picks per query.

#### UC-10.2 — Ask about a habit rather than a game
**Actor**: club player · **Status**: ✅ works end to end

Ask *"What do I keep getting wrong?"* in a thread.

**Expected**: the agent calls `get_profile_aggregate` (Phase 8) rather than a single game's
analysis, and answers with frequency evidence.

#### UC-10.3 — A claim the record doesn't support never reaches you
**Actor**: any user · **Status**: ✅ works end to end — structurally guaranteed

**Expected**: every `move`, `evaluation`, `variation`, and `opening` citation is checked
against the same profile-scoped tables the tools read from. On a rejected answer: one retry,
then a deterministic fallback that surfaces the turn's raw tool findings and asserts nothing
of its own.
**Measured**: `grounded_rate` **100%** and `intent_valid_rate` **100%** on a real 10-scenario
run — these are properties the code guarantees, not judge estimates.

#### UC-10.4 — Resume a conversation after a reload or a backend restart
**Actor**: any user · **Status**: ✅ works end to end

1. Have a multi-turn conversation at `/chat`
2. Reload the page (or restart the backend) and reopen the thread

**Expected**: the transcript **and** which thread was open both survive — the Postgres
checkpointer persists conversation state, and the thread id lives in the URL rather than
component state.

#### UC-10.5 — Ask the agent to check a line you're considering
**Actor**: club player · **Status**: ✅ works end to end

**Expected**: `validate_line` (backed by `python-chess`) confirms legality from the position
in question, so the agent cannot assert an illegal continuation.

#### UC-10.6 — Confirm chat can never read another profile's data
**Actor**: reviewer / security · **Status**: ✅ works end to end

**Expected**: one `ToolContext` binds `profile_id` for the whole turn, and **no tool's JSON
schema exposes `profile_id` as a parameter** — there is no code path a model could use to
request another profile's data (rule 14, proven directly by a stray-argument test).

### Not available yet at this phase

⚠️ **Faithfulness scored 0.70 against a 0.85 target** on the self-authored, unreviewed
golden set. Manually reading all ten real answers found **no false or fabricated
game-specific claim**; the gap is best explained by RAGAS scoring *every* sentence including
legitimate uncited coaching advice ("study tactical patterns like forks and pins"). Flagged
for the owner — either the threshold needs recalibrating for a system that intentionally
gives uncited advice, or the output contract needs an explicit advice-vs-fact split.
⚠️ **No streaming** — single-shot request/response, because the grounding guardrail needs
the complete answer before any of it reaches the user.
⚠️ **No per-turn rate limiting** beyond the shared daily token ceiling.

---

## Phase 11 — Long-Term Memory and Profile-Aware Chat

### Features added

| Feature | Where it lives | Surface |
|---------|---------------|---------|
| Durable memory across sessions: `preference`, `goal`, `recurring_finding` | `db/models/memory.py`, `domain/memory/` | `/memory` |
| Silent, confidence-gated writes (`MEMORY_WRITE_CONFIDENCE_FLOOR`, default 0.7) | `domain/memory/service.py` | — |
| A dedicated `write_memory` graph node — extraction can never change what you were told | `orchestration/graphs/chat.py` | — |
| `recall_memory` as an 8th agent tool | `orchestration/tools/memory_tools.py` | — |
| Supersession rather than overwrite — a wrong memory stays traceable | `domain/memory/service.py` | dimmed entries in the UI |
| Memory audit surface: list active + superseded, delete active | `features/memory/` | `/memory`, `GET`/`DELETE /api/v1/memory` |

### Use cases

#### UC-11.1 — State a preference once, have it respected later
**Actor**: returning user · **Status**: ✅ works end to end (needs `OPENAI_API_KEY`)
**Surface**: `/chat`, then `/memory`

1. In chat, say something durable: *"I prefer short answers"* or *"I'm working on my time trouble"*
2. Open `/memory`

**Expected**: the statement appears as a `preference` or `goal` with a confidence score. In
a later conversation the agent's `recall_memory` tool can retrieve it without you re-stating
it.
**Write policy**: silent and confidence-gated — no confirmation prompt. The floor is the
whole enforcement mechanism for "only durable facts persist". No automatic expiry: an entry
lives until superseded or deleted.

#### UC-11.2 — Correct a preference and see the old one retained, not erased
**Actor**: user whose goals changed · **Status**: ✅ works end to end

State a new preference of the same kind.

**Expected**: the previous entry shows dimmed with "No longer active" rather than
disappearing. `preference` and `goal` are single-current-value-per-profile; superseding
rather than overwriting is what keeps a wrong memory traceable.

#### UC-11.3 — Audit and delete what the system remembers about you
**Actor**: any user · **Status**: ✅ works end to end
**Surface**: UI `/memory` · API `GET /api/v1/memory`, `DELETE /api/v1/memory/{id}`

```bash
curl -b cookies.txt localhost:7575/api/v1/memory | python3 -m json.tool
curl -b cookies.txt -X DELETE localhost:7575/api/v1/memory/<memory-id>   # 204
```

**Expected**: the full list (active *and* superseded). Delete is offered on active entries
only and is a **real removal from both stores** — a different guarantee from the system's own
superseding.

#### UC-11.4 — Confirm memory is never attributed to the wrong speaker
**Actor**: reviewer · **Status**: ✅ works end to end

```bash
uv run pytest evals/suites/memory_quality
```

**Expected** (real recorded run, 10 scenarios):

| Metric | Score | Gate |
|--------|-------|------|
| `retention_true_positive_rate` | **100%** (10/10) | Soft until reviewed |
| `retention_true_negative_rate` | **100%** (10/10) | Soft until reviewed |
| `staleness_resolved` | **True** | Hard — real Postgres |
| `cross_profile_isolated` | **True** | Hard — real Postgres |

The set deliberately includes an adversarial case where the *assistant* says "I will remember
that you want to focus on defense" and the user only says "ok" — nothing is extracted, which
is correct.

### Not available yet at this phase

⛔ **`coach_note` memories** — deliberately not even in the data model; no coach-viewing
feature exists for them to serve (ADR-0012 still defers cross-account viewing).
⚠️ **No semantic conflict resolution** — supersession is same-kind-replaces-same-kind, with
exact-string dedup for `recurring_finding`. Two goals worded differently that mean the same
thing both stay active (D-026: an intentional MVP simplification).

---

## Cross-phase use cases

These are the scenarios that only exist because several phases compose.

#### UC-X.1 — The full pipeline, one paste to a coaching answer
**Actor**: club player · **Status**: ✅ works end to end (needs `OPENAI_API_KEY` for steps 5–6)

1. `/login` — log in with your platform username *(P2)*
2. `/imports` — paste a PGN *(P3)*. In that one request it is parsed, deduplicated,
   canonicalized with per-ply FEN/EPD *(P4)*, opening-matched *(P6)*, routed to My games or
   Study games *(P8b)*, and an analysis job is queued *(P5)*
3. `/games` → open the game. Watch "Analyzing…" become a full result *(P8a)* — accuracy,
   per-ply evaluations, classifications *(P5)*, opening name and ECO, tactical motifs and
   strategic themes *(P6)*
4. `/dashboard` — once you have ≥5 analysed games, recurring weaknesses, opening-family
   records, colour splits, and progress deltas *(P8)*
5. Back on the game, switch personas to read the same facts as a self-learner, a coach, or a
   child *(P9)*
6. "Ask about this game" → `/chat` — ask why a move was bad and get a cited, grounded answer
   *(P10)*; state a preference and see it persist to `/memory` *(P11)*

**This is the demo path.** Everything in it works today against the real stack.

#### UC-X.2 — Walk the three truth levels
**Actor**: reviewer checking the PRD's core principle · **Status**: ✅ works end to end

| Truth level | Surface | Phase |
|-------------|---------|-------|
| 1. Game Analysis Object — one deterministic object per game | `GET /analysis/games/{id}` + `GET /patterns/games/{id}` | 4–6 |
| 2. Profile Aggregate Object — trends across a window | `GET /analytics/profile?window=30` | 8 |
| 3. Persona View / Chat Layer — different explanations, identical facts | `GET /reports/games/{id}?persona=` · `/chat` | 9–11 |

**Expected**: levels 1 and 2 contain no LLM output whatsoever. Level 3 never introduces a
chess claim that levels 1–2 don't support — enforced by the report critic and the chat
guardrail, and measured (`fact_invariance_rate` 100%, `grounded_rate` 100%).

#### UC-X.3 — Reset the database and start clean
**Actor**: developer · **Status**: ✅ works end to end

```bash
cd backend
uv run alembic downgrade base    # drops every table and enum type cleanly
uv run alembic upgrade head      # re-creates with no "already exists" error
```

**Expected**: a clean up → down → up cycle. This is regression-tested
(`tests/test_migrations.py`) against its own dedicated database, including that enum types
are dropped — leaving them behind looks like a clean downgrade right up until the next
upgrade fails.

---

## What does not work yet

Consolidated ⛔ list, with the phase that delivers each.

| Capability | Why it's absent | Delivered by |
|-----------|----------------|-------------|
| **Coach views a student** (`/players/:profileId`) — PRD J7 | Route is commented out in `app/router/index.tsx`; no flow creates a `profile_relationships` row; ADR-0012 defers cross-account viewing pending a consent model | A future phase; ADR-0012 must be resolved first |
| **Import recent games from Lichess / Chess.com** — PRD J2 | Only manual PGN paste/upload exists. Phase 8b's routing applies equally once it lands | Phase 14 |
| **MCP server** exposing analysis and retrieval tools | Tool implementations exist (`orchestration/tools/`) and are deliberately shared so an MCP surface reuses them; `app/mcp/` is still an empty package skeleton reserved at Phase 1 | Phase 12 |
| **Multi-agent supervisor with a critic agent** | Phase 10 ships a single agent with a deterministic guardrail; `orchestration/graphs/` holds only `chat.py` | Phase 13 |
| **Training-plan generation** | Training-theme mapping exists (`domain/patterns/training_map.py`) and feeds reports; no plan generator | Phase 15 |
| **6 high-difficulty motifs** (deflection, decoy, overloading, interference, zwischenzug, windmill) | Need engine corroboration to ship without misleading a learner (D-012) | Deliberate scope boundary |
| **Aggregate-level persona reports** | Phase 9 is per-game only; the dashboard is deterministic | Deferred |
| **PDF export, parent and analyst personas** | MVP scope decision (D-002) | Post-MVP |
| **Proof of account ownership at login** | ADR-0014 — username claim only | Must close before any private-data feature |

---

## Traceability — PRD journeys to real use cases

Mapping [`prd.md`](prd.md) §7's nine journeys to what exists today.

| Journey | Status | Use cases |
|---------|--------|-----------|
| **J1** — First login | ⚠️ Works, but via username claim, not Lichess OAuth2 PKCE (ADR-0014) | UC-2.1, UC-2.2, UC-2.3 |
| **J2** — Import and analyse (from a platform) | ⛔ Platform import not built; **the same downstream journey works from a PGN** | UC-9 below; UC-X.1 |
| **J3** — Single game review | ⚠️ Works; best moves shown in UCI, not SAN | UC-8a.2, UC-5.1, UC-6.3 |
| **J4** — Ask about a game | ✅ Works | UC-10.1, UC-10.3 |
| **J5** — Ask about a habit | ✅ Works | UC-10.2, UC-8.1 |
| **J6** — Switch persona | ✅ Works (per game; not over aggregates) | UC-9.1, UC-9.2, UC-9.3, UC-9.4 |
| **J7** — Coach views a student | ⛔ Not available — no linking flow, no player page | — |
| **J8** — Memory continuity | ✅ Works | UC-11.1, UC-11.2, UC-11.3 |
| **J9** — Upload a PGN | ✅ Works | UC-3.1 … UC-3.5, UC-X.1 |

**Six of nine journeys work end to end today.** J1 and J3 work with stated caveats. J2's
*ingestion* half awaits Phase 14; its analysis half is J9's path and works now. J7 is the
one journey with nothing behind it.

---

## Maintenance

Add a phase section here when that phase's report lands, following the same shape: features
table, numbered use cases with runnable steps, and a "not available yet" block carried from
the report's own known-gaps section. Update the consolidated ⛔ list and the traceability
table at the same time — a use case that silently becomes stale is worse than one that was
never written.
