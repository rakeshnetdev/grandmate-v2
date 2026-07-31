# Release Checklist — GrandMate

This checklist must be executed and fully checked off prior to promoting the GrandMate platform from Beta to public Production release.

---

## 1. Environment & Infrastructure Setup

- [ ] **Secrets Provisioning**: Confirm all secrets are securely injected into the hosting platform (e.g. Fly.io Secrets):
  * `DATABASE_URL` (direct asyncpg/psycopg connection string, not transaction-pooled).
  * `OPENAI_API_KEY` (active production API key).
  * `SESSION_JWT_SECRET` (minimum 32-byte secure random string).
- [ ] **Config Audits**: Validate settings:
  * `APP_ENV=production` is set (disables devinsight middleware, turns on secure cookies).
  * `CORS_ALLOWED_ORIGINS` strictly names the Vercel production origin (no wildcards).
  * `LLM_DAILY_TOKEN_CEILING` set to the production spend ceiling limit (e.g. `1000000` tokens).
- [ ] **Docker Sizing**:
  * Persistent volume `grandmate_storage` is successfully provisioned and mounted at `/app/.storage`.
  * RAM allocated is at least **1.5 GB** (preferably **2 GB**) to handle Stockfish hash tables comfortably without OOM crashes.

---

## 2. Database & Vector Migrations

- [ ] **Schema Current**: Run migrations up to head:
  * Run `alembic upgrade head`.
  * Verify `alembic_version` matches head in the production database.
- [ ] **Vector Extension**: Confirm `pgvector` extension is enabled on the target database (`CREATE EXTENSION IF NOT EXISTS vector`).
- [ ] **Indexes Configured**: Verify that HNSW/IVFFlat indexes are active on vector columns to ensure low retrieval latency under load.

---

## 3. Core Capability Verification

- [ ] **Opening Dataset Present**: Ensure `data/openings/dist/all.tsv` exists in the container image and has been verified by the server starting without raising `OpeningDatasetError`.
- [ ] **Knowledge Base Ingestion**: Execute the one-shot corpus ingestion script against the production database:
  * Command: `uv run python -m scripts.ingest_corpus`
  * Verify that `search_knowledge` queries return valid citable strategy and tactics results.

---

## 4. End-to-End Walkthrough Checks

- [ ] **PGN Import**: Paste a PGN, import it, and confirm the job status transitions to `done` within seconds.
- [ ] **Opening & Tag Detection**: Verify the imported game is labeled with the correct ECO name and tactical motif tags (e.g. pin, fork).
- [ ] **Persona Validation**: View the game report, cycle through `self_learner`, `coach`, and `kid` personas, and verify the phrasing changes dynamically.
- [ ] **Agentic Chat Grounding**:
  * Ask: *"what was my opening here?"* (requires retrieval of game analysis).
  * Ask: *"why did I lose material?"* (requires analysis + LLM coaching explanation).
  * Verify that citations are generated and no hallucinated moves are introduced.

---

## 5. Security & Privacy Gating

- [ ] **Secure LangSmith Redaction**: With `LANGSMITH_CAPTURE_PROMPTS=false`, verify that traces submitted to LangSmith do not contain raw game moves, prompts, or reply strings.
- [ ] **Non-Root Execution**: Confirm the Docker container runs under the non-privileged `grandmate` user context.
- [ ] **Rate Limiting**: Hit the server with rapid requests and verify that client IP sliding-window rate limit returns `HTTP 429` as expected.
