# Phase 5 Report — Engine Analysis Core

**Date**: 2026-07-26/27
**Status**: Complete, pending sign-off

## Scope note

Two decisions were proposed and confirmed with the owner before coding, after
benchmarking real Stockfish timing on this machine (recorded as D-019 in
`decisions-log.md`):

- **Trigger**: unlike Phases 3–4 (synchronous, inline), engine analysis runs as an
  automatic background job. Benchmarked at ~7s/game (shallow sweep at `ENGINE_DEPTH`
  plus a deep pass on critical moments at `ENGINE_DEEP_DEPTH`), inline processing would
  turn a sub-second import request into minutes for a full batch. `ImportService` queues
  a `pending ENGINE_ANALYSIS` job per canonicalized game; the route dispatches it via
  `BackgroundTasks` after the response is sent.
- **Concurrency**: bounded, not sequential. `ENGINE_MAX_CONCURRENT_GAMES` (default 4)
  caps how many games analyse at once, each in its own single-threaded Stockfish
  process. Cuts a 60-game batch's background completion time from ~7 minutes sequential
  to ~1.75 minutes.

## Completed

| Deliverable | Status |
|-------------|--------|
| Stockfish UCI adapter behind an `EngineAdapter` interface, async (not blocking) | ✅ |
| Tiered analysis policy: shallow sweep every ply, deep pass on critical moments only | ✅ |
| Move evaluations, principal variations, mate-score handling | ✅ |
| Five-category move classification (best/good/inaccuracy/mistake/blunder) | ✅ |
| Critical moment extraction, deep re-analysis, correct swing propagation to both neighbouring plies | ✅ |
| `game_analysis` + `move_evaluations` tables, versioned per analysis run | ✅ |
| Background dispatch: bounded concurrency, per-job DB session, status tracking | ✅ |
| Job-level failure/timeout handling (marked `FAILED`, batch continues) | ✅ |
| Manual retry (`POST /analysis/games/{id}/retry`) | ✅ |
| Polling API: job status, completed analysis results | ✅ |
| Two real bugs found and fixed during this phase (see below) | ✅ |

## Files created or changed

**Backend**

```
backend/
  alembic/versions/..._engine_analysis.py     game_analysis, move_evaluations, jobs.game_id,
                                               job_kind enum widened (reversible rename/recreate)
  app/
    core/config/groups.py                     +engine_max_concurrent_games
    db/models/analysis.py                     GameAnalysis, MoveClassification, MoveEvaluation
    db/models/imports.py                      +Job.game_id, JobKind.ENGINE_ANALYSIS
    db/models/games.py                        disambiguated FK (games.job_id vs jobs.game_id)
    integrations/engine/
      base.py                                 EngineAdapter protocol, EngineEvaluation
      stockfish.py                            async adapter; transport lifecycle fix (see below)
    domain/analysis/
      classification.py                       compute_cpl, classify_move
      service.py                              AnalysisService: tiered policy orchestration
      dispatch.py                             run_pending_analysis_jobs: bounded concurrency
      queries.py                              job/result lookups, manual retry
    api/routes/analysis.py                    job polling, results, retry
    schemas/analysis.py                       response schemas
  .env.example, configuration.md              ENGINE_MAX_CONCURRENT_GAMES
  tests/
    test_analysis_classification.py           10 tests — CPL, five-category boundaries
    test_engine_stockfish.py                  9 tests — real Stockfish, mate detection,
                                               timeout, legal-line validation, reproducibility
    test_analysis_service.py                  6 tests — tiered policy, persistence, summary
    test_analysis_dispatch.py                 6 tests — concurrency, status, timeout, retry
    test_analysis_routes.py                   7 tests — HTTP contract, profile scoping
```

**Docs**: `data-model.md` (`game_analysis`/`move_evaluations`/`jobs.game_id` documented),
`decisions-log.md` (D-019), `changes/0001-reuse-ledger.md` (engine/classify/pipeline
reuse), this report.

## Test results

```
257 passed (38 new: 10 classification + 9 engine + 6 service + 6 dispatch + 7 routes)
  ruff check    All checks passed!
  ruff format   clean
  mypy (strict) Success: no issues found in 80 source files
```

## Scope note: test coverage ran ahead of MVP need

This phase's test count grew larger than the phase itself warranted — property-style
coverage and a full concurrency/timeout/retry matrix for dispatch, on top of the
adapter/classification/service layers. The owner flagged this mid-phase. `CLAUDE.md` now
has an explicit MVP-scope-discipline rule in its Testing Requirements section as a result:
coverage proportionate to what a phase's own scope calls for, not exhaustive permutation
coverage, and a rising test count is a signal to check whether *scope* crept, not a
reason to add more tests. Recorded here so the next phase starts from that rule already
in force, not from this phase's pace.

## Three bugs found and fixed during this phase

**1. Unclosed Stockfish subprocess transport.** `StockfishEngine.start()` discarded the
`asyncio.SubprocessTransport` returned by `chess.engine.popen_uci()`, keeping only the
protocol. `quit()` correctly sent the UCI `quit` command and awaited the process exiting,
but never closed the transport itself — the underlying pipes were left for the garbage
collector, which raises `ResourceWarning` (a hard test failure under this project's
`filterwarnings=error`) at an unpredictable later time. Found via
`tests/test_engine_stockfish.py`. Fixed by storing and explicitly closing the transport,
with a timeout around `protocol.quit()` so a wedged process (e.g. after a timed-out
analysis) can't block shutdown indefinitely.

**2. `deep_analyzed` only credited one side of a deepened swing.** A critical ply's
`eval_swing_cp` is computed from *both* its `eval_before` and `eval_after` positions —
when the "after" position gets deepened, that deepened value feeds the critical ply's own
CPL calculation just as much as it feeds the *next* ply's `eval_before`. The first
implementation only flagged the next ply as `deep_analyzed`, leaving the critical ply
itself flagged `False` despite its stored swing reflecting the deepened value — an
inconsistency between what a row claimed and what it actually contained. Found via
`tests/test_analysis_service.py`'s deep-pass test. Fixed: `deep_analyzed` for ply *i* is
now true if either position *i* or position *i+1* was deepened.

**3. Dispatch tests leaked committed rows into the shared test database.**
`test_analysis_dispatch.py` deliberately commits for real (it has to — it's testing that
`run_pending_analysis_jobs` sees data through a separate connection, the same as it does
in production; the rollback-wrapped `db_session` fixture can't exercise that). Without
teardown, those rows outlived the test and broke unrelated, later-running tests
(`test_import_service.py`, `test_models_imports.py`) whose assertions were shaped like
"select every row of X, expect exactly what this test made." Fixed by deleting all `User`
rows (cascading away everything else) at the end of the `session_factory` fixture, and,
as a second line of defence, changed the one `test_analysis_service.py` assertion that
queried unfiltered to filter by its own `analysis.id` instead of relying on the rest of
the suite never leaving stray rows behind.

## A verified, non-obvious engine nuance

`ENGINE_THREADS=1`'s determinism guarantee (documented since Phase 1) holds between
**independent, freshly-started** engine processes — which is what every analysis job
actually gets. It does **not** extend to re-querying the identical position twice on one
already-warm engine: the hash table carries state between calls, and a repeat query can
return a slightly different eval/PV as a result. Verified directly (two fresh engines
analysing the same position agree exactly; one engine queried twice does not) and
documented in both `EngineSettings`'s docstring and
`tests/test_engine_stockfish.py::test_independent_engine_instances_agree_at_the_same_depth`.

## Evaluation

| Criterion | Result |
|-----------|--------|
| Legal line validation | `best_move_uci` and every move in `pv` verified to be legal from the position given (`test_best_move_is_legal`, `test_pv_is_a_fully_legal_line`) |
| Classification stability across repeated runs | Holds between independent engine instances (see nuance above); verified exactly equal, not approximately |
| Throughput / cost per game | Depth 12 (shallow, every ply): ~46ms/position average. Depth 18 (deep pass, critical moments only): ~1.06s/position average. A ~40-ply game: ~7s total (shallow sweep + a handful of deep passes). No LLM/API cost — Stockfish runs locally |
| Concurrency benefit | 60-game batch: ~7 minutes sequential vs ~1.75 minutes at `ENGINE_MAX_CONCURRENT_GAMES=4`, entirely in the background — the import response itself stays sub-second either way |

## Decisions honoured

| Decision | How |
|----------|-----|
| D-010 (engine analysis budget) | `ENGINE_DEPTH=12` baseline, tiered deep pass on critical moments, thresholds all read from config |
| D-019 (this phase) | Background trigger, bounded concurrency — see Scope note |
| Rule 8 (deterministic core separate from LLM layer) | `domain/analysis` imports nothing LLM-related; layer-boundary check passes |
| D-008 no hardcoded values | `ENGINE_MAX_CONCURRENT_GAMES` added to `.env.example`; no magic numbers in classification (thresholds from `EngineSettings`) |

## Deviations from plan

1. **Background dispatch instead of inline processing** — the plan's tiered-policy wording
   didn't specify synchronous vs asynchronous; benchmarking made the choice necessary and
   it was confirmed with the owner before coding, not decided silently.
2. **Bounded concurrency (`ENGINE_MAX_CONCURRENT_GAMES`)** — a new config value beyond the
   original `EngineSettings` sketch, confirmed with the owner (see D-019).

## Known gaps

| Gap | Resolution |
|-----|-----------|
| No frontend for viewing analysis results | Out of Phase 5's scope per `project-plan.md` — Phase 5 has no UI tasks listed; analysis results get a UI in later phases (opening/tactics/strategy tags land first, per the plan's phase ordering) |
| Previously imported games (Phases 3–4) are not retroactively analysed | No backfill job exists yet — only games imported *after* this phase ships get an analysis job queued automatically. A manual retry per game works via the new endpoint; a bulk backfill was judged out of MVP scope |
| Accuracy formula in `summary` is a simple documented proxy (share of best/good moves), not a claim to match any commercial product's formula | Explicit in the code comment; revisit if a more principled formula is needed later |
| No automatic retry/backoff on transient failures | A failed job is visible and retryable via the manual endpoint; automatic retry-with-backoff was judged unnecessary infrastructure for MVP scale |

## Risks

| Risk | Status |
|------|--------|
| Engine determinism | Verified precisely for the case that matters (fresh engine per job); the warm-engine caveat is documented so it isn't rediscovered as a "flaky test" later |
| Background job failure silently losing work | Mitigated: every failure is recorded on its own job row with a reason, batch continues, manual retry exists |
| R-12 schema/architecture tangle | `domain/analysis` has no import of `api/routes`; `jobs.game_id` / `games.job_id` circular FK is handled correctly by SQLAlchemy (both nullable) — verified via `create_all()` and full migration up/down/repeat cycles, despite a benign `SAWarning` from Alembic's autogenerate comparison tooling |

## Structure review

Largest new file is `app/domain/analysis/service.py` at 141 lines — the tiered policy
(shallow sweep, critical detection, deep pass, persistence, summary) for one game, one
cohesive responsibility. No file is taking on multiple concerns; no refactor needed
before sign-off.

## How to test this phase

**API — import a game and check its analysis (background job, so poll):**

```bash
curl -c cookies.txt -X POST localhost:7575/api/v1/auth/login \
  -d '{"provider":"lichess","username":"DrNykterstein"}' -H 'Content-Type: application/json'

curl -b cookies.txt -X POST localhost:7575/api/v1/imports \
  -F 'pgn_text=[Event "Test"]
[White "DrNykterstein"]
[Black "Hikaru"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0'
# -> 201; note the game id via psql (no games-list route yet, same gap as Phase 4)

GAME_ID=$(docker compose exec -T postgres psql -U grandmate -d grandmate -tA -c \
  "SELECT id FROM games ORDER BY created_at DESC LIMIT 1;")

# Poll until the background job finishes (~1-2s for a 5-ply game)
curl -b cookies.txt "localhost:7575/api/v1/analysis/games/$GAME_ID"
# -> 404 while pending, then 200 with per-ply eval/classification once done
```

**Retry:**

```bash
curl -b cookies.txt -X POST "localhost:7575/api/v1/analysis/games/$GAME_ID/retry"
# -> 201, a new pending job — GameAnalysis is versioned, so this adds a run rather than
#    overwriting the last one
```

**Tests:**

```bash
cd backend
uv run pytest tests/test_analysis_classification.py tests/test_engine_stockfish.py \
  tests/test_analysis_service.py tests/test_analysis_dispatch.py tests/test_analysis_routes.py -v
# -> 38 passed
```

**Migration reversibility (includes the job_kind enum widening):**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1   # drops game_analysis/move_evaluations, narrows job_kind back
uv run alembic upgrade head   # re-creates with no "already exists" error
```

## Recommendation

**Ready for sign-off.** Deterministic engine analysis is trustworthy for downstream use:
legal lines verified, classifications reproducible across independent runs, tiered depth
policy correctly propagates deepened evaluations to both plies it affects, and background
dispatch handles failure/timeout/retry without ever blocking an import response.

**Phase 6 preview** — opening detection and chess intelligence tags: EPD-based opening
lookup against the Lichess dataset, tactical motif and strategic theme detectors reading
the `game_moves`/`move_evaluations` this phase and Phase 4 produce.
