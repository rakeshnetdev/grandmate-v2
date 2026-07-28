# Phase 8b Report — Private Study Profiles for Unowned PGNs

**Date**: 2026-07-27
**Status**: Complete, pending sign-off
**Branch**: `P8-multi-game-aggregation` (folded into Phase 8's branch/PR at the owner's
request, rather than split into its own)

## Why this checkpoint exists

Discovered while testing Phase 8 against real data: nothing before this phase
distinguished "a game I actually played" from "a game I imported to study" — every PGN a
profile uploaded, regardless of whose game it was, counted toward that profile's own
Phase 8 aggregate metrics. A profile whose owner tested with a mix of their own games and
historical/other-players' games got a dashboard whose win rate, accuracy trend, and
recurring-weakness list were silently contaminated by games that weren't theirs.

This directly conflicted with an already-locked decision, **ADR-0012** (self dashboard
never mixes in other players' data; analysing arbitrary opponents deferred pending a
consent model), which was flagged to the owner before any code was written. See
**ADR-0016** and **D-021** for the resolution: a private, single-account "study" bucket is
a materially different, smaller case than the cross-account viewing ADR-0012 deferred,
because it is never exposed to anyone but the account that chose to import the material.

## Scope decisions confirmed before implementation

- **Full pipeline parity for the study profile** (Option A of two presented), not a
  restricted per-game-only view — the owner's explicit choice, since the value of
  studying material is in the same trend/weakness signal Phase 8 already computes.
- **Automatic, per-game routing** at import time (identity-based: does a header name
  match a linked platform username), not a manual "which dashboard" picker on upload —
  matches how the owner actually thinks about it ("any game with my username").
- **Folded into Phase 8's own branch/PR** rather than split into a separate one.

## Completed

| Deliverable | Status |
|-------------|--------|
| Every account gets a second profile (`kind = opponent`, "Study games") at first login | ✅ |
| Pre-existing accounts get one lazily, defensively, the same way `SELF` already did | ✅ |
| Per-game import routing: header match → `SELF`, no match → study profile; a single batch can split across both | ✅ |
| Ambiguous self-play (both sides match) still routes to `SELF` — only a genuine no-match routes away | ✅ |
| An account with no linked usernames at all defaults everything to `SELF` (today's pre-Phase-8b behaviour, not silently reinterpreted) | ✅ |
| Dedup, and the queued `ENGINE_ANALYSIS` job, both scoped to wherever a game actually landed — not always `SELF` | ✅ |
| `GET /api/v1/profiles` — list the caller's own profiles | ✅ |
| `profile_id` query param (ownership-checked, one shared dependency) on `games`, `analysis`, `patterns`, `analytics` | ✅ |
| Frontend "My games" / "Study games" toggle, carried via URL search param across `/games`, `/games/:id`, `/dashboard` | ✅ |
| ADR-0016 written; ADR-0012, `decisions-log.md`, `data-model.md`, `project-plan.md` updated | ✅ |
| Verified live end to end: a mixed batch (one own game, one unowned game) split correctly between profiles in a real browser session | ✅ |

## Files created or changed

**Backend**

```
backend/app/
  domain/games/normalization.py       +matches_any_linked_username
  domain/imports/service.py           ingest() re-signatured: self_profile_id/
                                        study_profile_id/self_linked_usernames replace
                                        profile_id; per-game routing + scoped dedup
  domain/auth/service.py              _create_account also creates the study profile
  domain/profiles/                    new — queries.py (list/get_owned/get_or_create_
                                        study/get_linked_usernames), __init__.py
  api/dependencies/profile_scope.py   new — ScopedProfileIdDep, shared ownership check
  api/routes/profiles.py              new — GET /profiles
  api/routes/imports.py               resolves self+study profile, passes routing inputs
  api/routes/games.py, analysis.py,
    patterns.py, analytics.py         current.profile.id -> ScopedProfileIdDep
  schemas/profiles.py                 new — ProfileSummary
backend/tests/
  test_import_service.py              _ingest helper updated (no behaviour change)
  test_import_service_profile_routing.py  new — 7 tests
  test_profiles_routes.py             new — 3 tests
  test_profile_scope_dependency.py    new — 4 tests
  test_import_routes_profile_routing.py   new — 1 HTTP-level test
  test_import_analysis_dispatch_integration.py  fixture game's White changed to match
                                        the fixture's login username (see inline comment)
```

**Frontend**

```
frontend/src/
  features/profiles/                  new — api/profiles.ts, hooks/useProfiles.ts,
                                        components/ProfileToggle.tsx(+test), index.ts
  features/games/api/games.ts         all fetches accept an optional profileId
  features/games/hooks/useGames.ts    profileId threaded into every query key
  features/games/components/
    GamesList.tsx                     +profileId prop, profile-aware game links
    GamesList.test.tsx                +1 test
  features/analytics/api/analytics.ts +profileId
  features/analytics/hooks/useAnalytics.ts  +profileId, threaded into query key
  features/analytics/components/ProfileDashboard.tsx  +profileId prop
  pages/GamesPage.tsx, DashboardPage.tsx  ProfileToggle wired via `?profile=` search param
  pages/GameDetailPage.tsx            reads `?profile=`, threads through
```

**Docs**

```
final_docs/v2/adr/0016-private-study-profile-for-unowned-pgns.md   new
final_docs/v2/adr/0012-cross-profile-viewing-permissions.md        +cross-reference note
final_docs/v2/decisions-log.md      +D-020 (Phase 8 mechanics, backfilled), +D-021
final_docs/v2/data-model.md         `profiles` section: documents the dual usage of
                                      kind=opponent
final_docs/v2/README.md             ADR index +0016
project-plan.md                     +Phase 8b section
```

## Tests

- Backend: 511 → 526 (15 new), full suite passes including the one pre-existing test
  that needed a one-line fixture fix (documented above). `mypy app` clean, `ruff
  check`/`ruff format --check` clean.
- Frontend: 46 → 51 (5 new: 4 `ProfileToggle` tests, 1 `GamesList` routing test), `tsc`,
  `oxlint`, `prettier --check` clean.

## Live verification

Logged in as a real Lichess account, imported a two-game batch (one game with that
account's own username as a header, one game between two unrelated historical players),
and confirmed via screenshots: "My games" showed only the account's own game, "Study
games" showed only the unowned one, and the same toggle worked identically on the
dashboard (URL-persisted, so it survives navigation between pages). No unexpected console
errors.

## Known gaps

- **`profiles.kind = opponent` now carries two meanings** — this study bucket, and the
  original "an observed opponent, potentially coach-viewable" sketch in `data-model.md`.
  Documented explicitly in ADR-0016 and the data model. Worth splitting into a distinct
  `STUDY` kind (additive migration) if Phase 9's `/players/:profileId` work makes the
  overlap confusing.
- **No UI to rename or manage the study profile** — MVP scope is exactly what was asked
  for (own vs. study separation), not general multi-profile management.
- Real Lichess/Chess.com bulk import (Phase 14) is unrelated to and unaffected by this
  work — routing applies equally once that phase lands.

## Recommendation

Ready for sign-off alongside Phase 8. The ADR conflict was surfaced and resolved with the
owner before implementation, not discovered after the fact; the one test that broke from
the signature change was a real regression from this change, found by running the full
suite rather than the changed files only, and fixed rather than worked around.
