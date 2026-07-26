# Phase 2 Report — Local Postgres Foundation and Identity

**Date**: 2026-07-26
**Status**: Complete, pending sign-off

## Scope note

The owner asked for a **minimal** Phase 2: skip the Supabase local stack, keep plain
local Postgres, and ship a simple login usable with a Lichess or Chess.com account. Two
deviations from the original plan follow from that, both explicitly confirmed with the
owner before implementation and documented as ADRs rather than made silently:

- **Supabase deferred**, not adopted, for MVP — [ADR-0015](../adr/0015-postgres-for-mvp-supabase-deferred.md).
- **Real Lichess OAuth2 PKCE deferred** in favour of simple username-claim login for
  both platforms — [ADR-0014](../adr/0014-simple-username-claim-login-for-mvp.md). This
  narrows ADR-0007's original asymmetry (Lichess as OAuth login, Chess.com as link-only):
  for now, neither path proves account ownership, so both go through the same code path.
  **This is a real, accepted security gap** — anyone can log in as any username that
  exists on either platform — acceptable only because MVP analyses public games and
  holds nothing private yet.

## Completed

| Deliverable | Status |
|-------------|--------|
| Plain Postgres 17 + pgvector, single container, port 5433 | ✅ |
| `StorageBackend` interface with a local filesystem implementation | ✅ |
| SQLAlchemy models: `User`, `UserIdentity`, `Profile`, `ProfileSource`, `ProfileRelationship`, `AuditEvent` | ✅ |
| Alembic migration baseline, reversible (upgrade/downgrade/repeat tested) | ✅ |
| `PlatformClient`: existence lookup against Lichess and Chess.com public APIs | ✅ |
| `AuthService`: login, account bootstrap, current-user resolution | ✅ |
| Signed session JWT in an httpOnly cookie | ✅ |
| Routes: `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` | ✅ |
| Frontend: `auth` feature (api, hooks, `LoginForm`, `UserMenu`) | ✅ |
| Frontend: `/login` route, header auth state, personalised home page | ✅ |
| ADR-0014 (login simplification) and ADR-0015 (Supabase deferral, already landed) | ✅ |
| Fixed: test suite was silently wiping the dev database on every run | ✅ |

## Files created or changed

**Backend**

```
backend/
  alembic.ini, alembic/env.py, alembic/versions/..._identity_baseline.py
  app/
    db/base.py                       declarative base, naming convention, pg_enum helper
    db/session.py                    async engine/session factory, session_scope
    db/models/{identity,audit}.py    User, UserIdentity, Profile, ProfileSource,
                                      ProfileRelationship, AuditEvent
    domain/auth/service.py           AuthService: login, current(), account bootstrap
    domain/auth/session.py           signed session JWT issue/read
    integrations/platforms.py        PlatformClient: Lichess + Chess.com existence lookup
    integrations/storage/{base,local}.py
    schemas/auth.py                  LoginRequest, CurrentUser, ProfileSummary
    api/dependencies/{db,auth}.py    DbSessionDep, CurrentLoginDep
    api/routes/auth.py               /auth/login, /auth/me, /auth/logout
    main.py                          db engine/session factory wired into app lifespan
    core/config/groups.py            IdentitySettings simplified to session-only (ADR-0014)
  tests/
    test_models_identity.py          constraint tests (unique identity, cascade deletes, ...)
    test_migrations.py               upgrade/downgrade/repeat, enum values, no pending diff
    test_auth_service.py             15 unit tests, PlatformClient faked
    test_auth_routes.py              HTTP-level login/me/logout, real DB, faked platform
    db_fixtures.py                   fixed to use a dedicated grandmate_test database
```

**Frontend**

```
frontend/src/
  features/auth/
    api/auth.ts                      Zod schemas, fetchCurrentUser/login/logout
    hooks/useAuth.ts                 useCurrentUser, useLogin, useLogout
    components/LoginForm.tsx         provider toggle + username field
    components/UserMenu.tsx          header auth state
  pages/LoginPage.tsx
  shared/components/ui/input.tsx     new primitive
  app/layouts/RootLayout.tsx         UserMenu wired into header
  app/router/index.tsx               /login route
  pages/HomePage.tsx                 personalised greeting when logged in
  shared/config/env.ts               VITE_LICHESS_* removed (ADR-0014)
```

**Docs**: `ADR-0014` (new), `ADR-0007` status updated to point at it, `decisions-log.md`
D-003 updated, `configuration.md` Identity section updated, both `.env.example` files
updated.

## Test results

```
Backend:   135 passed, 1 skipped (0.99s → 28s including a real Postgres)
  ruff check    All checks passed!
  ruff format   clean
  mypy (strict) Success: no issues found in 58 source files

Frontend:  30 passed (7 files)
  oxlint          clean
  prettier        clean
  tsc -b          clean
```

The one skipped backend test is the layer-boundary parametrised check — still empty until
the deterministic core lands in Phase 4+, same as Phase 1.

## Bug found and fixed during the phase

**The test suite was silently destroying the local dev database.** `db_schema`
(`tests/db_fixtures.py`) is a session-scoped fixture that does
`Base.metadata.drop_all(engine)` / `create_all(engine)` at the start of a test session and
`drop_all` again at the end, so tests always run against a clean schema. It had no
`TEST_DATABASE_URL` set anywhere, so it fell back to `DEFAULT_DATABASE_URL` — the same
database the app itself connects to in development.

That meant every `pytest` run wiped every table in the developer's actual database at
teardown. It went unnoticed because `alembic_version` is not part of `Base.metadata`, so
`drop_all` never touches it — the migration bookkeeping table kept claiming the schema was
current while every table under it was gone. Caught while smoke-testing the login flow
against the real dev database after `alembic upgrade head` reported nothing to do, and
`\dt` showed only `alembic_version`.

Fixed by giving tests their own database (`grandmate_test`, same server, different name),
created automatically on first use via a maintenance-database connection so a fresh
checkout needs no manual setup step. Verified by running the full suite twice and
confirming `grandmate` (dev) and `grandmate_test` diverge as expected — dev keeps its
tables, test's are torn down.

## Verification performed

Beyond the suites, the full stack was run end to end — backend (`uv run python -m app`)
against real local Postgres, frontend dev server, both talking to each other:

```
$ curl localhost:7575/health
{"status":"ok","service":"grandmate-backend","version":"0.1.0"}

$ curl -c cookies.txt -X POST localhost:7575/api/v1/auth/login \
    -d '{"provider":"lichess","username":"DrNykterstein"}'
{"id":"...","provider":"lichess","username":"DrNykterstein","verified":false,
 "profile":{"id":"...","display_name":"DrNykterstein","kind":"self", ...}}

$ curl -b cookies.txt localhost:7575/api/v1/auth/me   # 200, same identity
$ curl -X POST -d '{"provider":"lichess","username":"nonexistent-zzz"}' ...  # 404
$ curl -b cookies.txt -X POST localhost:7575/api/v1/auth/logout   # 204
$ curl -b cookies.txt localhost:7575/api/v1/auth/me   # 401
```

That login call is a real network round-trip to `lichess.org` — `DrNykterstein` is Magnus
Carlsen's real account — confirming `PlatformClient` actually integrates, not just against
a mock.

The frontend was driven headlessly (Playwright/Chromium) against the running dev servers:
loaded the home page, clicked through to `/login`, toggled Lichess ↔ Chess.com, submitted
a real Lichess username, landed back on the home page with "Welcome back, DrNykterstein"
and the header showing the logged-in state, logged out, and confirmed a bad username shows
the inline "No Lichess account named ..." error. No console errors beyond the expected
401/404 network log entries from the deliberate negative-path tests. Screenshots were
reviewed for each step.

## Decisions honoured

| Decision | How |
|----------|-----|
| D-003 identity | Login by chess platform account, no email/password. Simplified per ADR-0014, confirmed with owner |
| D-008 no hardcoded values | `SESSION_JWT_SECRET`, `SESSION_TTL_SECONDS`, `DATABASE_URL` all from `.env`; `IdentitySettings` no longer carries unused OAuth fields |
| ADR-0005 three-layer memory | Not yet exercised — no chat/memory code lands until Phase 11 |
| ADR-0012 permission model | `ProfileRelationship` table and `verified` flags laid down now so Phase 9 cross-profile viewing has the columns it needs |

## Deviations from plan

Both already covered above and locked via ADR, not silent:

1. **Supabase deferred** — [ADR-0015](../adr/0015-postgres-for-mvp-supabase-deferred.md), landed in the prior commit on this branch.
2. **Simple username-claim login instead of real OAuth2 PKCE** — [ADR-0014](../adr/0014-simple-username-claim-login-for-mvp.md), confirmed with the owner this session before implementation.

## Known gaps

| Gap | Resolution |
|-----|-----------|
| No proof of account ownership — anyone can log in as any existing username | Accepted for MVP per ADR-0014; **must** close before any private-data or write feature ships |
| A weak `SESSION_JWT_SECRET` (under 32 bytes) is not rejected at startup, only warned about by PyJWT | Worth a `missing_required_for_production`-style length check before Phase 17 hosting |
| `AuthService.current()` picks the first-linked identity to represent "who is this session" | Fine while signup creates exactly one identity; breaks once a user can link a second provider — needs the session to track which identity logged in |
| Dev-insight routes (`/dev/traces`) remain unauthenticated | Unchanged from Phase 1 — they are dev-only, off in production, and gating them behind the new auth layer was judged out of this phase's minimal scope |
| No E2E test suite checked into the repo for the login flow | Verified manually with a headless-Chromium script (see Verification) rather than committing Playwright as a dependency, to keep this phase minimal; worth adding once more user-visible flows exist |
| `final_docs/v2/data-model.md` still shows `lichess_id` on `users` | Pre-existing drift from before this phase (already flagged in `identity.py`'s own docstring); not touched, out of this phase's scope |

## Risks

| Risk | Status |
|------|--------|
| Login trust gap reaching a feature that assumes real identity | Documented in ADR-0014 with an explicit follow-up requirement; `verified=false` is stored on every row so it's checkable in code, not just in a comment |
| Test suite silently corrupting shared state | Was live (see Bug section); now structurally prevented by a differently-named test database |
| R-12 schema/architecture tangle | Continues to be mitigated: `domain/auth` has no import of `api/routes`; routes stay thin and delegate |

## Structure review

Largest new file is `app/domain/auth/service.py` at 180 lines — login, account bootstrap,
and current-user resolution for a table cluster of six models. Kept as one file because
the three methods share the same three-table write pattern and splitting further would
scatter that pattern rather than clarify it. `frontend/src/features/auth/components/LoginForm.tsx`
at 109 lines is the largest frontend file, single responsibility (form + inline error
mapping). No refactor needed before sign-off.

## Recommendation

**Ready for sign-off**, with the login trust gap flagged prominently rather than buried —
it is the one thing about this phase that must not be forgotten before Phase 9 (cross-
profile viewing) or any phase touching private data.

**Phase 3 preview** — game ingestion: uploaded PGN, pasted PGN, batch upload, and (once
the trust gap above is judged acceptable to build on top of, or is closed first) Lichess
and Chess.com game imports.
