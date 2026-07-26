# Configuration and Secrets Contract

The project owner was explicit: **no hardcoded keys, no hardcoded constants.** This
document is the contract that makes that enforceable rather than aspirational.

## Rules

1. Every secret and every tunable lives in `.env`.
2. The backend reads it through a single typed `pydantic-settings` module. No
   `os.environ` access scattered through domain code.
3. The frontend reads only `VITE_`-prefixed public values. Secrets never reach the browser.
4. `.env.example` is committed with every key listed and every secret blank.
5. `.env` is gitignored and never committed.
6. A literal number in a code path that a reviewer would ask "why that value?" about is a
   configuration item, not a constant.
7. Claude never prints a real secret to the terminal, logs, or documentation.
8. Claude never invents a placeholder key value that fails confusingly at runtime. It asks
   the owner to populate `.env` and waits.

## Why this is strict

The reference application hardcoded its engine depth default in `.env.example` but read
severity thresholds in more than one place. That is exactly how a system ends up producing
two different blunder classifications depending on which code path ran. Centralising the
read is the fix, and it is cheap to do at Phase 1 and expensive to retrofit at Phase 8.

## Backend environment variables

### Application
| Key | Default | Notes |
|-----|---------|-------|
| `APP_ENV` | `development` | `development` \| `test` \| `production` |
| `LOG_LEVEL` | `INFO` | |
| `API_PORT` | `8000` | |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma separated |

### Supabase
| Key | Default | Notes |
|-----|---------|-------|
| `SUPABASE_URL` | — | Local CLI URL in development |
| `SUPABASE_ANON_KEY` | — | Secret |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Secret. Backend only, never exposed |
| `DATABASE_URL` | — | Direct Postgres connection for migrations |

### Identity
| Key | Default | Notes |
|-----|---------|-------|
| `LICHESS_CLIENT_ID` | `grandmate-v2` | Public client; self-chosen, no secret needed |
| `LICHESS_REDIRECT_URI` | `http://localhost:5173/auth/callback` | |
| `LICHESS_SCOPES` | `email:read,preference:read` | Minimal by default |
| `SESSION_JWT_SECRET` | — | Secret. Signs backend-issued session tokens |
| `SESSION_TTL_SECONDS` | `604800` | |

### Engine
| Key | Default | Notes |
|-----|---------|-------|
| `STOCKFISH_PATH` | `/usr/local/bin/stockfish` | Verified present on this machine |
| `ENGINE_DEPTH` | `12` | Baseline sweep depth, per D-010 |
| `ENGINE_DEEP_DEPTH` | `18` | Deep pass on critical moments only |
| `ENGINE_THREADS` | `1` | Determinism requires pinning this |
| `ENGINE_HASH_MB` | `128` | |
| `ENGINE_TIMEOUT_S` | `30` | Per position |
| `INACCURACY_CP` | `50` | |
| `MISTAKE_CP` | `100` | |
| `BLUNDER_CP` | `300` | |
| `CRITICAL_SWING_CP` | `150` | Threshold for deep re-analysis |

`ENGINE_THREADS=1` is not arbitrary. Multi-threaded Stockfish is non-deterministic across
runs, and the Phase 5 exit criteria require reproducible classifications.

### LLM
| Key | Default | Notes |
|-----|---------|-------|
| `LLM_PROVIDER` | `openai` | Selects the adapter |
| `LLM_MODEL` | `gpt-4o-mini` | Per D-005 |
| `OPENAI_API_KEY` | — | Secret. Owner supplies at Phase 1 |
| `LLM_TEMPERATURE` | `0.2` | Low; this is an explanation system |
| `LLM_MAX_TOKENS` | `2000` | |
| `LLM_REQUEST_TIMEOUT_S` | `60` | |
| `LLM_DAILY_TOKEN_CEILING` | — | Hard guardrail; value pending Q-4 |

### Embeddings and retrieval
| Key | Default | Notes |
|-----|---------|-------|
| `EMBED_MODEL` | `text-embedding-3-small` | |
| `EMBED_DIMENSIONS` | `1536` | Must match the pgvector column |
| `CHUNK_SIZE_TOKENS` | `512` | Per-bucket overrides allowed |
| `CHUNK_OVERLAP_TOKENS` | `64` | |
| `RETRIEVAL_TOP_K` | `8` | |
| `RETRIEVAL_FUSION_K` | `60` | Reciprocal rank fusion constant |
| `RETRIEVAL_MIN_SCORE` | `0.0` | |

### Agents
| Key | Default | Notes |
|-----|---------|-------|
| `AGENT_MAX_STEPS` | `8` | Loop protection |
| `AGENT_MAX_TOOL_CALLS` | `12` | |
| `AGENT_TOKEN_BUDGET` | `20000` | Per conversation turn |

### Ingestion
| Key | Default | Notes |
|-----|---------|-------|
| `MAX_PGN_UPLOAD_MB` | `10` | |
| `MAX_GAMES_PER_IMPORT` | `60` | Matches the largest aggregate window |
| `LICHESS_RATE_LIMIT_RPS` | `1` | Conservative; be a good API citizen |
| `CHESSCOM_RATE_LIMIT_RPS` | `1` | |

### Developer insight (ADR-0013)
| Key | Default | Notes |
|-----|---------|-------|
| `DEV_INSIGHT_ENABLED` | `true` | Records span names, timings, counts, token usage. Forced off in production. |
| `DEV_INSIGHT_CAPTURE_PROMPTS` | `false` | Captures prompt and context **text**. Off everywhere by default; forced off in production regardless of value. |
| `DEV_INSIGHT_MAX_TRACES` | `50` | Ring buffer size |
| `DEV_INSIGHT_MAX_SPANS_PER_TRACE` | `200` | Guards against a runaway agent loop |

Both switches are hard-gated in production by `Settings.dev_insight_active` and
`Settings.dev_insight_capture_sensitive`. The trace routes are unauthenticated until
Phase 2 adds auth, and prompt text can contain a user's game history — so the environment
is not permitted to opt into either.

Recording never calls a model and never runs a tokenizer. Token counts come from the
provider's own response.

### Evaluation
| Key | Default | Notes |
|-----|---------|-------|
| `RAGAS_FAITHFULNESS_THRESHOLD` | `0.85` | Gating |
| `RAGAS_ANSWER_ACCURACY_THRESHOLD` | `0.80` | Gating |
| `RAGAS_CONTEXT_PRECISION_THRESHOLD` | `0.75` | |
| `RAGAS_CONTEXT_RECALL_THRESHOLD` | `0.75` | |
| `EVAL_RUN_DIR` | `evals/runs` | |

## Frontend environment variables

| Key | Notes |
|-----|-------|
| `VITE_API_BASE_URL` | Backend origin |
| `VITE_LICHESS_CLIENT_ID` | Public by design |
| `VITE_LICHESS_REDIRECT_URI` | |

Nothing secret appears here. If a value needs protecting, it belongs behind the backend.

## When the owner must act

| Moment | Action needed |
|--------|--------------|
| Phase 1, backend scaffold lands | Add `OPENAI_API_KEY` to `backend/.env`; confirm `gpt-4o-mini`; set `LLM_DAILY_TOKEN_CEILING` |
| Phase 2, Supabase setup | Supply `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` |
| Phase 2, Lichess app | Confirm the registered redirect URI |

Claude will prompt at each of these points rather than proceeding with broken defaults.
