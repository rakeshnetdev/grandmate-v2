# Deployment — Fly.io backend, Vercel frontend

> ## ✅ DEPLOYED AND VERIFIED — 2026-08-04
>
> | | |
> |---|---|
> | Frontend | https://grandmate.vercel.app |
> | Backend | https://grandmate-v2-backend.fly.dev |
> | Database | Neon Postgres 17 + pgvector 0.8.0, AWS `us-west-2` |
>
> This document used to say "nothing here has been run against a real deployment". That
> is no longer true, and the change is worth stating precisely: **six of the seven
> problems below were only findable by deploying.** Four were predicted by reading the
> code; three were not, and one of those was introduced by the fix for another.
>
> Every command in §8a was executed. The results are in §9.

---

## 0. What went wrong, and why

Seven problems stood between a working local app and a working deployed one. They are
listed in the order they were *hit*, not the order they were understood, because the order
matters: two of them only became visible after an earlier one was fixed.

| # | Problem | How it presented | Fix |
|---|---|---|---|
| 1 | `data/` not copied into the image | Crash loop: `OpeningDatasetError: Opening dataset file not found` | `COPY data ./data` |
| 2 | `alembic/` not copied into the image | Migrations could not run at all | `COPY alembic ./alembic`, `COPY alembic.ini ./` |
| 3 | Session cookie hardcoded `SameSite=Lax` | Login returns a clean 200 with `Set-Cookie`; the *next* request 401s, forever | `SESSION_COOKIE_SAMESITE`, set to `none` |
| 4 | Background jobs killed by machine auto-stop | Import succeeds, analysis silently never arrives | `min_machines_running = 1` |
| 5 | **Stockfish not at the configured path** | Container perfectly healthy, no game ever analysed | `STOCKFISH_PATH = '/usr/games/stockfish'` |
| 6 | **`scripts/` not copied into the image** | `ModuleNotFoundError: No module named 'scripts'` running the documented ingest command | `COPY scripts ./scripts` |
| 7 | **CORS placeholder treated as fatal** | Ten restart attempts, `RuntimeError: Missing required configuration: CORS_ALLOWED_ORIGINS`, on an otherwise healthy container | Split fatal config from advisory warnings |

Problems 1–4 were predicted by reading the code before any deploy was attempted. **5, 6 and
7 were not**, and they are the interesting ones.

### 5 — Stockfish was never where the app looked

Debian's `stockfish` package installs the binary at `/usr/games/stockfish` and does not put
it on `PATH`. `EngineSettings.stockfish_path` defaults to `/usr/local/bin/stockfish`, which
is correct on a developer's machine with Homebrew and absent from the image.

The failure mode is the dangerous kind: **nothing looks wrong**. The web process never
touches the engine, so `/health` passes, imports return `201`, and jobs queue happily. Only
the background worker needs Stockfish, and its failure is not on any request path.

Found by running the Dockerfile's own `apt-get` line in `python:3.13-slim` and looking:

```bash
docker run --rm python:3.13-slim sh -c \
  'apt-get update -qq && apt-get install -y -qq stockfish && ls -la /usr/games/stockfish'
```

`/ready` now reports `checks.stockfish_binary`, which is what makes this visible rather
than inferred.

### 6 — The documented command did not exist in the image

`DEPLOYMENT.md` told the operator to run
`fly ssh console -C 'uv run python -m scripts.ingest_corpus'`. The Dockerfile copied `app`,
`data`, `alembic` and `alembic.ini` — not `scripts`. The command failed with
`ModuleNotFoundError`.

This one could not have been caught by reading code, because the thing that broke is a
command a human runs by hand. It is the clearest argument for why the "planned, not
verified" banner this document used to carry was honest rather than pedantic.

Corpus ingestion is a **required deployment step**, not a development convenience: without
it `search_knowledge` returns nothing and chat quietly degrades to answering from game
analysis alone, with the container reporting healthy throughout — the same shape as
problem 5.

### 7 — A fix that deadlocked the deployment

While closing the others, `/ready` was observed returning `ready` while
`CORS_ALLOWED_ORIGINS` was still the `REPLACE-ME` placeholder. The obvious repair — add the
placeholder to `missing_required_for_production()` — was wrong, because that list is not
only read by `/ready`. `main.py`'s lifespan turns it into a `RuntimeError` and refuses
startup.

The result was a **deadlock**, not merely a wrong check:

- The backend refused to start until it knew the frontend's origin.
- The frontend could not be built until it knew the backend's URL, because
  `VITE_API_BASE_URL` is compiled into the bundle rather than read at runtime.

Neither side could go first. Ten restart attempts later, the container was still healthy in
every respect except the one that stopped it existing.

The fix splits the checks along the line that actually matters:

| Method | Means | Effect |
|---|---|---|
| `missing_required_for_production()` | the process **cannot function** — `DATABASE_URL`, `SESSION_JWT_SECRET`, `OPENAI_API_KEY`, and a wildcard CORS origin under `SameSite=None` | refuses startup |
| `deployment_warnings()` | the process **works but is not yet wired to its frontend** | reported in `/ready`'s `warnings`, verdict unchanged |

A wildcard origin under `SameSite=None` stays fatal: that is a live security hole, since
the allow-list is then the only thing bounding who may make a credentialed request with a
user's session. A placeholder origin is the opposite — nothing is unsafe, the frontend
merely does not exist yet.

### Two non-problems worth recording

**`sea` is deprecated.** The Fly region was set to `sea` (Seattle) to sit closest to the
Neon database in AWS `us-west-2` (Oregon). Fly rejects it outright — *"Region sea is
deprecated and cannot have new resources provisioned"* — and recommends `sjc` in the same
error. `sjc` is same-coast, roughly 10–15 ms further from the database. The reasoning was
right; the region was not available.

**`fly launch` overwrites `fly.toml` and strips every comment.** It also resets
`primary_region` to whatever is nearest the developer. The values survived; the reasons did
not. If you run it again, decline the overwrite prompt or restore from git.

---

## 1. What the container needs at startup

Three things must be true before the app serves a request.

**The opening dataset must be on disk.** `load_opening_index` parses ~3,800 rows of
vendored TSV once at startup and holds the index in `app.state`. This is a hard failure by
design — the same "fail fast, not on first request" posture as the production config check
— so a missing file is a crash loop, not a silent degradation.

**The database must have `pgvector` and the current schema.** `CREATE EXTENSION IF NOT
EXISTS vector` plus `alembic upgrade head`. LangGraph's checkpointer and store tables
create themselves via idempotent `.setup()` calls on first use, so they need no deploy
step — and `alembic/env.py` deliberately filters them out of autogenerate.

**The corpus must be ingested, once, against the production database.** `uv run python -m
scripts.ingest_corpus`. This costs real embedding calls. Skipping it is not fatal — the app
starts — but `search_knowledge` returns nothing and chat quietly degrades to answering from
analysis alone. Worth a startup log line stating the chunk count, so a zero is visible
rather than inferred.

Unlike the sibling project, ingestion is **not** wired into an entrypoint script. It is a
manual one-shot today.

---

## 2. Database

`ADR-0015` deferred Supabase but noted that "because Supabase is Postgres, adopting it
later changes this URL and nothing else." Deployment is that moment. Supabase, Neon, or
Timescale all ship `pgvector` as a first-class extension; verify availability on whatever
Fly's current Postgres offering is before committing to it, since that has changed more
than once.

One trap worth knowing: the app derives **three** connection strings from one
`DATABASE_URL` — asyncpg for the application, psycopg for Alembic (`sync_url`), and a bare
libpq string for LangGraph (`psycopg_conninfo`). If you use a Supabase **pooler** URL,
transaction-mode pooling breaks prepared statements. Put the direct connection string in
`DATABASE_URL`, or use session-mode pooling.

---

## 3. Machine sizing

Stockfish is why a small instance will not work:

```
ENGINE_HASH_MB=128  ×  ENGINE_MAX_CONCURRENT_GAMES=4  =  512 MB of hash tables
+ Python, FastAPI, SQLAlchemy, the opening index      ≈  250–350 MB
```

**1 GB minimum, 2 GB comfortable.** Alternatively drop `ENGINE_MAX_CONCURRENT_GAMES` to 2
and accept slower batches — it is an environment variable, not a code change.

Keep `ENGINE_THREADS=1`. That is not a performance oversight: multi-threaded Stockfish is
not reproducible across runs, and the classification-stability guarantee depends on it.

---

## 4. The cross-origin cookie decision

Two ways out of blocker 3.

**Option A — custom domain (recommended).** `app.grandmate.dev` on Vercel,
`api.grandmate.dev` on Fly. A shared registrable domain means same-site, so `SameSite=Lax`
keeps working unchanged and retains its CSRF protection. No code change.

**Option B — cross-site cookie.** Keep the platform subdomains and set
`SESSION_COOKIE_SAMESITE=none`. Works, but gives up the CSRF protection `Lax` was
providing, and browsers grow steadily more hostile to third-party cookies.

```bash
SESSION_COOKIE_SAMESITE=none
CORS_ALLOWED_ORIGINS=https://<your-app>.vercel.app
APP_ENV=production
```

Two things the code does for you here, both because the halves are not independently
valid:

- **`Secure` is derived, not configured.** Browsers reject a `SameSite=None` cookie
  outright unless it is also `Secure`, so the route sets `secure=True` whenever the policy
  is `none` rather than trusting two settings to agree. Getting one right and the other
  wrong would drop the cookie silently, which is the same failure this blocker already
  cost once.
- **A wildcard CORS origin becomes a production blocker.** With `SameSite=None` the
  allow-list is the *only* thing bounding who can make a credentialed request carrying the
  user's session, so `missing_required_for_production()` reports `CORS_ALLOWED_ORIGINS`
  when it is `*` and the policy is `none`. That combination is only reachable by setting
  both deliberately.

Either way `CORS_ALLOWED_ORIGINS` must name the exact frontend origin — the app sets
`allow_credentials=True`, and a browser rejects a wildcard in that combination.

The frontend already sends `credentials: 'include'` (`shared/lib/api-client.ts`), so no
change is needed there.

---

## 5. File storage

`STORAGE_BACKEND=local` writes raw PGNs to `.storage` on the container filesystem, and
`domain/games/service.py:38` **reads them back** during canonicalization. Fly machine
filesystems are ephemeral.

| Option | Cost |
|---|---|
| **Fly volume** | Simplest. Pins the app to one machine — no horizontal scaling, and volumes do not follow a machine across regions. |
| **S3/R2 adapter** | ~60 lines. `StorageBackend` was built for exactly this: ADR-0015 says swapping "means writing one adapter, not changing calling code." |

The volume is fine for a demo. The adapter is the honest answer if more than one machine is
ever in play.

---

## 6. Background work

This is the architectural decision Fly forces, and Phase 14 made it sharper: a Lichess
import of 60 games is an HTTP fetch plus roughly 7 seconds per game of Stockfish —
**several minutes** of work with no HTTP request holding the machine awake.

| Approach | Trade-off |
|---|---|
| `auto_stop_machines = false`, `min_machines_running = 1` | Simplest. Machine always on. Work still dies on deploy or restart, and no retry exists to recover it. |
| A worker process polling the `jobs` table | The right shape. `jobs` already has `kind`, `status`, and an unused `idempotency_key` — it was designed for this in Phase 3, and `run_pending_analysis_jobs` already takes a job id and opens its own session. |

For a demo, the first. For anything real, the second.

---

## 7. Configuration

Secrets via `fly secrets set`: `OPENAI_API_KEY`, `SESSION_JWT_SECRET`, `DATABASE_URL`.
Everything else can be plain `[env]` in `fly.toml`.

`SESSION_JWT_SECRET` needs ≥32 bytes of real randomness. A known gap from Phase 2: a short
secret is **not rejected at startup**, only warned about by PyJWT — so this will not fail
loudly if you get it wrong.

Set `APP_ENV=production`. It turns on `Secure` cookies, hard-disables every `/dev/*` route,
and makes startup fail fast on missing configuration rather than deferring to first use.

A sketch of the shape (not a verified file):

```toml
app = "grandmate-api"
primary_region = "sjc"

[build]
  dockerfile = "backend/Dockerfile"

[env]
  APP_ENV = "production"
  API_HOST = "0.0.0.0"
  API_PORT = "7575"
  CORS_ALLOWED_ORIGINS = "https://<your-frontend>"
  STOCKFISH_PATH = "/usr/games/stockfish"
  ENGINE_MAX_CONCURRENT_GAMES = "2"

[http_service]
  internal_port = 7575
  force_https = true
  auto_stop_machines = false   # see §6 — background jobs die otherwise
  min_machines_running = 1

[[vm]]
  memory = "2gb"               # see §3 — Stockfish hash tables

[deploy]
  release_command = "alembic upgrade head"
```

---

## 8. Frontend on Vercel

Root directory `frontend`, framework preset Vite, build `npm run build`, output `dist`.

`frontend/vercel.json` is now committed and carries the build settings plus the SPA
rewrite, so the dashboard does not have to be configured by hand:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

The catch-all rewrite does not swallow the built assets: Vercel matches static files
first and only falls through to a rewrite when nothing on disk matches. Without it a hard
refresh on any route below `/` 404s, because the SPA owns routing and the server has only
`index.html`.

One thing that is still easy to miss:

`VITE_API_BASE_URL` is baked in at **build** time, not read at runtime — changing it
requires a redeploy, not just an environment-variable edit. `shared/config/env.ts`
validates it with Zod, so a wrong value fails loudly at boot rather than producing
mysterious network errors.

---

## 8a. The deploy, in order

This is the sequence that was actually run, with the ordering constraints that make it a
sequence rather than a checklist:

- The database must exist and have `pgvector` **before** the first deploy, because
  `release_command` runs migrations before machines take traffic.
- Secrets must be set **before** the first deploy, for the same reason. A blank
  `DATABASE_URL` does not error — it falls back to the local development default and fails
  as *"connection to 127.0.0.1:5433 refused"*, which reads like a networking problem and is
  not one.
- The corpus is ingested **after** the backend is up, because it writes to the live
  database through the app's own code.
- The frontend is built **after** the backend exists, because `VITE_API_BASE_URL` is
  compiled into the bundle.
- CORS is set **last**, because the frontend's origin does not exist until Vercel has
  deployed it. This is why the placeholder must warn rather than be fatal — see problem 7.

### 1 — Database

Provision Postgres 17 with `pgvector`. Neon was used here; Fly Postgres and Supabase both
work (§2). Pick the region closest to the Fly region, not to yourself: one chat turn costs
many round trips to Postgres — session lookup, game queries, pgvector search, two LangGraph
checkpointer writes — while a user pays one round trip to the app.

```sql
-- Neon's SQL editor, or psql
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extversion FROM pg_extension WHERE extname = 'vector';   -- expect 0.8.x
```

Then convert the connection string for the app. Neon hands you a libpq URL; SQLAlchemy
needs its dialect:

```
# what Neon gives you — use this for psql
postgresql://user:pass@ep-xxx.us-west-2.aws.neon.tech/neondb?sslmode=require

# what DATABASE_URL needs — driver prefix added, sslmode dropped
postgresql+asyncpg://user:pass@ep-xxx.us-west-2.aws.neon.tech/neondb
```

`+asyncpg` is a SQLAlchemy dialect string, not a URL scheme — `psql` will reject it. And
`sslmode` is a libpq parameter that asyncpg rejects; TLS is negotiated anyway. **Use the
direct connection string, not the pooled one** (§2).

### 2 — Backend service

```bash
cd backend
fly auth login
fly launch --no-deploy      # decline: its Postgres offer, and overwriting fly.toml
```

`fly launch` rewrites `fly.toml` and strips every comment even when you decline. Restore
from git if it does.

Secrets one at a time — a line continuation with trailing whitespace produces
`could not parse secrets: ' ': must be in the format NAME=VALUE`:

```bash
fly secrets set --stage DATABASE_URL='postgresql+asyncpg://...'
fly secrets set --stage OPENAI_API_KEY='sk-...'
fly secrets set SESSION_JWT_SECRET="$(openssl rand -base64 48)"
```

`--stage` records without deploying; the last one applies all three. Single quotes protect
`$` and `&` in Neon passwords; the `openssl` one needs double quotes to expand.

```bash
fly deploy
curl -fsS https://<app>.fly.dev/health
curl -fsS https://<app>.fly.dev/ready
```

`/ready` should return `200` with `missing_configuration: []` and
`warnings: ["CORS_ALLOWED_ORIGINS"]` — healthy, and honest that the deploy is half done.

### 3 — Corpus, once

```bash
fly ssh console -C 'uv run python -m scripts.ingest_corpus'
```

Costs real embedding calls. Skipping it is not fatal and that is the problem: the app
starts, chat answers, and `search_knowledge` silently returns nothing. Verify:

```sql
SELECT bucket, count(*) FROM knowledge_chunks GROUP BY bucket;
```

Four buckets, ~92 chunks. `analysis` is absent by design — it is profile-scoped and written
at runtime.

### 4 — UI

```bash
cd ../frontend
vercel login && vercel link
vercel env add VITE_API_BASE_URL production     # https://<app>.fly.dev — no trailing slash
vercel --prod
```

No trailing slash: `api-client.ts` concatenates directly, so one would produce `//api/v1/…`.
`vercel.json` is committed, so the build command, output directory and SPA rewrite need no
dashboard configuration.

### 5 — Close the loop

```bash
cd ../backend
fly secrets set CORS_ALLOWED_ORIGINS='https://<app>.vercel.app'
```

Use the **stable alias**, not the per-deployment URL — the latter changes on every push and
will be rejected. Setting a secret triggers its own redeploy. `/ready` should now return
`warnings: []`.

### 6 — Verify in a browser

Log in, paste a PGN, wait for analysis, ask a question in chat. Everything before this
proves the process is up; only this proves the product works.

---

## 8b. Related operational documents

These live in `final_docs/`, which is a **git submodule on a private repository** — run
`git submodule update --init` if the directory is empty. Nothing in the deploy path reads
them; they are what you reach for around a deploy rather than during one.

| Document | When you want it |
|---|---|
| [`../final_docs/beta/release_checklist.md`](../final_docs/beta/release_checklist.md) | Pre-flight, before running §8a |
| [`../final_docs/runbooks/incidents.md`](../final_docs/runbooks/incidents.md) | When a deployed container misbehaves |
| [`../final_docs/playbooks/backup_and_recovery.md`](../final_docs/playbooks/backup_and_recovery.md) | Database restore |

The incident runbook covers the crash loop from problem 1 (missing opening TSVs) and the
silent-Stockfish failure from problem 5, which is the quieter of the two: the container
reports healthy and simply never analyses anything.

---

## 9. Verified — 2026-08-04

This section was deliberately empty while the document was speculative. It is no longer.
Every row below was executed against the live deployment.

| Check | Result |
|---|---|
| Image builds and pushes | 230 MB |
| `release_command` runs migrations | `alembic upgrade head` on Neon |
| Container starts without crash-looping | after problem 7 was fixed |
| `GET /health` | `200`, ~96 ms |
| `GET /ready` | `200`, `missing_configuration: []`, `warnings: []` |
| `checks.stockfish_binary` | `true` — problem 5 confirmed fixed *in the real image* |
| `checks.llm_configured` | `true` |
| Corpus ingested | **92 chunks** — rules 35, openings 27, tactics 16, strategy 14 |
| Frontend serves | `200` at `https://grandmate.vercel.app` |
| SPA rewrite | `/login` returns `200`, not `404` — `vercel.json` in effect |
| `VITE_API_BASE_URL` baked into the bundle | `https://grandmate-v2-backend.fly.dev` present in `assets/index-*.js` |
| CORS preflight from the real origin | `access-control-allow-origin: https://grandmate.vercel.app`, `access-control-allow-credentials: true` |
| Full UI path | login → import → analysis → chat, confirmed in a browser |

The `analysis` bucket is absent from the chunk counts by design: it is profile-scoped and
written at runtime as games are analysed, not seeded by ingestion.

### What is still not verified

- **Load of any kind.** One user, a handful of games. Nothing here says what happens at
  ten concurrent imports.
- **Recovery.** A machine restart mid-analysis still loses the job, because
  `min_machines_running = 1` is a workaround for the missing worker, not a replacement
  (§6). No retry path has been exercised.
- **Preview deployments.** Only the production alias is in `CORS_ALLOWED_ORIGINS`. Vercel
  preview URLs change per push and will be rejected. A wildcard is deliberately refused
  under `SameSite=None`, so this needs a real decision rather than a quick fix.
- **Cost.** An always-on 2 GB machine, unmeasured over time.

---

## 10. Relevance to the certification rubric

**Task 4 is worth 15 points and requires a deployed, decoupled prototype.** That is now
satisfied: the backend and frontend are separately deployed, separately toolchained, and
talk over a typed HTTP contract across two hosting providers. §9 records the evidence.

Cost: a 2 GB Fly machine at roughly $15–20/month, Neon free tier, Vercel free. OpenAI usage
is capped by `LLM_DAILY_TOKEN_CEILING`. Not yet measured over a full billing period.

---

## 11. Troubleshooting

Rows marked **observed** were hit during the deploy this document records. The rest are
still predictions from reading the code.

| Symptom | Likely cause |
|---|---|
| **observed** — Release command fails, `connection to 127.0.0.1:5433 refused` | `DATABASE_URL` unset. It does not error; it falls back to the local development default. `release_command` calls Alembic directly and never runs `missing_required_for_production()`, so it cannot tell you that by name |
| **observed** — `ModuleNotFoundError: No module named 'scripts'` | Problem 6 — `scripts/` not in the image |
| **observed** — Container healthy, `/ready` passes, no game ever analysed | Problem 5 — Stockfish at the wrong path. Check `/ready`'s `checks.stockfish_binary` |
| **observed** — Crash loop, `RuntimeError: Missing required configuration: CORS_ALLOWED_ORIGINS` | Problem 7 — a placeholder treated as fatal. Placeholders belong in `deployment_warnings()`, not the required list |
| **observed** — `could not parse secrets: ' ': must be in the format NAME=VALUE` | Trailing whitespace after a `\` line continuation. Set secrets one at a time with `--stage` |
| **observed** — `Region sea is deprecated and cannot have new resources provisioned` | Fly retired the region. Use `sjc` for AWS `us-west-2` |
| **observed** — `fly.toml` loses all its comments | `fly launch` rewrote it. Restore from git |
| Container crash-loops immediately, `OpeningDatasetError` | Blocker 1 — `data/` not in the image |
| `alembic: command not found` or "no such file `alembic.ini`" | Blocker 2 |
| Login returns 200, then every request is 401 | Blocker 3 — cookie set but never sent cross-site |
| Import returns 201, analysis never completes, job stays `pending`, no error | Blocker 4 — machine stopped before the background task ran |
| Chat answers with no retrieved context | Corpus never ingested against this database |
| `CREATE EXTENSION vector` fails | The chosen Postgres does not offer pgvector |
| Frontend calls `localhost` in production | Built without `VITE_API_BASE_URL` — set it and **redeploy** |
| Prepared-statement errors under load | Supabase pooler in transaction mode; use the direct URL |
| Analysis silently slow or OOM-killed | Under-sized machine — see §3 |
