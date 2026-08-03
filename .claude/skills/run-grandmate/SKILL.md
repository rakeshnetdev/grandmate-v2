---
name: run-grandmate
description: Build, run, screenshot, and drive the GrandMate chess-coaching app (FastAPI backend + React/Vite frontend). Use when asked to run, start, launch, smoke-test, screenshot, or debug GrandMate locally, or to verify a UI change in a real browser.
---

# Running GrandMate

Two processes plus a database: a FastAPI backend on **:7575**, a Vite/React frontend on
**:3535**, and Postgres (pgvector) on **:5433**. The UI is driven programmatically by
`driver.mjs` in this directory — a zero-dependency Chrome DevTools Protocol client that
logs in, picks a game, opens tabs, and writes PNGs.

All paths below are relative to the repo root (`grandmate-v2/`). Verified on macOS 15.7
with Node 25, `uv`, Docker, and Chrome installed.

## Prerequisites

Already present on this machine; on a fresh one:

```bash
brew install uv node docker stockfish
```

Chrome is required for the driver (`/Applications/Google Chrome.app`, or Playwright's
cached Chromium if you have one). No `chromium-cli` and no `playwright` npm package are
needed — the driver talks CDP directly.

Note macOS lacks `psql` and `timeout`. Query the database with `uv run python -c ...`
(examples below) rather than reaching for `psql`.

## Start everything

```bash
docker compose up -d postgres                      # :5433, pgvector
cd backend && uv run alembic upgrade head          # migrations
cd backend && uv run python -m app                 # :7575, auto-reloads in development
cd frontend && npm run dev                         # :3535
```

Check it came up (note the path — `/health`, *not* `/api/v1/health`):

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:7575/health   # 200
```

`backend/.env` must exist. `OPENAI_API_KEY` is only needed for LLM features (reports,
story, chat); without it those fall back to deterministic text rather than erroring.

## Run: drive the UI (agent path)

```bash
# End-to-end: log in, list tabs, select a game, screenshot. Exits nonzero on failure.
node .claude/skills/run-grandmate/driver.mjs smoke

# Screenshot one tab of one game.
node .claude/skills/run-grandmate/driver.mjs shot --profile study --game 1 --tab Story

# Read state out of the running page.
node .claude/skills/run-grandmate/driver.mjs eval \
  '[...document.querySelectorAll("[role=tab]")].map(t=>t.textContent)'
```

Verified output of `smoke`:

```
→ frontend http://localhost:3535
✓ logged in, workspace rendered
✓ tabs: Overview, Chat, Memory
… no games in "My games" — trying "Study games"
✓ selected game: NikitaShandrygin vs Hikaru (0-1)
✓ game tabs: Overview, Analysis, Moves, Patterns, Story, PGN, Chat, Memory
✓ screenshot: .../.claude/skills/run-grandmate/screenshots/smoke.png
```

Flags: `--headed` (watch it), `--profile my|study`, `--game N`, `--tab <label>`.
Env: `GRANDMATE_URL`, `GRANDMATE_USER` (default `DrNykterstein`).
Screenshots default to `.claude/skills/run-grandmate/screenshots/` (git-ignored); pass
a path to `shot` to put one elsewhere. On failure the driver writes `fail.png` there —
**look at it**, it is usually decisive.

## Run: drive the API (no browser)

Login takes a username and no password (MVP unverified identity, ADR-0014), and returns
a session cookie:

```bash
curl -s -c /tmp/gm.txt -X POST http://localhost:7575/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"provider":"lichess","username":"DrNykterstein"}'

curl -s -b /tmp/gm.txt http://localhost:7575/api/v1/profiles      # self + study profile ids
curl -s -b /tmp/gm.txt http://localhost:7575/api/v1/games         # own games
```

Get real data in (imports another player's games; they land in the **study** profile
automatically):

```bash
curl -s -b /tmp/gm.txt -X POST http://localhost:7575/api/v1/imports/chesscom/sync \
  -H 'Content-Type: application/json' -d '{"window":10,"username":"Hikaru"}'
# → {"id":"<job-id>","status":"pending",...}; poll it:
curl -s -b /tmp/gm.txt http://localhost:7575/api/v1/imports/<job-id>
```

Interactive API docs: <http://localhost:7575/docs>.

## Run: call domain code directly (no server)

Most backend changes are quicker to check this way than through HTTP:

```bash
cd backend && uv run python -c "
import asyncio
from sqlalchemy import select
from app.core.config import get_settings
from app.db.models import Profile, ProfileKind
from app.db.session import create_engine, create_session_factory
from app.domain.games import list_games

async def main():
    e = create_engine(get_settings().database); S = create_session_factory(e)
    async with S() as s:
        study = (await s.execute(select(Profile).where(
            Profile.kind == ProfileKind.OPPONENT))).scalars().first()
        print(len(await list_games(s, study.id)), 'study games')
    await e.dispose()
asyncio.run(main())"
```

## Test

```bash
cd backend  && uv run pytest -q                    # 857 passed, ~2.5 min
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run mypy app/
cd frontend && npm run test -- --run               # 115 passed
cd frontend && npm run build                       # tsc -b + vite build
```

## Gotchas

Each of these cost real time to find:

- **The login form is at `/login`, not `/`.** Logged out, `/` renders a landing card
  with a "Log in" button; a driver that types into `/` waits forever.
- **Health is `/health`, not `/api/v1/health`** — the latter 404s.
- **Postgres is on 5433**, deliberately, so it doesn't collide with a local 5432.
- **CORS is pinned to exactly `http://localhost:3535`.** If Vite starts on another
  port, every API call fails preflight with an opaque **400**. `strictPort: true` now
  makes Vite fail loudly instead of silently bumping to 3536 — don't remove it.
- **"My games" can be empty while games exist.** An imported player's games go to the
  separate *study* profile (routed per game by whether the PGN headers match your linked
  username). Use `--profile study`.
- **Analysis and Story tabs make live LLM calls** (5–20s on first view per game). The
  driver waits for them. With no `OPENAI_API_KEY` you silently get a deterministic
  report badged "Deterministic summary" rather than an error.
- **Reports are cached** per (game, persona, analysis version), so editing a prompt
  looks like it did nothing. Clear the cache:
  `cd backend && uv run python -m scripts.clear_reports` (`--story`, `--all`).
- **Chess *variant* games are rejected at ingestion** (`unsupported_variant`), as of the
  variant gate in `app/domain/imports/parsing.py`. They used to import fine — Antichess /
  Crazyhouse / etc. parse and canonicalize without complaint — and then **segfault
  Stockfish** when the analysis job fed their positions (an Antichess game legally
  captures both kings, and standard Stockfish crashes on a kingless FEN rather than
  erroring): `engine process died unexpectedly (exit code: -11)`. The job's FAILED write
  was then rolled back by an exception escaping `engine.quit()` under uvloop, so the job
  reverted to `pending` and the startup sweep re-crashed it on **every** restart.
  Pre-existing variant games were deleted from this database on 2026-08-02. If you see
  that segfault again, a variant game got in somehow — check before debugging anything
  else:

  ```bash
  cd backend && uv run python -c "
  import asyncio
  from collections import Counter
  from sqlalchemy import select
  from app.core.config import get_settings
  from app.db.models import Game, GameAnalysis
  from app.db.session import create_engine, create_session_factory
  async def main():
      e = create_engine(get_settings().database); S = create_session_factory(e)
      async with S() as s:
          t = Counter()
          for g in (await s.execute(select(Game))).scalars().all():
              has = bool((await s.execute(select(GameAnalysis.id).where(
                  GameAnalysis.game_id == g.id))).first())
              t[(g.headers.get('Variant') or 'Standard', 'ok' if has else 'NO analysis')] += 1
          for k, n in sorted(t.items()): print(k, n)
      await e.dispose()
  asyncio.run(main())"
  ```

  No retry fixes an already-imported variant game — delete it. Standard, From Position,
  and Chess960 all count as standard chess and still import.
- **A standard game can also fail on the deep pass**, with
  `Analysis of '<fen>' at depth 18 exceeded 30s` (`ENGINE_DEEP_DEPTH=18`,
  `ENGINE_TIMEOUT_S=30`). Unlike the variant crash this is transient — requeuing usually
  succeeds (5 of 6 did). Raise `ENGINE_TIMEOUT_S` if it recurs on the same game.
- **python-chess 1.11.2 + Stockfish 18 floods stderr** with
  `Exception parsing pv from info` and `Engine sent invalid ponder move`. Noisy, but
  **non-fatal** — the analysis still completes. Filter it when reading logs:
  `... 2>&1 | grep -vE "^Exception parsing|^Engine sent"`.
- **Analysis jobs orphan permanently if the backend restarts mid-flight.** They are
  dispatched as FastAPI `BackgroundTasks` with no worker or retry, so a job stuck at
  `pending` never resumes and the UI shows "Analyzing…" forever. Requeue them (with the
  backend stopped, so only one process spawns engines) — see Troubleshooting.
- **The frontend suite flakes under load** with `Failed to start forks worker` /
  worker timeouts. Re-run it; a clean run passes.

## Troubleshooting

**Driver: `Timed out waiting for: workspace tabs`** — the frontend isn't up, or you're
not on `/login`. `curl -s -o /dev/null -w "%{http_code}" http://localhost:3535/`.

**Driver: `CDP timeout: Page.navigate`** — a previous Chrome is still shutting down and
holding the debug port. The driver now uses port 0 + `DevToolsActivePort` to avoid this;
if you see it, `pkill -f remote-debugging-port`.

**Driver: `No Chrome binary found`** — install Chrome, or add your path to
`CHROME_CANDIDATES` in `driver.mjs`.

**A game's Analysis/Story/Moves/Patterns tabs are all empty or stuck** — it has no
`GameAnalysis`. Check the variant first (see Gotchas): a variant game will never
analyze. If it is Standard, its job either failed on the deep-pass timeout or was
orphaned — requeue it with the snippet below.

**Games stuck "Analyzing…" forever** — orphaned jobs. Stop the backend first, then:

```bash
cd backend && uv run python -c "
import asyncio
from sqlalchemy import select
from app.core.config import get_settings
from app.db.models import Job, JobKind, JobStatus
from app.db.session import create_engine, create_session_factory
from app.domain.analysis import run_pending_analysis_jobs

async def main():
    s = get_settings(); e = create_engine(s.database); S = create_session_factory(e)
    async with S() as ses:
        ids = (await ses.execute(select(Job.id).where(
            Job.status == JobStatus.PENDING,
            Job.kind == JobKind.ENGINE_ANALYSIS))).scalars().all()
    print(f'{len(ids)} stuck jobs')
    if ids: await run_pending_analysis_jobs(list(ids), session_factory=S, settings=s)
    await e.dispose()
asyncio.run(main())"
```

**Every API call returns 400** — Vite is not on 3535 (see the CORS gotcha).

**`docker compose up` says port 5433 in use** — an old container is running;
`docker compose ps` then `docker compose down`.
