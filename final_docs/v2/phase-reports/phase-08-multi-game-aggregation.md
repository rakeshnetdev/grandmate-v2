# Phase 8 Report — Multi-Game Aggregation and Profile Analytics

**Date**: 2026-07-27
**Status**: Complete, pending sign-off
**Branch**: `P8-multi-game-aggregation` (from `main`, which includes P8a)

## Goal

Move from per-game insight to player development insight: last-N-game windows, recurring
weakness detection, opening-family performance, tactical/strategic trend reports,
color/time-control segmentation, progress deltas, versioned aggregate snapshots, and a
profile dashboard UI.

## Scope decisions confirmed before implementation

Three things the plan left undefined were resolved with the owner before coding (see
conversation record; all three picked the recommended default):

1. **Recurring weakness definition** — a motif/theme that recurs, on the player's own
   side, above a configurable occurrence rate. Reuses Phase 6's existing taxonomy, no new
   categories invented.
2. **Compute trigger** — on demand, recomputed and re-persisted on every dashboard
   request rather than a background job. Aggregation only reads already-computed
   per-game data, so this is cheap.
3. **Small-sample guard** — 5 games minimum (`ANALYTICS_MIN_GAMES_FOR_TREND`) before
   trends/weaknesses are asserted rather than caveated.

## A correctness issue found during implementation, not by the owner

The "recurring weakness" definition required knowing, for each motif/theme finding,
whether it represents the player's own problem or something the player did *to* their
opponent. Reading the actual Phase 6 detectors (not just their docstrings) turned up that
this polarity is **not uniform**:

- Motifs are always recorded against the *mover's* side, but what that means differs:
  creating a fork/pin/skewer/etc. is a tactical win for the mover — so it's "the
  player's problem" when the *opponent* is the mover. `HANGING_PIECE` is the one
  exception: it's defined as the mover leaving their own piece hanging, a self-inflicted
  blunder, so there "the player's problem" means the player *is* the mover.
- Themes are recorded per side directly from what's true of that side's position, but
  not every theme is bad news: `PASSED_PAWN_CREATION`, `OPEN_FILE_CONTROL`,
  `CENTRE_CONTROL`, and `SPACE_ADVANTAGE` are achievements, not weaknesses.

Getting this backwards would have silently told a player their own successful forks were
a weakness, or missed genuine recurring vulnerabilities. `domain/analytics/metrics.py`
documents the exact polarity table with the reasoning, and the live browser check (below)
confirmed the deployed behavior against real analyzed games: `open_file_control` (an
achievement) was correctly excluded from the same game's weakness list that correctly
included `bad_bishop` and `development_lag`.

## Completed

| Deliverable | Status |
|-------------|--------|
| `GET /api/v1/analytics/profile?window={10,30,60}` | ✅ |
| `domain/analytics/metrics.py` — pure aggregation functions (outcome, time-control bucketing, opening family, classification rates, color/time-control segmentation, recurring weaknesses) | ✅ |
| `domain/analytics/service.py` — window loading (current vs. previous), delta computation, persistence | ✅ |
| `ProfileAggregateSnapshot` — versioned, one new row per computation, never updated in place | ✅ |
| `AnalyticsSettings` — window sizes, default window, min-sample threshold, weakness occurrence threshold, time-control bucket thresholds — all `.env`-configurable | ✅ |
| Frontend `analytics` feature: API client, hook, and a dashboard composed of 7 focused components (window selector, sample-size banner, stat tiles, classification table, opening-family table, color/time-control tables, weakness list) | ✅ |
| `/dashboard` page and route, nav link, home-page card | ✅ |
| Shared `shared/lib/classification.ts` — extracted from Phase 8a's `GameAnalysisView` so both features render the same 5-way move-quality scale identically | ✅ |
| Verified live end to end in a real browser against real analyzed games | ✅ |

## Files created or changed

**Backend**

```
backend/app/
  db/models/analytics.py             new — ProfileAggregateSnapshot
  db/models/__init__.py              +export
  core/config/groups.py              +AnalyticsSettings
  core/config/__init__.py, settings.py  +wiring
  domain/analytics/
    metrics.py                        new — pure aggregation functions
    service.py                        new — ProfileAnalyticsService
    __init__.py                       new
  schemas/analytics.py               new — ProfileAnalyticsSummary and its parts
  api/routes/analytics.py            new — GET /analytics/profile
  api/routes/__init__.py             +router registered
backend/alembic/versions/20260727_2136_..._profile_aggregate_snapshots.py  new migration
backend/.env.example                 +7 analytics/time-control keys
backend/tests/
  test_analytics_metrics.py          new — 26 tests
  test_analytics_service.py          new — 6 tests
  test_analytics_routes.py           new — 5 tests
final_docs/v2/configuration.md       +Profile analytics section
```

**Frontend**

```
frontend/src/
  shared/lib/classification.ts       new — shared move-quality label/color scale
  features/games/components/GameAnalysisView.tsx   refactored to use the shared module
  features/analytics/
    api/analytics.ts                  new
    hooks/useAnalytics.ts             new
    lib/format.ts, lib/constants.ts   new
    components/
      ProfileDashboard.tsx            new — composition only
      WindowSelector.tsx              new
      SampleSizeBanner.tsx            new
      StatTile.tsx                    new
      ClassificationRateTable.tsx     new
      OpeningFamilyTable.tsx          new
      ColorSegmentationTable.tsx      new
      TimeControlTable.tsx            new
      RecurringWeaknessList.tsx       new
      ProfileDashboard.test.tsx       new — 4 tests
    index.ts                          new
  pages/DashboardPage.tsx            new
  app/router/index.tsx               +/dashboard
  app/layouts/RootLayout.tsx         +nav link
  pages/HomePage.tsx                 +dashboard card, docstring fix
```

## Structure review

`ProfileDashboard.tsx` was first written as one 312-line file with 7 sub-components
inline — over the line where "small and composable" stops being true, per the phase-gate
structure-review requirement. Split into one file per table/section before sign-off;
`ProfileDashboard.tsx` is now composition-only (~90 lines).

## Tests

- Backend: 474 → 511 (37 new: 26 metrics unit tests, 6 service integration tests against
  a real transactional Postgres session, 5 HTTP route tests), `mypy app` clean, `ruff
  check`/`ruff format --check` clean.
- Frontend: 42 → 46 (4 new dashboard tests: empty state, populated state, sample-size
  banner, window-switch re-fetch), `tsc`, `oxlint`, `prettier --check` clean.

## Live verification

Ran the real stack (existing dev Postgres, backend, Vite dev server) and drove it with
Playwright against the profile's already-analyzed games from the Phase 8a session: logged
in, opened `/dashboard`, confirmed the sample-size banner appeared correctly (2 analyzed
games, below the 5-game threshold), and confirmed every section rendered real, internally
consistent numbers — 98.7% accuracy, a classification-rate table summing to 100%, a
correctly-identified Ruy Lopez family with 1-0-0 record, and (the load-bearing check) a
recurring-weakness list containing `development_lag` and `bad_bishop` while correctly
*excluding* `open_file_control`, which the same underlying game's Phase 6 findings also
contained. Clicking "Last 30" re-rendered with that button highlighted and a fresh
request. Console had only the expected pre-login 401 probe — no unhandled errors.

## Known gaps

- **`TimeControl` header is rarely present** in manually uploaded/pasted PGNs, so the
  time-control segmentation table will mostly show "Unknown" until Lichess/Chess.com
  imports (Phase 9) start supplying real values. The bucketing logic itself is tested and
  correct.
- **No snapshot-history endpoint.** Each request recomputes and persists a new version,
  but nothing yet reads *past* versions — "progress deltas" are current-window-vs.
  -previous-window computed fresh each time, not a comparison across historical
  dashboard views. Versioned storage exists specifically so this is additive later, not a
  redesign.
- **Deferred to Phase 9+, not a gap in this phase's scope**: no LLM narrative over the
  aggregate data, no RAG involvement — same deterministic-only boundary as Phase 8a.

## Recommendation

Ready for sign-off. The polarity bug (caught before it ever reached a user) and the
file-size split are exactly what live verification and the structure-review step exist
to catch — both are documented above rather than quietly fixed and left unmentioned.
