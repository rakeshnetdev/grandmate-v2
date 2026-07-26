# Data Model Draft

Phase 0 draft. Implemented as migrations in Phase 2 and extended per phase. Every schema
change ships as a migration with a rollback plan.

## Storage boundaries

Three storage models that must never be collapsed into one, per the memory rules in
`claude.md`:

1. **Analysis truth** — Postgres tables. Deterministic, reproducible, engine-derived.
2. **Short-term thread state** — LangGraph checkpointer. Ephemeral, thread-scoped.
3. **Long-term profile memory** — LangGraph store plus an audited Postgres mirror.

The Postgres mirror of long-term memory exists so the user can see and delete what is
remembered. A memory the user cannot inspect is a memory the user cannot trust.

---

## Identity and profiles

### `users`
The authenticated account.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `lichess_id` | text unique | Lichess account id from OAuth |
| `lichess_username` | text | Display name, may change upstream |
| `email` | text null | Only if `email:read` scope granted |
| `created_at` / `last_login_at` | timestamptz | |

### `profiles`
A player identity that can be analysed. Distinct from `users`: one account may hold
several profiles, and an observed opponent has a profile but no account.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `owner_user_id` | uuid FK → users | Who created it |
| `kind` | enum | `self` \| `child` \| `student` \| `opponent` \| `shared` |
| `display_name` | text | |
| `default_persona` | enum | `self_learner` \| `coach` \| `kid` |
| `created_at` | timestamptz | |

A user's own profile is created automatically at first login with `kind = 'self'`.

### `profile_sources`
Links a profile to platform accounts. A profile may have both.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `profile_id` | uuid FK | |
| `source` | enum | `lichess` \| `chesscom` \| `upload` |
| `source_username` | text | |
| `verified` | boolean | True for OAuth-derived, false for claimed usernames |
| `verification_method` | text null | |

The `verified` flag matters: a claimed Chess.com username is unverified by default, and
unverified sources must not be presented as authoritatively belonging to the user.

### `profile_relationships`
Who may view whom, and in what role. This table is the permission gate for the
view-another-player page.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `viewer_user_id` | uuid FK | |
| `subject_profile_id` | uuid FK | |
| `role` | enum | `owner` \| `coach` \| `parent` \| `viewer` \| `student` |
| `granted_at` / `revoked_at` | timestamptz | Soft revocation preserves audit history |

---

## Games and analysis

### `games`
| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `profile_id` | uuid FK | The focus player |
| `source` | enum | |
| `source_game_ref` | text null | Platform game id |
| `content_hash` | text | Dedup key over normalised movetext |
| `headers` | jsonb | Raw PGN headers |
| `focus_color` | enum | `white` \| `black` |
| `opponent_name` | text | |
| `time_control` | text | |
| `played_at` | timestamptz | |
| `raw_pgn_path` | text | Supabase Storage path |

Unique constraint on `(profile_id, content_hash)` — this is what makes re-import
idempotent across upload, Lichess, and Chess.com.

### `game_moves`
| Column | Type | Notes |
|--------|------|-------|
| `game_id` | uuid FK | |
| `ply` | int | Zero-indexed |
| `san` / `uci` | text | |
| `fen_before` / `fen_after` | text | |
| `epd_after` | text | Indexed; opening lookup key |
| `clock_ms` | int null | Where the source provides it |

Primary key `(game_id, ply)`.

### `game_analysis`
One row per game per analysis version, so re-analysis under new settings is additive
rather than destructive.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `game_id` | uuid FK | |
| `analysis_version` | text | Engine + policy + detector version |
| `engine_depth` | int | Recorded, not assumed |
| `summary` | jsonb | Accuracy, counts by classification |
| `completed_at` | timestamptz | |

### `move_evaluations`
| Column | Type | Notes |
|--------|------|-------|
| `game_analysis_id` | uuid FK | |
| `ply` | int | |
| `eval_cp` | int null | Null when mate score present |
| `mate_in` | int null | |
| `best_move_uci` | text | |
| `pv` | text[] | |
| `classification` | enum | See glossary |
| `eval_swing_cp` | int | |
| `is_critical_moment` | boolean | |
| `deep_analyzed` | boolean | Whether the tiered deep pass ran here |

### `game_openings`
| Column | Type | Notes |
|--------|------|-------|
| `game_id` | uuid FK | |
| `eco` | text | |
| `opening_name` | text | |
| `matched_ply` | int | Depth of the deepest EPD match |

### `game_tactics` / `game_strategy_tags`
| Column | Type | Notes |
|--------|------|-------|
| `game_analysis_id` | uuid FK | |
| `ply` | int | Ply range start for strategy tags |
| `label` | text | From the taxonomy in `glossary.md` |
| `confidence` | numeric | 0–1 |
| `evidence` | jsonb | Squares, pieces, engine corroboration |

`evidence` is not decoration. It is what the grounding guardrail checks an LLM claim
against, and what a reviewer reads when a detector misfires.

---

## Aggregation

### `profile_aggregates`
| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `profile_id` | uuid FK | |
| `window_size` | int | 10, 30, 60 |
| `segment` | jsonb | Colour, time control filters |
| `metrics` | jsonb | Computed rollups |
| `sample_size` | int | Actual games, may be below `window_size` |
| `aggregate_version` | text | |
| `computed_at` | timestamptz | |

`sample_size` is stored separately from `window_size` so the UI can suppress confident
claims on thin samples rather than implying thirty games of evidence when there are four.

### `training_plans`
| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `profile_id` | uuid FK | |
| `source_aggregate_id` | uuid FK | Traceability back to evidence |
| `themes` | jsonb | |
| `created_at` | timestamptz | |

---

## Knowledge and retrieval

### `corpus_documents`
| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `bucket` | enum | `rules` \| `openings` \| `tactics` \| `strategy` \| `analysis` |
| `title` | text | |
| `source_url` | text null | |
| `license` | text | Required. No licence, no ingestion. |
| `retrieved_at` | timestamptz | |
| `reviewed_by` | text | Required before the document goes live |
| `corpus_version` | text | |

### `corpus_chunks`
| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `document_id` | uuid FK | |
| `bucket` | enum | Denormalised for filter performance |
| `profile_id` | uuid null | Non-null only for the `analysis` bucket |
| `content` | text | |
| `metadata` | jsonb | |
| `embedding` | vector | pgvector |
| `tsv` | tsvector | Sparse retrieval index |

`profile_id` on the chunk is the isolation mechanism. Every retrieval against the
`analysis` bucket filters on it at the retriever interface, so no caller can forget.

---

## Chat and memory

### `chat_threads`
`id`, `user_id`, `profile_id`, `persona`, `active_game_id`, `created_at`.

### `chat_messages`
`id`, `thread_id`, `role`, `content`, `tool_calls` jsonb, `citations` jsonb, `created_at`.

`citations` records which analysis rows and corpus chunks backed the answer. This is what
makes an answer auditable after the fact.

### `long_term_memory`
Audited mirror of the LangGraph store.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `profile_id` | uuid FK | Scoping boundary |
| `kind` | enum | `preference` \| `goal` \| `recurring_finding` \| `coach_note` |
| `content` | text | |
| `confidence` | numeric | |
| `source_message_id` | uuid null | Provenance |
| `created_at` / `superseded_at` | timestamptz | Supersede rather than overwrite |

Superseding rather than overwriting means a wrong memory can be traced and explained
instead of silently vanishing.

---

## Operations

### `jobs`
`id`, `kind`, `profile_id`, `status`, `progress`, `idempotency_key`, `error` jsonb,
`created_at`, `completed_at`.

### `audit_events`
`id`, `actor_user_id`, `action`, `subject_type`, `subject_id`, `metadata` jsonb,
`created_at`.

Cross-profile access and memory writes both emit audit events.

### `eval_runs`
`id`, `suite`, `dataset_version`, `model_version`, `prompt_version`, `retriever_version`,
`scores` jsonb, `passed` boolean, `run_at`.

This table is the score ledger required by the RAGAS rules. Evaluation that is not
recorded here did not happen.
