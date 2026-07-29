# Phase 14 Report — Lichess and Chess.com Game Import Connectors

**Date**: 2026-07-29
**Status**: Complete, pending sign-off
**Branch**: `P14-lichess-chesscom-connectors`

## Goal

Add account-based game ingestion beyond manual upload/paste: import a profile's recent
games from its linked Lichess and Chess.com accounts.

## Scope decisions confirmed before implementation (D-030, D-031)

Two real gaps in the written plan surfaced before coding and were resolved with the
owner rather than silently reinterpreted:

1. **No OAuth token exists to reuse (D-030).** `project-plan.md`'s Phase 14 text
   assumed real Lichess OAuth2 PKCE had landed by now; ADR-0014 (Phase 2) deferred it.
   Confirmed: both connectors read each platform's **public**, unauthenticated
   game-export endpoint for the profile's already-linked username — the same trust
   level today's username-claim login already relies on, and outside ADR-0014's "before
   private data or write access" OAuth gate, since reading public games is neither.
2. **PGN, not NDJSON/structured JSON (D-031).** The plan's task list literally said
   "NDJSON stream handling for Lichess." Proposed instead and confirmed: both
   connectors fetch **PGN text** (Lichess via `Accept: application/x-chess-pgn`,
   Chess.com via the `pgn` field already in each archived game) and hand it to
   `ImportService`'s existing pipeline completely unchanged — no second parser for a
   structured game shape, per `claude.md` rule 13.

## Design

- **Connectors produce PGN; `ImportService` does everything else, unchanged.**
  `LichessGameConnector`/`ChessComGameConnector` (`app/integrations/{lichess,chesscom}/
  client.py`) both satisfy one `PlatformGameConnector` Protocol
  (`domain/imports/connectors.py`): `fetch_recent_games_pgn(username, max_games) -> str`.
  Their entire job is an HTTP fetch — zero parsing logic, zero dedup logic, zero
  canonicalization logic. Every one of those already existed in `ImportService` from
  Phase 3/4 and needed no changes to support a new source.
- **A real bug caught before it shipped: every imported game was silently tagged
  `GameSource.UPLOAD`.** `SourceText` had no field recording which platform a PGN blob
  actually came from, so `_ingest_sources` always wrote `GameSource.UPLOAD` onto every
  `Game` row regardless of source. Fixed by adding `SourceText.source: GameSource =
  GameSource.UPLOAD` (default preserves every existing manual-upload call site
  unchanged) and using it instead of the hardcoded value. Caught by design review before
  any test was written against it, then covered by an explicit assertion in the new
  dispatch tests.
- **`ImportService.ingest_into_job` is a new sibling to `ingest`, not a rewrite of it.**
  Manual paste/upload is fast enough to create its own job inline
  (`ingest`, unchanged). A platform fetch is genuinely slow and unpredictable — the
  service module's own docstring anticipated this before Phase 14 existed
  ("once Phase 9's [renumbered: Phase 14's] Lichess/Chess.com imports need real async
  work: only the call site moves from inline to a worker"). The route now creates a
  `PENDING` job immediately and returns `202`; a background task
  (`domain/imports/dispatch.py::run_platform_import_job`, mirroring
  `domain/analysis/dispatch.py`'s existing shape) fetches, then fills the same job in
  via `ingest_into_job`. The actual parse/dedupe/persist/canonicalize logic
  (`_ingest_sources`) is shared by both entry points, extracted once, not duplicated.
- **No new configuration.** `IngestionSettings.lichess_rate_limit_rps`/
  `chesscom_rate_limit_rps`/`max_games_per_import` already existed (Phase 3) and are
  reused unchanged. Window selection (10/30/60) reuses `AnalyticsSettings` — the same
  "how many recent games" concept the profile-analytics window picker already exposes,
  not a second setting for the same thing.
- **Profile-to-source linkage reuses `ProfileSource`**, already written at login
  (`AuthService.login`) — added one query, `get_profile_source(session, profile_id,
  source)`, since the existing `get_linked_usernames` flattens every platform together
  and a sync needs to know *which* platform's username to hand a connector.
- **Rate-limit backoff** (`integrations/http_retry.py::get_with_backoff`) is shared by
  both connectors: a 429 or 5xx retries up to 3 times with linear backoff
  (`attempt / rate_limit_rps` seconds) — deliberately simple, not exponential, given the
  bounded request volume (`max_games_per_import`) these syncs ever make.

## Files created or changed

Backend:

- `domain/imports/connectors.py` (new) — `PlatformGameConnector` Protocol, `ConnectorError`
- `integrations/lichess/client.py`, `integrations/chesscom/client.py` (new)
- `integrations/http_retry.py` (new) — shared backoff helper
- `domain/imports/service.py` — `SourceText.source` field; `ingest_into_job`/
  `_ingest_sources` extracted from `ingest`, which is otherwise unchanged
- `domain/imports/dispatch.py` (new) — `run_platform_import_job`, `build_platform_connector`
- `domain/profiles/queries.py` — `get_profile_source`
- `schemas/imports.py` — `PlatformSyncRequest`
- `api/routes/imports.py` — `POST /imports/{provider}/sync`

Frontend (added after the backend was reviewed, at the owner's request — see
"Frontend addition" below):

- `features/imports/api/imports.ts` — `syncFromPlatform`
- `features/imports/hooks/useImports.ts` — `useSyncFromPlatform`
- `features/imports/components/SyncFromPlatform.tsx` (new) — the sync button + window
  selector
- `features/imports/index.ts` — public exports
- `pages/ImportsPage.tsx` — renders `SyncFromPlatform` using `useCurrentUser()`'s
  `provider`/`username`, above the existing manual-upload card

## Frontend addition

Phase 14 was scoped backend-only; the owner asked, after seeing the backend tested via
Swagger, for a real UI entry point rather than API-docs-only testing. `SyncFromPlatform`
reads `provider`/`username` directly from `/api/v1/auth/me` (`useCurrentUser`) rather
than fetching a separate "linked accounts" list — MVP login links exactly one platform
per account, so there is only ever one to show. It reuses the existing `ImportJobStatus`/
`useImportJob` polling path unchanged (that hook's own docstring, written at Phase 10,
already anticipated "once Phase 9's [Phase 14's] Lichess/Chess.com imports make jobs
that genuinely take time" — this is that day).

**Verified live, not just against mocks**: ran the actual dev server (backend already
running, frontend on :3535) through a scripted Playwright session — logged in as a real
Lichess account (`DrNykterstein`), clicked **Sync from Lichess**, and confirmed:

1. The button click created a job that appeared instantly at the top of "Recent
   imports" as `Queued`.
2. Within a few seconds it reached `Done` with **10 imported · 0 duplicates · 0
   rejected** — 10 real games fetched live from Lichess's public API and ingested.
3. Running the sync a second time (fresh login session) correctly reported **0
   imported · 10 duplicates · 10 rejected**, each labelled
   `lichess:DrNykterstein (game N): duplicate game` — cross-session dedup by content
   hash, working exactly as designed.

This is the first real (non-mocked) exercise of the Lichess connector against the
actual internet this phase, and it closes the "no live smoke test" gap the backend-only
version of this report originally listed.

## Tests

45 new tests, plus the full existing hermetic suite re-run for regressions:

- **Connector tests** (`test_lichess_client.py`, `test_chesscom_client.py`, mocked
  `httpx.MockTransport`, no real network): successful fetch, 404, unexpected status,
  transport failure, 429-then-success retry (Lichess), archive-walking from most recent
  month backward until enough games are collected without over-fetching, empty archive
  list.
- **Dispatch tests** (`test_platform_import_dispatch.py`, real session factory,
  fake connector): successful sync with correct `Game.source` tagging and queued
  analysis jobs, connector failure → `FAILED` job, empty account → `DONE` with zero
  games (not a failure), too-many-games → `FAILED`, a missing job id is a defensive
  no-op, re-syncing reports a duplicate, **a malformed game alongside a valid one still
  completes with partial import** (the plan's "partial import recovery" requirement).
- **Route tests** (`test_import_routes.py`): sync on a linked provider returns `202`
  pending; syncing an unlinked provider is `404`; `upload` as a provider (a valid
  `GameSource` member, not a syncable platform) is `422`; an out-of-range window is
  `422`; an explicit valid window is accepted; unauthenticated sync is `401`.

Result: **all new tests passing**; full hermetic suite re-run confirms no regressions
from the `ImportService` refactor.

- **Frontend tests** (`SyncFromPlatform.test.tsx`, 4 new): requests a sync for the given
  provider/default window, sends the selected window when changed, calls `onSynced`
  with the pending job, shows a clear message on a 404 (no linked account). Full
  frontend suite (68 tests, up from 61) and `tsc -b`/`oxlint`/`prettier --check` all
  pass; production build (`vite build`) succeeds.

## Evaluation

Phase 14 has no LLM or chess-reasoning component, so — consistent with earlier
deterministic phases (4/5/6) — "evaluation" here means the deterministic guarantees
the plan asked for, verified by the test suite above rather than a RAGAS harness:

- **Import completeness**: the Chess.com connector's archive-walk test proves it
  collects *exactly* enough games (stopping once `max_games` is reached, never
  over-fetching a full multi-year history for a "last 10" request) and preserves
  chronological order across month boundaries. The Lichess connector delegates
  count-truncation to the platform's own `max` parameter.
- **Source failure handling quality**: covered by the connector-error, malformed-game,
  and too-many-games dispatch tests — every failure mode ends in a `FAILED` job with a
  specific `reason`, never an unhandled exception or a silently stuck `PENDING` job.

## Known gaps

- Real Lichess OAuth2 PKCE remains deferred (ADR-0014) — unaffected by this phase, since
  reading public games never needed it.
- Chess.com's planned username-verification token (ADR-0007) is not implemented; a
  profile can only sync a platform it already has a `ProfileSource` link for (created at
  login), and there is no route yet to link an additional platform after the fact.
- The live browser verification exercised Lichess only (a real, well-known account was
  on hand); Chess.com's connector has not yet had the equivalent live, non-mocked run —
  its unit coverage (archive-walking, pagination, error mapping) is solid, but the same
  "does the real API's shape still match what the tests assume" caveat applies to it
  specifically until someone runs it against a real Chess.com account.
- The frontend only ever shows one sync button (whichever platform the account logged
  in with) — consistent with the backend's own current limit (one `ProfileSource` per
  account, see above), not an independent gap.

## Recommendation

Ready for sign-off. Scope was delivered close to the original plan, with two confirmed,
documented deviations (D-030 auth model, D-031 PGN over NDJSON) and one real bug fixed
during implementation (the `GameSource.UPLOAD` mistagging) before it ever shipped. The
owner-requested frontend addition was verified end-to-end against the real, running
Lichess API in a real browser, not just against mocks.
