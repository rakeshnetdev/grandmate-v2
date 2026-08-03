# Runbook — Incident Response

This runbook provides actionable step-by-step procedures for addressing common runtime issues and alerts in the GrandMate production environment.

---

## Blocker/Incident 1: Container Crash Loop (`OpeningDatasetError`)

### Symptom
The container fails to start, crash-looping with the following traceback in the logs:
```
app.domain.patterns.opening_lookup.OpeningDatasetError: Opening dataset file not found at data/openings/dist/all.tsv
```

### Cause
The opening TSV dataset is not copied into the docker image, or the path is incorrect.

### Resolution
1. **Dockerfile Check**: Verify that `COPY data ./data` exists in the `backend/Dockerfile`.
2. **Build and Redeploy**: Rebuild the Docker image to ensure the TSV files are packed:
   ```bash
   fly deploy --no-cache
   ```
3. **Validate Asset Existence**: Run a temporary interactive shell to verify the file path:
   ```bash
   fly ssh console -C "ls -la /app/data/openings/dist/all.tsv"
   ```

---

## Incident 2: Analysis Jobs Stuck in `PENDING` or `PROCESSING`

### Symptom
Users report that imported games never show Stockfish analysis or opening tags. The dashboard shows `status: pending` or `status: processing` indefinitely.

### Cause
- The worker or web process was rebooted or crashed mid-job.
- The Fly.io machine auto-stopped due to inactivity because background tasks were run in-process without an active HTTP connection holding it awake.

### Resolution
1. **Restart Application**: Re-running or restarting the container triggers the `startup_analysis_sweep` ([dispatch.py](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/backend/app/domain/analysis/dispatch.py)) which automatically resets all `processing` jobs to `pending` and re-runs them:
   ```bash
   fly machine restart <machine-id>
   ```
2. **Configure Auto-Stop Setting**: In `fly.toml`, ensure that `auto_stop_machines` is set to `false` (or `min_machines_running` is set to `1`) so that the background thread has enough time to run Stockfish to completion without the machine going to sleep.
3. **Manually Force Re-Sweep**: Call the startup sweep logic manually via a script if needed, or invoke the retry API route:
   ```bash
   curl -X POST https://api.grandmate.dev/api/v1/analysis/jobs/<job-id>/retry \
     -H "Authorization: Bearer <token>"
   ```

---

## Incident 3: Infinite 401 Unauthorized Loop at Login

### Symptom
Users authenticate via Lichess/Chess.com OAuth. The login endpoint responds with a 200 OK and a `Set-Cookie` header, but every subsequent request to `/auth/me` or `/profiles` returns `401 Unauthorized`.

### Cause
Cross-origin cookie block. The frontend is hosted on Vercel (`*.vercel.app`) and the backend is on Fly.io (`*.fly.dev`). Since both domains reside on the Public Suffix List, the browser treats them as cross-site. If the cookie is configured as `SameSite=Lax`, the browser will refuse to attach the cookie to cross-origin API calls.

### Resolution
1. **Primary Solution (Custom Domain)**: Set up a shared custom domain (e.g., `app.grandmate.dev` for frontend, `api.grandmate.dev` for backend) to make them Same-Site.
2. **Alternative Solution (Cross-Site Cookie)**: If custom domains are unavailable, override settings to set `SameSite=None` with `Secure`:
   - Set environment variable `SESSION_COOKIE_SAMESITE=none` (ensure `SESSION_COOKIE_SECURE=true` is also set).
   - Re-deploy the backend container.

---

## Incident 4: LLM Requests Failing due to Token Budget Exhaustion

### Symptom
API endpoints related to chat or report generation return `429 Too Many Requests` or return fallback deterministic reports, logging `daily_token_ceiling_exceeded`.

### Cause
The daily LLM token budget limit defined by `LLM_DAILY_TOKEN_CEILING` (default `500000`) has been exceeded.

### Resolution
1. **Check Budget Status**: Query the database to inspect the `llm_usage` tracking table for the current date.
2. **Temporary Budget Increase**: If the usage is legitimate, increase the daily ceiling value in the environment:
   ```bash
   fly secrets set LLM_DAILY_TOKEN_CEILING=1000000
   ```
3. **Check for Graph Loops**: Inspect LangSmith traces to check if a user request caused the multi-agent graph to loop indefinitely, burning tokens.

---

## Incident 5: Database Connection Timeout or pgvector Query Latency

### Symptom
Slow request times on `/chat` and `/reports` endpoints, with database query time warnings in logs.

### Cause
Vector search over the knowledge corpus or user memory using cosine distance is scanning the tables sequentially because no index exists, or the connection pool is exhausted.

### Resolution
1. **Connection Pool Adjustments**: Increase `DATABASE_POOL_SIZE` (default 5) and `DATABASE_MAX_OVERFLOW` (default 10) in settings if connection timeouts occur.
2. **Index pgvector Columns**: Ensure an HNSW or IVFFlat index is created on the vector columns:
   ```sql
   CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
   ```
3. **Analyze Connections**: Check active PG connections:
   ```sql
   SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   ```
