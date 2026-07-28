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
| `API_HOST` | `127.0.0.1` | Bind address for `python -m app`. Containers override to `0.0.0.0` |
| `API_PORT` | `7575` | Applied by `python -m app`; the bare `uvicorn` CLI ignores it |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3535` | Comma separated |

### Supabase
| Key | Default | Notes |
|-----|---------|-------|
| `SUPABASE_URL` | — | Local CLI URL in development |
| `SUPABASE_ANON_KEY` | — | Secret |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Secret. Backend only, never exposed |
| `DATABASE_URL` | — | Direct Postgres connection for migrations |

### Identity
MVP login is username-claim, not OAuth (ADR-0014, deferring ADR-0007's Lichess PKCE) —
there is no client id, redirect URI, or scope list to configure yet.

| Key | Default | Notes |
|-----|---------|-------|
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
| `ENGINE_MAX_CONCURRENT_GAMES` | `4` | Background analysis jobs run at once (Phase 5) |
| `INACCURACY_CP` | `50` | |
| `MISTAKE_CP` | `100` | |
| `BLUNDER_CP` | `300` | |
| `CRITICAL_SWING_CP` | `150` | Threshold for deep re-analysis |

`ENGINE_THREADS=1` is not arbitrary. Multi-threaded Stockfish is non-deterministic across
runs, and the Phase 5 exit criteria require reproducible classifications.
`ENGINE_MAX_CONCURRENT_GAMES` is where parallelism lives instead: several single-threaded
Stockfish processes running different games at once, confirmed with the owner in Phase 5
after benchmarking real per-game analysis time (~7s sequential per game at this machine's
speed).

### Pattern intelligence (Phase 6)
| Key | Default | Notes |
|-----|---------|-------|
| `OPENINGS_DATA_DIR` | `data/openings/dist` | Directory holding `all.tsv`, the vendored, cross-volume-deduplicated Lichess dataset, EPD-keyed (D-011, ADR-0009) |
| `MOTIF_HANGING_PIECE_MIN_VALUE_CP` | `300` | Below this, a hanging piece is common/intentional (e.g. a pawn) and not flagged |
| `MOTIF_FORK_MIN_TARGET_VALUE_CP` | `300` | Minimum value of a forked piece to count as a target |
| `THEME_OPENING_PHASE_PLY_CUTOFF` | `20` | Where "the opening" ends, for development-lag purposes |
| `THEME_BAD_BISHOP_MIN_FIXED_PAWNS` | `3` | Own fixed pawns on the bishop's colour needed to call it "bad" |
| `THEME_PASSED_PAWN_PERSIST_PLIES` | `4` | A passed pawn must survive this long to count as "created" |
| `THEME_PIECE_ACTIVITY_WINDOW_PLIES` | `10` | Averaging window for the mobility-differential theme |
| `THEME_SPACE_ADVANTAGE_MIN_RANK_DIFFERENTIAL` | `2` | Minimum sustained advancement differential |
| `THEME_TIME_TROUBLE_CLOCK_MS_THRESHOLD` | `30000` | Clock remaining under which a position is "time trouble" |
| `THEME_TIME_TROUBLE_ACCURACY_DROP_PCT` | `20.0` | Accuracy drop, time-trouble phase vs. rest of game, to call it a "collapse" |
| `PATTERN_MIN_CONFIDENCE_TO_PERSIST` | `0.0` | Findings below this confidence are computed but not stored |

Piece values used for material comparisons (pawn/knight/bishop/rook/queen) are **not**
configuration — they are standard chess facts, not a product policy, and live as a
documented constant in `domain/patterns`. Rule 11 targets policy thresholds ("how much is
enough to flag"), not universal domain facts.

### LLM
| Key | Default | Notes |
|-----|---------|-------|
| `LLM_PROVIDER` | `openai` | Selects the adapter |
| `LLM_MODEL` | `gpt-4o-mini` | Per D-005 |
| `OPENAI_API_KEY` | — | Secret. Owner supplies at Phase 1 |
| `LLM_TEMPERATURE` | `0.2` | Low; this is an explanation system |
| `LLM_MAX_TOKENS` | `2000` | |
| `LLM_REQUEST_TIMEOUT_S` | `60` | |
| `LLM_DAILY_TOKEN_CEILING` | `500000` | Hard guardrail (Phase 9, D-022 — Q-4 resolved). Soft-overflow, hard-stop-next: an in-flight call finishes, the next one falls back to the deterministic report instead. Blank = uncapped |

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
| `CORPUS_DATA_DIR` | `data/corpus` | Curated source documents, chunked and embedded at ingestion (Phase 7) |
| `RETRIEVAL_BM25_K1` | `1.5` | BM25 term-frequency saturation |
| `RETRIEVAL_BM25_B` | `0.75` | BM25 length normalisation |

### Profile analytics (Phase 8)
| Key | Default | Notes |
|-----|---------|-------|
| `ANALYTICS_WINDOW_SIZES` | `10,30,60` | Comma-separated; the only window sizes `/analytics/profile?window=` accepts |
| `ANALYTICS_DEFAULT_WINDOW` | `10` | Used when `window` is omitted |
| `ANALYTICS_MIN_GAMES_FOR_TREND` | `5` | Below this, trends/weaknesses are computed but flagged `sufficient_sample=False` rather than asserted |
| `ANALYTICS_WEAKNESS_MIN_OCCURRENCE_RATE` | `0.3` | Share of a window's games a motif/theme must recur in (against the player) to count as a recurring weakness |
| `TIME_CONTROL_BULLET_MAX_S` | `180` | Estimated game duration (`base + 40*increment`) ceiling for the bullet bucket |
| `TIME_CONTROL_BLITZ_MAX_S` | `480` | Same, blitz |
| `TIME_CONTROL_RAPID_MAX_S` | `1500` | Same, rapid; above this is classical |

### Persona reports (Phase 9, `persona-matrix.md`)
| Key | Default | Notes |
|-----|---------|-------|
| `REPORT_SELF_LEARNER_MAX_FINDINGS` | `5` | Self-learner persona's finding cap |
| `REPORT_KID_MAX_FINDINGS` | `3` | Kid persona's finding cap |
| `REPORT_KID_MIN_CONFIDENCE_TO_SHOW` | `0.6` | Below this, a finding is suppressed entirely for the kid persona, not softened — persona-matrix.md's safety rules |

Coach has no cap (`persona-matrix.md` states it as unbounded), so there is no
corresponding setting.

### Agents
Declared at Phase 1, enforced starting Phase 10 — the chat agent loop
(`orchestration/graphs/chat.py`) is the first thing that actually reads these.

| Key | Default | Notes |
|-----|---------|-------|
| `AGENT_MAX_STEPS` | `8` | Loop protection — bounds tool-calling iterations plus answer attempts combined, one chat turn |
| `AGENT_MAX_TOOL_CALLS` | `12` | Per turn; a call past this returns an error result to the model rather than dispatching |
| `AGENT_TOKEN_BUDGET` | `20000` | Per turn; exceeding it stops the loop and falls back to a deterministic answer, same as exhausting `LLM_DAILY_TOKEN_CEILING` mid-turn |

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

Nothing secret appears here. If a value needs protecting, it belongs behind the backend.

## When the owner must act

| Moment | Action needed |
|--------|--------------|
| Phase 1, backend scaffold lands | Add `OPENAI_API_KEY` to `backend/.env`; confirm `gpt-4o-mini` |
| Phase 2 | `docker compose up -d postgres` (ADR-0015); set `SESSION_JWT_SECRET` to a random string |
| Phase 9, first real completion spend | `LLM_DAILY_TOKEN_CEILING` set — D-022, default `500000`, adjust if the real spend rate warrants it |
| Before any private-data feature | Implement real Lichess OAuth2 PKCE (ADR-0007/ADR-0014) |

Claude will prompt at each of these points rather than proceeding with broken defaults.
