# Phase 3 Report — Ingestion MVP (Single PGN + Batch Upload)

**Date**: 2026-07-26
**Status**: Complete, pending sign-off

## Scope note

Three implementation defaults were proposed and confirmed with the owner before coding,
recorded as D-018 in `decisions-log.md`:

- **Job processing**: in-process, DB-backed (`jobs` table), not a Redis-backed queue.
  Phase 3 processes synchronously within the request — parsing a handful of games is
  sub-second — but the `jobs` table and polling endpoint are real, so Phase 9's
  Lichess/Chess.com imports (which will genuinely need async work) are additive, not a
  schema change.
- **Batch semantics**: one endpoint accepts pasted text, one file, or many files
  together, and any file may itself contain one game or many concatenated games. A
  single-game upload is the N=1 case of this path, not a separate mode, per the owner's
  explicit instruction.
- **Dedup key**: sha256 over normalised movetext + result + players + date, scoped to
  `(profile_id, content_hash)` — catches the same game re-exported with different
  comments/clock annotations, which a raw-text hash would miss.

`jobs` and `games` are the tables already sketched in `data-model.md`'s "Operations" and
"Games and analysis" sections — this phase implements that draft rather than inventing
parallel structures, with two small additions documented there: a `job_id` FK on `games`
for traceability, and `raw_pgn_path` pointing at the local `StorageBackend` (Supabase
remains deferred, ADR-0015).

## Completed

| Deliverable | Status |
|-------------|--------|
| `jobs` table: generic job tracking, `kind` discriminator, reusable by later phases | ✅ |
| `games` table: profile-scoped, deduplicated, `job_id` traceability | ✅ |
| Alembic migration, reversible (upgrade/downgrade/repeat tested) | ✅ |
| PGN header + mainline-move parsing (`python-chess`), structured rejection reasons | ✅ |
| Dedup: sha256(moves + result + players + date), per-profile scoped | ✅ |
| `ImportService`: parse → dedup → store → job status, one game's failure doesn't sink the batch | ✅ |
| Raw PGN persistence via the existing `StorageBackend` (local adapter) | ✅ |
| Routes: `POST /imports`, `GET /imports/{id}`, `GET /imports` | ✅ |
| Frontend: `imports` feature (api, hooks, `UploadForm`, `ImportJobStatus`) | ✅ |
| Frontend: `/imports` route, `HomePage` link, login-gated page state | ✅ |
| `Textarea` shared UI primitive | ✅ |
| API client extended to support multipart/`FormData` bodies (file upload) | ✅ |

## Files created or changed

**Backend**

```
backend/
  alembic/versions/..._imports_baseline.py   jobs + games tables, enum cleanup on downgrade
  app/
    db/models/imports.py                     Job, JobKind, JobStatus, Game, GameColor
    domain/imports/
      parsing.py                             PGN parse/validate, content-hash, rejection taxonomy
      service.py                             ImportService: orchestration, dedup, job lifecycle
    integrations/storage/ (no change)         wired into app.state for the first time
    api/
      dependencies/storage.py                StorageDep
      routes/imports.py                      POST/GET routes
    schemas/imports.py                       JobSummary, JobProgress, RejectedGameSummary
    main.py                                  app.state.storage wired in lifespan
    api/routes/__init__.py                   imports router registered
  pyproject.toml                             +python-chess, +python-multipart
  app/integrations/platforms.py              transport-error fix (see Bug section)
  tests/
    test_models_imports.py                   7 tests — constraints, cascade behaviour
    test_import_parsing.py                   12 tests — valid/malformed/batch parsing, hashing
    test_import_service.py                   8 tests — dedup, storage, job status, per-profile scoping
    test_import_routes.py                    10 tests — HTTP-level create/get/list, auth, errors
    test_platforms.py                        7 tests — PlatformClient, including the transport-error regression
    test_migrations.py                       extended EXPECTED_TABLES/EXPECTED_ENUMS
```

**Frontend**

```
frontend/src/
  features/imports/
    api/imports.ts                           Zod schemas, createImport/fetchImportJob(s)
    hooks/useImports.ts                       useCreateImport, useImportJob (polls to terminal), useImportJobs
    components/UploadForm.tsx                 paste + multi-file upload, single code path
    components/UploadForm.test.tsx            4 tests
    components/ImportJobStatus.tsx            status, counts, per-game rejection reasons
    components/ImportJobStatus.test.tsx       3 tests
    index.ts                                  feature public surface
  pages/ImportsPage.tsx                       upload + recent-imports list, login-gated
  pages/HomePage.tsx                          "Next" card now links to /imports
  app/router/index.tsx                        /imports route
  shared/components/ui/textarea.tsx           new primitive
  shared/lib/api-client.ts                    FormData support (no forced JSON header/stringify)
```

**Docs**: `data-model.md` (`jobs`/`games` marked implemented, deviations noted),
`decisions-log.md` (D-018), this report.

## Test results

```
Backend:   179 passed, 1 skipped (44 new: 7 model + 12 parsing + 8 service + 10 route + 7 platform)
  ruff check    All checks passed!
  ruff format   clean
  mypy (strict) Success: no issues found in 65 source files

Frontend:  37 passed (9 files, 7 new: 4 UploadForm + 3 ImportJobStatus)
  oxlint          clean
  prettier        clean
  tsc -b          clean
```

The one skipped backend test is the layer-boundary parametrised check — still empty until
the deterministic core lands in Phase 4+, unchanged since Phase 1.

## Bug found and fixed during the phase

**A network failure reaching Lichess/Chess.com produced an unhandled 500 that the browser
reported as a CORS error, masking the real cause.** `PlatformClient._get()`
(`app/integrations/platforms.py`, written in Phase 2) made raw `httpx` calls with no
handling for transport-level failures — DNS failure, connection refused, timeout. Any such
failure raised a bare `httpx.HTTPError`, not the `PlatformError` the login route already
knows how to catch and turn into a clean `502`. It fell through as an unhandled exception,
and FastAPI's error-response path doesn't get a chance to attach CORS headers to a 500 —
so the browser showed "blocked by CORS policy" instead of the actual network failure.

Found while smoke-testing the login flow after this phase's other changes, when a login
attempt failed with exactly that symptom. Fixed by catching `httpx.HTTPError` in `_get()`
and wrapping it as `PlatformError`. `tests/test_platforms.py` is new — this module had no
direct test coverage before (auth tests only ever monkeypatched `fetch_user` wholesale) —
7 tests including the exact regression (`test_raises_platform_error_on_a_transport_failure`).

Pre-existing from Phase 2, not introduced by this phase's ingestion work; fixed here
because it actively blocked manual verification of the login flow this phase depends on.

## How to test this phase

**API — paste a PGN and get a job back:**

```bash
# 1. Log in first (creates the session cookie + self profile)
curl -c cookies.txt -X POST localhost:7575/api/v1/auth/login \
  -d '{"provider":"lichess","username":"DrNykterstein"}' \
  -H 'Content-Type: application/json'

# 2. Paste a real short PGN
curl -b cookies.txt -X POST localhost:7575/api/v1/imports \
  -F 'pgn_text=[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0'
# -> 201, {"status":"done","progress":{"total":1,"imported":1,"duplicates":0,"rejected":[]},...}

# 3. Re-submit the exact same PGN — dedup should catch it
curl -b cookies.txt -X POST localhost:7575/api/v1/imports \
  -F 'pgn_text=[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0'
# -> 201, {"status":"done","progress":{"total":1,"imported":0,"duplicates":1,...}}

# 4. Poll the job by id (id comes from step 2's response)
curl -b cookies.txt localhost:7575/api/v1/imports/<job-id-from-step-2>
```

**API — a malformed game is reported, not a 500:**

```bash
curl -b cookies.txt -X POST localhost:7575/api/v1/imports \
  -F 'pgn_text=[White "A"]
[Black "B"]
[Result "1-0"]

1. e4 e5 2. Qxd8 1-0'
# -> 201 (not an error), progress.rejected[0].reason == "malformed_pgn"
```

**UI — upload flow end to end:**

```
1. docker compose up -d postgres
2. cd backend && uv run python -m app
3. cd frontend && npm run dev
4. Open http://localhost:3535/login, log in with any real Lichess username
   (e.g. "DrNykterstein")
5. Go to http://localhost:3535/imports
6. Paste:
     [Event "Test"]
     [White "Alice"]
     [Black "Bob"]
     [Result "1-0"]

     1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0
7. Click "Import games"
8. Expect: status turns "Done", showing "1 imported · 0 duplicates · 0 rejected"
9. Resize the browser to ~375px wide — page should reflow with no horizontal scrollbar
10. Toggle the OS/browser color scheme to dark — colors should invert via the existing
    token system, no unreadable text
```

**Migration — reversibility:**

```bash
cd backend
uv run alembic upgrade head      # -> creates jobs, games tables
uv run alembic downgrade -1      # -> drops them cleanly, including job_kind/job_status/game_color enums
uv run alembic upgrade head      # -> re-creates with no "already exists" error
```

## Environment note (not a code defect)

The backend `.venv` and a couple of its dependency dist-info directories had been silently
duplicated by a filesystem sync tool (`pytest 2`, `pytest_cov 2`, `ruff-0.16.0 2.dist-info`
alongside the real ones), which broke `pytest` entirely. `.venv` is gitignored and fully
disposable, so it was deleted and rebuilt with `uv sync` rather than patched — confirmed
clean afterward. Unrelated to this phase's code; noted here only because it blocked the
first test run.

## Verification performed

Beyond the suites, the full stack was run end to end — backend against real local
Postgres, frontend dev server, both talking to each other — driven headlessly
(Playwright/Chromium, installed temporarily for this check and removed afterward):

- Logged in with a real Lichess account (`DrNykterstein`), navigated to `/imports`.
- Pasted a valid PGN, submitted, and confirmed the job reached **Done** with
  `1 imported · 0 duplicates · 0 rejected` displayed in the UI.
- Confirmed the same behaviour and correct token-based colour rendering in both **light**
  and **dark** colour schemes (`prefers-color-scheme` — no toggle exists yet, none was
  needed for this check).
- Confirmed the page at a 375px mobile viewport: no horizontal overflow
  (`scrollWidth === clientWidth`), status row wraps cleanly instead of cramping.
- Checked the browser console: no errors beyond the expected 401 from the
  not-yet-authenticated `/auth/me` probe before login — the same pattern already noted in
  the Phase 2 report.

## Decisions honoured

| Decision | How |
|----------|-----|
| D-008 no hardcoded values | `MAX_PGN_UPLOAD_MB`, `MAX_GAMES_PER_IMPORT` from `.env` (already existed, first real consumer) |
| D-018 (this phase) | Job mechanics, batch semantics, dedup key — see Scope note |
| Rule 13 (one implementation per capability) | `jobs` table generic across phases; `StorageBackend` reused, not re-implemented |
| ADR-0015 (Supabase deferred) | Raw PGNs go through the existing local `StorageBackend`, not literal Supabase Storage |

## Deviations from plan

1. **"Raw game persistence in Supabase Storage"** (project-plan.md's literal wording) —
   implemented against the local `StorageBackend` adapter instead, per the already-locked
   ADR-0015 deferral. Not a new deviation, just this phase's instance of the Phase 2 one.
2. **Synchronous job processing** — the plan says "job queue for parsing"; Phase 3
   processes inline within the request rather than via a background task. Still DB-backed,
   still no new infra, still the same API contract job-status polling depends on. Recorded
   in D-018 rather than left implicit.

## Known gaps

| Gap | Resolution |
|-----|-----------|
| `focus_color` / `opponent_name` are nullable and unpopulated | Deliberate — determining the focus player is Phase 4's header-normalisation policy, not raw ingestion. Columns laid down now per the Phase 2 precedent (`ProfileRelationship`) |
| No move-list/FEN persistence yet | Phase 4 scope by design (`python-chess parsing pipeline`, `FEN and EPD reconstruction`) — Phase 3 only reads headers and mainline moves transiently for validation and hashing |
| Rejected games are not separately downloadable/re-uploadable | Not required by Phase 3's exit criteria; the per-game reason and detail are visible in the job's `progress`, which is enough to fix and re-submit |
| No E2E test suite checked into the repo | Verified manually via a temporary Playwright script (see Verification), consistent with the Phase 2 precedent of not committing an E2E framework until more user-visible flows exist |
| `idempotency_key` on `jobs` is unused | Reserved column for Phase 9, per the generic-jobs-table design; no code reads or writes it yet |
| **No way to see the games you've imported** — no `GET /games`, no "my games" page. `/imports` only shows job-level counts (imported/duplicates/rejected), not the games themselves | By design, not an oversight — raised by the owner during review. `imports` and `games` are separate frontend modules per `project-plan.md`'s module breakdown; a game list needs the canonical game object (opponent, result, opening, moves) that only exists from Phase 4 onward. Building a list now would mean showing raw JSON headers or writing throwaway parsing Phase 4 immediately replaces |

## Risks

| Risk | Status |
|------|--------|
| Dedup false-negatives across sources | Mitigated: hash ignores comments/clock annotations; still content-based, not semantic — a PGN with a transposed move order would not be caught. Acceptable for MVP, worth flagging if it becomes a real complaint |
| Synchronous processing on a large paste/upload blocking the request | Bounded by `MAX_GAMES_PER_IMPORT` (default 60), checked before any writes — an oversized submission fails fast with no partial import |
| R-12 schema/architecture tangle | Continues to be mitigated: `domain/imports` has no import of `api/routes`; routes stay thin and delegate to `ImportService` |

## Structure review

Largest new backend file is `app/domain/imports/service.py` at 166 lines — parsing
orchestration, dedup, storage, and job lifecycle for one clear responsibility (ingest one
submission). Largest frontend file is `UploadForm.tsx` at 114 lines — form state, submit,
and error mapping, single responsibility. No file is taking on multiple concerns; no
refactor needed before sign-off.

## Recommendation

**Ready for sign-off.** Manual PGN/paste/batch ingestion is stable, deduplicated, and
visible through job status, with the generic `jobs` table positioned to carry Phase 5 and
Phase 9's job-tracking needs without a redesign.

**Phase 4 preview** — parsing and canonical game object: full `python-chess` move replay,
per-ply FEN/EPD persistence, and the header-normalisation policy that will finally
populate `focus_color`/`opponent_name` on the games this phase already ingested.
