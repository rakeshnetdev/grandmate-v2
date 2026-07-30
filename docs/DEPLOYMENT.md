# Deployment — Fly.io backend, Vercel frontend

> ## ⚠️ PLANNED — NOT YET DEPLOYED
>
> **Nothing in this document has been run against a real deployment.** Every step below is
> derived from reading the code, not from watching it work. The sibling project's
> deployment guide could say "verified against a real container build"; this one cannot,
> and says so rather than implying otherwise.
>
> The hosting decision belongs to **Phase 17**, deferred from Phase 0 (D-006). The
> Dockerfile's own header says it exists "so the deployment decision is not foreclosed."
>
> **Four blockers below will stop a deploy today.** All four are real, found in the code,
> and none has been worked around.

---

## 0. Blockers — fix before attempting anything else

| # | Blocker | Evidence | Fix |
|---|---|---|---|
| 1 | **Container crashes at startup.** `lifespan` calls `load_opening_index` unconditionally, which raises `OpeningDatasetError` when `data/openings/dist/all.tsv` is missing. The Dockerfile only does `COPY app ./app`. | `app/main.py:58`, `domain/patterns/opening_lookup.py:91`, `backend/Dockerfile` | `COPY data ./data` (2.3 MB) |
| 2 | **Migrations cannot run.** `alembic` the package is installed (it is a main dependency), but `alembic/` and `alembic.ini` are never copied into the image. | `backend/Dockerfile` | `COPY alembic ./alembic` and `COPY alembic.ini ./` |
| 3 | **Login silently fails from Vercel.** The session cookie is `samesite="lax"`. `*.vercel.app` → `*.fly.dev` is cross-site — both are on the Public Suffix List — so the browser accepts the cookie at login and then never sends it. `/auth/me` 401s forever, with no error to explain why. | `app/api/routes/auth.py:48` | Custom domain (preferred) or `SameSite=None; Secure` — see §4 |
| 4 | **Background jobs get killed.** Engine analysis and platform imports run via FastAPI `BackgroundTasks` *after* the response is sent. A Fly machine that auto-stops when idle dies mid-Stockfish, with the job left `pending` and nothing to pick it up. | `api/routes/imports.py:140,200`, `analysis.py:109` | `min_machines_running = 1` for a demo; a real worker for anything more — see §6 |

Blocker 3 is the expensive one to debug if you meet it unprepared: everything appears to
work, the login response is a clean 200 with a `Set-Cookie` header, and only the *next*
request reveals the problem.

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

**Option B — cross-site cookie.** Keep the platform subdomains and set `SameSite=None`
with `Secure` (both platforms give you HTTPS anyway). Works, but gives up the CSRF
protection `Lax` was providing, and browsers grow steadily more hostile to third-party
cookies.

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

Two things that are easy to miss:

```json
// frontend/vercel.json — without this, /games/:id 404s on a hard refresh
{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
```

`VITE_API_BASE_URL` is baked in at **build** time, not read at runtime — changing it
requires a redeploy, not just an environment-variable edit. `shared/config/env.ts`
validates it with Zod, so a wrong value fails loudly at boot rather than producing
mysterious network errors.

---

## 9. What "verified" would mean

The sibling project's deployment doc carries a table of checks run against a real
container. This section is the placeholder for the equivalent, and is deliberately empty.

| Check | Result |
|---|---|
| Image builds | *not verified* |
| No `.env` or key material in any layer | *not verified* |
| Runs as non-root | *not verified* — the Dockerfile does not currently set a `USER` |
| Stockfish reachable at the configured path | *not verified* in a deployed container |
| Migrations run via release command | *not verified* |
| Corpus ingestion chunk count | *not verified* |
| `GET /health` and `/ready` | *not verified* |
| Login round-trip from the deployed frontend | *not verified* — blocker 3 makes this the one most likely to fail |
| Background analysis completes | *not verified* — blocker 4 |

Fill this in from a real deploy. Do not fill it in from intent.

---

## 10. Relevance to the certification rubric

**Task 4 is worth 15 points and requires a deployed, decoupled prototype.** Until the
blockers in §0 are fixed and a real deployment exists, those points cannot honestly be
claimed. This is recorded in [`grading-rubric.md`](grading-rubric.md) as an open item
rather than self-scored as complete.

Estimated cost once deployed: a 2 GB Fly machine at roughly $15–20/month, managed Postgres
free-tier to ~$25/month, Vercel free. OpenAI usage is already capped by
`LLM_DAILY_TOKEN_CEILING`.

---

## 11. Troubleshooting — predicted, not observed

Every row here is a prediction from reading the code. Confirm against real logs.

| Symptom | Likely cause |
|---|---|
| Container crash-loops immediately, `OpeningDatasetError` | Blocker 1 — `data/` not in the image |
| `alembic: command not found` or "no such file `alembic.ini`" | Blocker 2 |
| Login returns 200, then every request is 401 | Blocker 3 — cookie set but never sent cross-site |
| Import returns 201, analysis never completes, job stays `pending`, no error | Blocker 4 — machine stopped before the background task ran |
| Chat answers with no retrieved context | Corpus never ingested against this database |
| `CREATE EXTENSION vector` fails | The chosen Postgres does not offer pgvector |
| Frontend calls `localhost` in production | Built without `VITE_API_BASE_URL` — set it and **redeploy** |
| Prepared-statement errors under load | Supabase pooler in transaction mode; use the direct URL |
| Analysis silently slow or OOM-killed | Under-sized machine — see §3 |
