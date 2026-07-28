# GrandMate Project Plan

## Overview

GrandMate is a modular chess analysis and coaching platform that ingests single PGNs, bulk PGNs, and recent game histories from Lichess and Chess.com, enriches each game into a canonical analysis object, aggregates recurring patterns into player profiles, and exposes persona-aware chat on top of those results. Lichess supports programmatic user-game export with filtering such as color and maximum count, and Chess.com provides a read-only public API for published player and game archive data, which makes the multi-source ingestion model feasible.[cite:393][cite:423][cite:396]

The product is intentionally designed as a companion layer rather than a replacement for playing platforms. Its unique value is persistent memory, persona-aware coaching, and structured explanation over deterministic engine-backed analysis rather than raw engine output alone.

Architecturally, GrandMate is an **agentic RAG system built on a deterministic chess
core**. Those two halves have different failure modes and are engineered differently. The
chess core must be reproducible, testable, and boring. The agent layer must be grounded,
observable, and evaluated continuously. The core computes what is true about a game; the
agent decides what to retrieve, how to explain it, and to whom. Neither is allowed to do
the other's job.

## Product Definition

### What is being built

A distributed application with separate frontend and backend that:
- Accepts uploaded PGN files, pasted PGN text, batches of PGNs, and imported recent games from Lichess and Chess.com.[cite:393][cite:423]
- Parses each game into a normalized internal representation.
- Enriches every game with opening, engine, tactic, strategy, pattern, motif, and training metadata.
- Aggregates multiple games into profile-level patterns over configurable windows such as last 10, 30, or 60 games.
- Supports multiple personas over the same analysis core: self-learner, child, parent, coach, and analyst/opponent-prep.
- Provides chat over analysis with both short-term and long-term memory.
- Uses deterministic chess computation as the source of truth and the LLM as an explanation and interaction layer.

### Core product principle

Separate the system into three truth levels:
1. **Game Analysis Object** — one enriched object per game.
2. **Profile Aggregate Object** — trends and recurring patterns across multiple games.
3. **Persona View / Chat Layer** — different explanations and outputs over the same underlying analysis.

Personas should never alter chess truth. They should only affect language, depth, framing, and recommendations.

## High-Level Architecture

### Architectural goals

- Modular and loosely coupled services.
- Clear separation of frontend and backend.
- Feature-driven, component-based frontend.
- Domain-driven backend modules.
- Deterministic, testable analysis core.
- Replaceable LLM layer.
- Replaceable ingestion connectors.
- Strong observability, auditability, and incremental rollout.
- Phase gates with explicit user sign-off before moving ahead.

### Recommended stack

#### Frontend
- TypeScript
- React + Vite
- Tailwind CSS
- shadcn/ui component system
- TanStack Query for server state
- React Router
- Zod for runtime validation
- Zustand or lightweight feature-local stores where needed
- Feature-driven folder structure

#### Backend
- Python
- FastAPI
- LangGraph for orchestration and memory-aware chat flows
- Celery or Dramatiq for async workers, or Temporal later if workflow complexity grows
- python-chess for PGN parsing and board replay
- UCI integration with Stockfish for deterministic evaluation
- Pydantic for schemas

#### Data layer
- Supabase as the primary managed data platform: Postgres, Storage, optional Realtime, and backups are natively supported.[cite:422][cite:424][cite:425][cite:433]
- **pgvector in Postgres for semantic retrieval — required, not optional.** Retrieval is a core capability of this product.
- Redis for queues, caching, rate limiting, and ephemeral state
- Supabase Storage for uploaded PGNs, generated reports, artifacts, and optional cached exports

#### Retrieval and agent layer
- pgvector for dense retrieval
- BM25 for sparse retrieval, fused with dense results via reciprocal rank fusion
- Multi-bucket corpus with per-bucket chunking and retrieval strategy
- LangGraph for agent orchestration, checkpointing, and long-term stores
- MCP server exposing the same tools consumed by internal agents
- RAGAS for retrieval and answer quality evaluation

#### External integrations
- Lichess OAuth2 (Authorization Code + PKCE, public client) for login, and the Lichess API for user game export.[cite:393][cite:396]
- Chess.com PubAPI for published game archives and player data. Read-only and unauthenticated; OAuth login is approval-gated and out of MVP scope.[cite:423][cite:429]
- LLM provider abstraction, defaulting to `gpt-4o-mini`, so models can be swapped without touching domain code

### System boundaries

```text
Frontend (React/Vite)
  -> Backend API (FastAPI)
     -> Identity (Lichess OAuth PKCE) + DB / Storage (Supabase)
     -> Analysis Worker(s)
        -> PGN parser
        -> Engine analyzer (Stockfish/UCI)
        -> Pattern detectors
        -> Aggregation service
     -> Knowledge & Retrieval service
        -> corpus ingestion + chunking
        -> pgvector dense index + BM25 sparse index
        -> multi-bucket router (rules/openings/tactics/strategy/analysis)
     -> Agent layer (LangGraph)
        -> supervisor + specialised agents
        -> tools: retrieval, analysis lookup, move validation
        -> short-term checkpointer / long-term store
     -> MCP server (same tools, external clients)
     -> Integration connectors (Lichess / Chess.com)
```

The deterministic analysis path and the agent path are separate branches on purpose. The
agent reads analysis results; it never produces them.

### Service decomposition

#### 1. API Gateway / Backend App
Responsibilities:
- Auth context validation
- Request routing
- File upload initiation
- Job creation and status lookup
- Profile, report, chat, and memory APIs
- Response shaping for personas

#### 2. Ingestion Service
Responsibilities:
- Single PGN upload
- Bulk PGN upload
- Pasted PGN input
- Lichess import
- Chess.com import
- Source normalization
- Deduplication
- Metadata extraction

#### 3. Analysis Service
Responsibilities:
- Parse PGN
- Replay moves
- Produce FEN per ply
- Engine evaluation per key position or configurable depth schedule
- Opening detection and ECO tagging
- Move classification
- Critical moment extraction

#### 4. Pattern Intelligence Service
Responsibilities:
- Tactical motifs
- Strategic themes
- Recurrent mistakes
- Phase-of-game patterns
- Opening-family trends
- Candidate training themes
- Confidence scoring

#### 5. Profile Aggregation Service
Responsibilities:
- Aggregate across N recent games
- Trend generation
- Persona-neutral summaries
- Progress deltas
- Windowed stats such as last 10/30/60 games

#### 6. Memory & Chat Service
Responsibilities:
- Short-term thread memory via LangGraph checkpointers.[cite:407][cite:410]
- Long-term profile memory via LangGraph stores.[cite:407][cite:408][cite:411]
- Retrieval of game and profile context
- Persona formatting
- Controlled write-back of durable memory

#### 7. Report / Presentation Service
Responsibilities:
- Human-readable reports
- Training plans
- Coach summaries
- Kid-friendly summaries
- Exportable structured outputs

#### 8. Knowledge & Retrieval Service
Responsibilities:
- Corpus ingestion, chunking, and provenance tracking
- Embedding generation and vector index maintenance
- Dense, sparse, and hybrid retrieval behind one interface
- Multi-bucket routing driven by query intent
- Per-profile isolation of the `analysis` bucket
- Retrieval quality instrumentation feeding the evaluation harness

#### 9. Agent & MCP Service
Responsibilities:
- LangGraph supervisor and specialised agents
- Tool registry shared by internal agents and the MCP server
- Grounding guardrails and the critic verification pass
- Trajectory tracing, token accounting, and cost ceilings
- Permission-scoped tool execution

## Core Data Model

### Canonical Game Analysis Object

Each input game must become one canonical enriched object.

```json
{
  "game_id": "uuid",
  "source": "upload|lichess|chesscom",
  "source_game_ref": "string",
  "headers": {},
  "player_context": {
    "focus_profile_id": "uuid",
    "focus_player_name": "string",
    "color": "white|black",
    "opponent_name": "string"
  },
  "raw_pgn": "string",
  "moves": [],
  "positions": [],
  "opening": {},
  "engine": {},
  "tactics": [],
  "strategy": [],
  "patterns": [],
  "critical_moments": [],
  "training_themes": [],
  "summary": {},
  "analysis_version": "string"
}
```

### Recommended top-level entities

- `users`
- `profiles`
- `profile_relationships`
- `game_sources`
- `games`
- `game_moves`
- `game_positions`
- `game_analysis`
- `game_tactics`
- `game_strategy_tags`
- `game_patterns`
- `profile_aggregates`
- `training_plans`
- `chat_threads`
- `chat_messages`
- `short_term_thread_state`
- `long_term_profile_memory`
- `report_artifacts`
- `jobs`
- `audit_events`

### Profile model

A user can maintain multiple profiles:
- self profile
- child profile
- student profile
- opponent profile
- shared analysis profile

### Persona model

Use role + persona as separate concepts.

- **Role / relationship**: owner, coach, parent, viewer, student
- **Persona mode**: self-learner, kid, parent, coach, analyst

This allows one account to view the same profile through different output modes without duplicating analysis.

## Memory Architecture

### Memory layers

#### 1. Short-term memory
Thread-scoped memory for the current chat session, implemented with LangGraph checkpointers.[cite:407][cite:410]

Store:
- active profile
- active game(s)
- active report
- current persona mode
- recent user questions
- current comparison context

#### 2. Long-term memory
Cross-session memory for durable facts about a profile, implemented with LangGraph stores.[cite:407][cite:408][cite:411]

Store:
- explanation preferences
- recurring weaknesses
- recurring strengths
- preferred openings
- training goals
- coach notes
- parent-friendly progress highlights

#### 3. Analysis history
This is not chat memory; it is application truth.

Store:
- analyzed game records
- aggregates
- trend snapshots
- prior training plans
- prior generated reports

### Memory write policy

Do not write every message into durable memory. Only write:
- explicit user preferences
- stable profile facts
- confirmed learning goals
- validated recurring findings from aggregation
- role-specific notes approved by the user or coach

## Frontend Architecture

### Principles

- Feature-driven modules
- Shared design system
- Clear separation between UI components and feature logic
- Strong typing at boundaries
- No oversized page components
- Reusable chart and analysis visualizations
- Commented code with docstrings and rationale for non-obvious logic

### Suggested folder structure

```text
frontend/
  src/
    app/
      router/
      providers/
      layouts/
    shared/
      components/
      lib/
      hooks/
      types/
      utils/
      config/
    features/
      auth/
      profiles/
      imports/
      games/
      analysis/
      reports/
      chat/
      memory/
      coaching/
      settings/
    pages/
```

### Frontend feature modules

#### auth
- login
- signup
- session handling
- route guards

#### profiles
- create profile
- manage linked profiles
- select persona mode
- view profile summary

#### imports
- upload PGN
- paste PGN
- import from Lichess
- import from Chess.com
- import history and job status

#### games
- game list
- game detail
- move list
- position browser

#### analysis
- critical moments
- move classifications
- opening summary
- tactical motifs
- strategic themes

#### reports
- multi-game summaries
- training plans
- persona-specific report views

#### chat
- chat thread list
- thread view
- context badges
- answer panels linked to analysis

#### memory
- memory preferences
- coaching notes
- retained facts audit view

### Frontend engineering standards

- Type every API response with generated or shared schemas.
- Use co-located tests for components and feature hooks.
- No direct fetch calls inside presentation components.
- Centralize API client logic.
- Use optimistic UI only where low risk.
- Keep components under reasonable size; split when behavior grows.
- Comment all non-obvious hooks, state flows, and rendering conditions.

## Backend Architecture

### Principles

- Domain modules with explicit interfaces
- Clear separation between API, services, repositories, workers, and orchestration
- Idempotent jobs
- Configuration by environment variables
- Replaceable infrastructure adapters
- Rich logging and tracing
- Strong schema validation at all ingress and egress points

### Suggested folder structure

```text
backend/
  app/
    api/
      routes/
      dependencies/
    core/
      config/
      logging/
      security/
    domain/
      profiles/
      imports/
      games/
      analysis/
      patterns/
      aggregation/
      knowledge/        # corpus model, chunking policy, provenance
      retrieval/        # retriever interfaces, bucket routing, fusion
      reports/
      chat/
      memory/
    services/
    repositories/
    workers/
    integrations/
      lichess/
      chesscom/
      llm/
      engine/
      vectorstore/
    orchestration/
      graphs/           # LangGraph state graphs
      agents/           # agent definitions and tool bindings
      tools/            # tool implementations shared by agents and MCP
      jobs/
    mcp/                # MCP server exposing tools over the service layer
    schemas/
    tests/
```

Note that `orchestration/tools/` is deliberately shared between the LangGraph agents and
the MCP server. Both surfaces call the same tool implementations, which in turn call the
same services. A capability must never exist twice with two behaviours.

### Backend module responsibilities

#### domain/imports
- normalize source inputs
- define import job contracts
- deduplicate

#### domain/games
- PGN representation
- move and position models
- validation

#### domain/analysis
- engine requests
- evaluation policies
- move labeling
- critical moment policies

#### domain/patterns
- tactic detectors
- strategy detectors
- training theme mapping

#### domain/aggregation
- rollups
- trend scoring
- improvement heuristics

#### domain/chat
- prompt context builder
- persona transformation
- answer contracts

#### domain/memory
- short-term state model
- long-term memory model
- retention/write policies

## Supabase Usage Plan

Supabase is suitable as the primary managed database layer because each project gets a full Postgres database, while Auth, Storage, and Realtime are built on that database foundation.[cite:424][cite:425][cite:433]

### Use Supabase for
- Postgres primary DB
- pgvector indexes for the knowledge corpus
- Row-level security where appropriate
- Storage buckets for PGNs and exports
- Database backups and recovery
- Realtime only if later needed for job progress or collaborative coach views

### Do not use Supabase Auth as the login provider
This is a deliberate change from the original plan. Primary login is "Log in with
Lichess", and Supabase Auth has no Lichess provider. The backend therefore owns the
OAuth2 PKCE exchange, issues its own session token, and persists user records in Supabase
Postgres. Supabase remains the system of record for identity data; it is simply not the
authenticator. Rationale and the rejected alternatives are in
`final_docs/v2/adr/0007-identity-and-oauth-strategy.md`.

### Use custom backend alongside Supabase
A hybrid architecture with Supabase as the data layer and a custom backend for application logic is a sensible approach for this project because the system needs orchestration, engine analysis, background jobs, and LLM workflows beyond thin CRUD behavior.[cite:430][cite:422]

### Recommended DB approach
- Supabase Postgres as system of record
- Migrations managed in code
- Avoid pushing complex chess logic into DB functions unless needed for performance
- Use service role access only from backend services
- Never place engine or LLM secrets in the frontend

## External Data Source Plan

### Lichess
Lichess is both an identity provider and a game source.

- **Login**: OAuth2 Authorization Code with PKCE. Public client, so no client secret is
  needed and `client_id` is a self-chosen constant. Authorization endpoint
  `https://lichess.org/oauth`, token endpoint `https://lichess.org/api/token`. Requested
  scopes are kept minimal — `email:read` and `preference:read` — and expanded only if a
  feature genuinely requires it.
- **Games**: user game export endpoints with filters such as colour and maximum count,
  supporting NDJSON and JSON variants.[cite:393][cite:396]

### Chess.com
Chess.com is a game source only in MVP.

The Published-Data API is unauthenticated and read-only, covering player profiles, stats,
and monthly game archives.[cite:423][cite:429] Chess.com does operate an OAuth login
programme, but access is granted by application and approval, so it cannot be assumed
available. MVP links a Chess.com account by username and reads public archives. If OAuth
approval is later obtained, the connector interface allows promoting Chess.com to a login
provider without changing the profile model.

### Opening data
`lichess-org/chess-openings`, `dist/` TSVs with columns `eco`, `name`, `pgn`, `uci`, and
`epd`, released under CC0. The `epd` column is the lookup key: detection walks the played
positions, matches each EPD against the index, and keeps the deepest hit. This handles
transpositions correctly, which SAN prefix matching does not.

### Connector design
Each connector should implement a common interface:
- validate identity / handle configuration
- fetch recent games
- normalize result
- map source metadata
- persist raw payload optionally for debugging

## Phase-by-Phase Delivery Plan

> **Revision note (Phase 0, locked).** The phase list below supersedes the original
> 15-phase sequence. Three new phases were inserted (Knowledge Corpus & RAG Foundation,
> MCP Server & Tool Interface, Multi-Agent Orchestration) and the evaluation phase was
> expanded to cover synthetic data, golden sets, and fine-tuning. See
> `final_docs/v2/adr/0008-agentic-rag-architecture.md` for the rationale and
> `final_docs/v2/phase-map.md` for the old-to-new phase mapping.

Every phase must end with:
1. implementation complete,
2. tests passing,
3. evaluation completed and **scores recorded** (from Phase 7 onward),
4. architecture review notes updated,
5. explicit user sign-off,
6. only then permission to continue.

### Phase index

| # | Phase | Status |
|---|-------|--------|
| 0 | Discovery and Decision Baseline | complete |
| 1 | Engineering Foundation | complete, pending sign-off |
| 2 | Supabase Foundation and Identity | pending |
| 3 | Ingestion MVP (PGN upload / paste / batch) | pending |
| 4 | Parsing and Canonical Game Object | pending |
| 5 | Engine Analysis Core | pending |
| 6 | Opening Detection and Chess Intelligence Tags | pending |
| 7 | Knowledge Corpus and RAG Foundation **(new)** | pending |
| 8 | Multi-Game Aggregation and Profile Analytics | pending |
| 9 | Persona Layer and Report Generation | pending |
| 10 | Agentic RAG Chat with Short-Term Memory | pending |
| 11 | Long-Term Memory and Profile-Aware Chat | pending |
| 12 | MCP Server and Tool Interface **(new)** | pending |
| 13 | Multi-Agent Orchestration **(new)** | pending |
| 14 | Lichess and Chess.com Game Import Connectors | pending |
| 15 | Training Plan and Coaching Recommendations | pending |
| 16 | Evaluation, Synthetic Data, Golden Sets, Fine-Tuning **(expanded)** | pending |
| 17 | Observability, Security, and Production Hardening | pending |
| 18 | Beta Rollout and Evaluation Loop | pending |

### Evaluation cadence

RAGAS and grounding evaluation is not deferred to a single phase. The harness is built
early and extended as capability lands. Every run writes a scored record to
`evals/runs/` — no informal, discarded evaluation.

| Phase | Evaluation added | Primary metrics |
|-------|------------------|-----------------|
| 4 | Parser correctness suite | parse success rate, replay consistency |
| 5 | Engine determinism suite | classification stability, legal-line validity |
| 6 | Detector precision suite | motif precision/recall vs labelled set |
| 7 | **RAGAS retrieval harness** | Context Precision, Context Recall |
| 9 | Persona fidelity suite | fact-invariance across personas |
| 10 | **RAGAS answer harness** | Faithfulness, Response Relevancy, grounding |
| 11 | Memory quality suite | retention precision, cross-profile isolation |
| 13 | Multi-agent trajectory eval | tool-choice accuracy, handoff correctness |
| 16 | Full suite + golden sets + fine-tuning gate | all of the above, versioned and trended |

---

## Phase 0 — Discovery and Decision Baseline

### Goal
Freeze scope, non-functional requirements, interfaces, and unresolved decisions before
implementation.

### Deliverables
- Product requirements document
- Architecture decision record set
- Domain glossary including starter motif and strategy taxonomies
- Data model draft
- Persona matrix
- Configuration and secrets contract
- RAG and agent architecture note
- Evaluation strategy note
- Success metrics definition
- Risk register
- Definition of done for all later phases
- Reuse ledger seeded for `grandmate/` ports

### Decisions confirmed by user
All Phase 0 blocking decisions are recorded in `final_docs/v2/decisions-log.md`.

### Tests / validation
- Completeness checklist
- Walkthrough of all user journeys
- Architecture review against the non-negotiable rules in `claude.md`

### Exit criteria
- No major open product ambiguity remains
- User signs off

---

## Phase 1 — Engineering Foundation

### Goal
Set up a maintainable monorepo with hard boundaries between backend and frontend.

### Deliverables
- `grandmate-v2/backend` and `grandmate-v2/frontend` with independent toolchains
- branch strategy and conventional commits
- linting, formatting, type checking on both sides
- test frameworks wired
- pre-commit hooks
- **configuration module: every tunable and secret read from `.env`, zero hardcoded constants**
- `backend/.env.example` and `frontend/.env.example`
- CI pipelines for frontend and backend
- containerised dev environment
- ADR template in use
- issue and PR templates

### Frontend tasks
- Vite React TypeScript scaffold
- Tailwind + shadcn/ui install
- app shell, routing, providers
- feature folder template
- typed API client scaffold

### Backend tasks
- FastAPI scaffold managed with `uv`
- pydantic-settings config module
- health and readiness endpoints
- domain module template
- worker scaffold
- LangGraph integration skeleton

### Testing
- FE: Vitest + React Testing Library smoke tests
- BE: Pytest + API smoke tests
- CI must fail on lint, type, or test failure

### Exit criteria
- `uv run` starts the backend and `npm run dev` starts the frontend reliably
- CI green
- Sign-off from user

---

## Phase 2 — Supabase Foundation and Identity

### Goal
Establish the persistent system of record and the chess-platform identity model.

### Deliverables
- local Postgres 17 with pgvector, one container (ADR-0015 — Supabase deferred to Phase 17)
- schema migration baseline
- **Lichess OAuth2 Authorization Code + PKCE login**
- **Chess.com account linking by username** (see identity note below)
- backend-issued session JWT and dependency-injected auth context
- user, profile, and profile-relationship tables
- storage behind a `StorageBackend` interface, filesystem implementation for MVP
- local seed data

### Identity note
Lichess supports public-client OAuth2 with PKCE, so "Log in with Lichess" is available
immediately. Chess.com's Published-Data API is unauthenticated and read-only, and its
OAuth login is an approval-gated partner programme. MVP therefore supports Chess.com as
a **linked username** rather than a login provider, with an optional ownership
verification step. If partner OAuth access is granted later, the connector interface
is designed so Chess.com can be promoted to a full login provider without reworking the
profile model. See `final_docs/v2/adr/0007-identity-and-oauth-strategy.md`.

### Tasks
- define initial schema and migration pipeline
- implement Lichess OAuth PKCE flow end to end
- implement Chess.com username link and verification
- issue and validate backend session tokens
- create storage buckets
- implement profile CRUD and the self / linked / observed profile distinction
- **implement the coach-student / parent-child linking flow that creates `profile_relationships` rows**

The linking flow was added after the Phase 0 journey walkthrough found that no phase
created relationship rows, which would have left the coach-views-student journey (J7)
unreachable and blocked uploading games on behalf of a student. See
`final_docs/v2/checklists/user-journeys.md` finding F-1.

### Testing
- OAuth flow integration tests with a mocked provider
- token validation and expiry tests
- RLS and permission tests
- migration rollback tests
- profile CRUD tests

### Exit criteria
- a user can log in with Lichess and land on their own dashboard
- a user can link a Chess.com username
- backend trusts auth correctly
- sign-off required

---

## Phase 3 — Ingestion MVP (Single PGN + Batch Upload)

### Goal
Support manual PGN-based ingestion first, before any external connector.

### Deliverables
- upload PGN file
- paste PGN text
- bulk upload of multiple PGNs
- import job tracking with visible status
- deduplication strategy
- raw game persistence in Supabase Storage

### Tasks
- upload UI in the `imports` feature
- backend ingestion endpoint delegating to an ingestion service
- PGN validation with structured rejection reasons
- job queue for parsing
- persist raw PGNs in storage and normalised headers in Postgres
- duplicate detection on a content hash plus source metadata

### Testing
- valid PGN parse tests
- malformed PGN rejection tests
- duplicate handling tests
- large batch handling tests
- UI upload flow tests

### Exit criteria
- single and batch PGN ingestion stable
- job visibility works
- sign-off required

---

## Phase 4 — Parsing and Canonical Game Object

### Goal
Turn ingested games into canonical normalised game objects.

### Deliverables
- python-chess parsing pipeline
- move list extraction
- FEN and EPD reconstruction per ply
- position persistence policy
- canonical schema implementation

### Tasks
- parse headers with a documented normalisation policy
- replay every move
- persist move records
- generate FEN and EPD for each position
- capture failures with a structured failure taxonomy

### Testing
- parser unit tests against the curated PGN corpus
- property tests for move replay consistency
- spot verification against known games
- performance tests on batch parsing

### Evaluation
- parsing accuracy rate against the corpus
- failure taxonomy coverage
- time per game

### Exit criteria
- canonical object proven stable on the sample corpus
- sign-off required

---

## Phase 5 — Engine Analysis Core

### Goal
Add deterministic engine-backed analysis as the truth layer.

### Deliverables
- Stockfish UCI adapter
- **tiered analysis policy: shallow sweep at configurable baseline depth, deep re-analysis only on candidate critical moments**
- move evaluations and principal variations
- move quality labels
- critical moment extraction

### Configuration
Baseline depth starts at **12** and is read from `ENGINE_DEPTH`. Severity thresholds
(`INACCURACY_CP`, `MISTAKE_CP`, `BLUNDER_CP`) and the deep-pass depth
(`ENGINE_DEEP_DEPTH`) are equally configurable. No engine constant is hardcoded.

### Tasks
- integrate the UCI engine adapter behind an interface
- implement the tiered analysis policy
- compute evaluation before and after each move
- classify moves: best, good, inaccuracy, mistake, blunder
- identify largest swings and pivotal positions

### Testing
- engine adapter integration tests
- deterministic reproducibility tests under fixed settings
- sanity checks against known tactical positions
- worker timeout and retry tests

### Evaluation
- legal line validation
- classification stability across repeated runs
- throughput and cost estimate per game at depth 12 vs the deep pass

### Exit criteria
- engine analysis trustworthy enough for downstream use
- sign-off required

---

## Phase 6 — Opening Detection and Chess Intelligence Tags

### Goal
Add structured meaning beyond raw evaluations.

### Deliverables
- opening and ECO tagging from the Lichess openings dataset
- tactical motif detectors over the agreed taxonomy
- strategic theme detectors
- pattern vocabulary
- training theme mapping
- confidence scores

### Opening data
Source is `lichess-org/chess-openings` `dist/` TSVs (`eco`, `name`, `pgn`, `uci`,
`epd`), CC0 licensed. Detection matches on the **EPD** of each played position and keeps
the deepest match, which is both faster and more accurate than prefix-matching SAN text.
See `final_docs/v2/adr/0009-opening-data-source.md`.

### Tasks
- build the opening lookup service with an EPD index
- implement motif detectors as individually testable units
- implement strategic pattern detection
- map findings to coaching themes
- assign confidence scores

### Testing
- opening identification tests including transpositions
- motif detector tests on curated positions
- false-positive review set
- taxonomy consistency checks

### Evaluation
- precision and recall on a manually labelled sample set
- usefulness review of surfaced tags

### Exit criteria
- tags are useful and sufficiently precise
- sign-off required

---

## Phase 7 — Knowledge Corpus and RAG Foundation (new)

### Goal
Build the retrieval substrate that every downstream explanation depends on. Retrieval is
a first-class product capability here, not a bolt-on.

### Deliverables
- curated, versioned, attributed knowledge corpus
- corpus ingestion pipeline with chunking and metadata policy
- embeddings and vector storage in Supabase Postgres via pgvector
- **multi-RAG: separate retrieval buckets with distinct chunking and retrieval strategies**
- hybrid retrieval combining dense vectors and BM25 with reciprocal rank fusion
- retrieval router that selects buckets from query intent
- **RAGAS retrieval evaluation harness and score ledger**

### Corpus buckets
| Bucket | Content | Source policy |
|--------|---------|---------------|
| `rules` | FIDE Laws of Chess, engine and evaluation semantics | reuse from `grandmate/`, re-verified |
| `openings` | opening names, ideas, typical plans per ECO family | derived from Lichess dataset plus curated prose |
| `tactics` | motif definitions and recognition cues | reuse and expand the existing motif notes |
| `strategy` | pawn structures, plans, endgame principles | curated from open sources with attribution |
| `analysis` | the user's own canonical game objects and aggregates | generated, per-profile, access controlled |

The `analysis` bucket is what makes retrieval personal, and it is the bucket with the
strictest isolation requirement: a retrieval must never cross profile boundaries without
an explicit permission grant.

### Tasks
- curate and attribute corpus content, recording provenance per document
- implement loaders, chunkers, and the metadata schema
- enable pgvector and build the embedding pipeline
- implement dense, sparse, and fused retrievers behind one interface
- implement the bucket router
- build the RAGAS harness with a versioned retrieval dataset

### Testing
- chunking policy unit tests
- retriever interface contract tests
- bucket isolation tests, especially for `analysis`
- index rebuild idempotency tests

### Evaluation
- Context Precision and Context Recall per bucket
- retriever comparison: dense vs BM25 vs hybrid, results recorded
- thresholds defined in `final_docs/v2/evaluation-strategy.md`

### Exit criteria
- retrieval quality clears agreed thresholds
- corpus provenance fully documented
- sign-off required

---

## Phase 8 — Multi-Game Aggregation and Profile Analytics

### Goal
Move from per-game insight to player development insight.

### Deliverables
- last N game windows (10 / 30 / 60)
- Start with 10 games to decrease the complexity
- recurring weakness detection
- opening-family performance summaries
- tactical and strategic trend reports
- colour and time-control segmentation
- progress deltas
- versioned aggregate snapshots

### Tasks
- define aggregate metrics
- compute profile summary snapshots
- build trend scoring rules with explicit small-sample guards
- store aggregate versions for reproducibility

### Testing
- aggregation correctness tests
- small-sample edge cases
- cross-window comparison tests
- profile dashboard UI tests

### Evaluation
- compare aggregate output to manual review on sample profiles
- verify no misleading confidence on tiny samples

### Exit criteria
- profile analytics stable and explainable
- sign-off required

---

## Phase 8b — Private Study Profiles for Unowned PGNs (new)

Checkpoint added during Phase 8 testing, not in the original plan: importing arbitrary
PGNs (games the logged-in user isn't part of, or games loaded purely to learn from) into
the same profile as the user's own games silently corrupted that profile's Phase 8
metrics. See D-021 and ADR-0016.

### Goal
Own games and studied-but-unowned games never mix in the same aggregate metrics, without
requiring a manual "which dashboard is this for" choice at upload time.

### Deliverables
- a second, always-present profile per account (`kind = opponent`, "Study games"),
  created alongside `SELF` at first login
- automatic, per-game import routing: a parsed game's header names are checked against
  the account's linked platform username(s) before persisting; a match routes to `SELF`,
  no match routes to the study profile — a single batch may split across both
- `GET /api/v1/profiles` — list the caller's own profiles
- `profile_id` query param (ownership-checked) on `games`, `analysis`, `patterns`, and
  `analytics` routes, defaulting to `SELF`
- a profile toggle ("My games" / "Study games") on the games list and dashboard pages
- the study profile runs the full Phase 5–8 pipeline — not a restricted view (D-021)

### Tasks
- move Phase 4's header-matching check earlier so it can pick an import target, not just
  resolve `focus_color` after the fact
- lazy/eager study-profile creation in `AuthService`
- ownership-scoped profile resolution added to existing routes
- frontend profile toggle, reused by the games list, game detail, and dashboard pages

### Testing
- import routing: own-username match vs. no match, within a single mixed batch
- cross-profile isolation: a study-profile game never appears in `SELF`'s aggregates or
  vice versa
- ownership check: a `profile_id` the caller doesn't own is rejected, not just filtered

### Exit criteria
- a profile's aggregate metrics only ever reflect games that profile actually owns
- sign-off required

---

## Phase 9 — Persona Layer and Report Generation

### Goal
Render the same truth differently for different audiences.

### Deliverables
- persona transformation layer
- self-learner reports
- coach summaries
- kid-friendly summaries
- in-app HTML report views
- persona switch control

MVP personas are **self-learner, coach, and kid**. Parent and analyst personas are
deferred. PDF export is deferred; MVP reports render in-app.

### Tasks
- define tone and detail policy per persona
- build output contracts that reference analysis facts by id
- create report templates
- add persona switching in the UI

### Testing
- persona contract tests
- content safety tests for the kid persona
- snapshot tests for report rendering
- manual tone review

### Evaluation
- fact-invariance: the same underlying analysis facts must appear across all personas
- verify simplification does not distort chess truth

### Exit criteria
- persona views are distinct but faithful
- sign-off required

---

## Phase 10 — Agentic RAG Chat with Short-Term Memory

### Goal
Interactive question answering grounded in deterministic analysis and the knowledge
corpus, driven by an agent that decides what to retrieve rather than a fixed pipeline.

### Deliverables
- chat threads
- LangGraph agent with tool calling
- **retrieval exposed as agent tools, one per bucket, plus an analysis-lookup tool and a legal-move validation tool**
- active game and profile context injection
- short-term thread memory via a LangGraph checkpointer
- intent routing for explain / compare / summarise / train-next
- grounding guardrail that rejects answers citing moves absent from the game record
- **RAGAS answer-quality harness**

### Why agentic rather than a fixed RAG chain
A single retrieval pass cannot serve both "why was move 23 a blunder in my game" and
"what is the general plan in the Catalan". The first needs the `analysis` bucket keyed to
a specific game; the second needs `openings` and `strategy`. The agent selects tools and
may retrieve iteratively, which is why retrieval is modelled as tools rather than as a
prefix step.

### Tasks
- build the chat UI in the `chat` feature
- add the thread model
- implement the LangGraph state graph with checkpointing
- implement retrieval and analysis tools
- expose evidence and citations internally for debugging
- implement the grounding guardrail

### Testing
- thread continuity tests
- context carry-over tests
- hallucination guard tests against the canonical analysis object
- tool selection tests
- latency and load tests

### Evaluation
- Faithfulness and Response Relevancy via RAGAS, scores recorded
- answers must refer only to valid game facts and legal moves
- context switching must be explicit and predictable

### Exit criteria
- chat is useful within a session and clears faithfulness thresholds
- sign-off required

---

## Phase 11 — Long-Term Memory and Profile-Aware Chat

### Goal
Remember durable preferences and recurring profile facts across sessions.

### Deliverables
- long-term memory store via a LangGraph store
- memory write policy with a confidence floor
- memory audit surface in the UI
- preference retention
- recurring pattern retention
- coach notes

### Memory boundary rule
Short-term thread state, long-term profile memory, and analysis database truth remain
three separate storage models. They are never collapsed.

### Tasks
- implement the memory repository
- connect the LangGraph store
- memory retrieval scoped by profile and persona
- approval rules for memory writes
- audit and delete UI

### Testing
- memory retention tests
- no-overwrite and conflict tests
- cross-profile isolation tests
- privacy and permission tests

### Evaluation
- long-term memory improves continuity without introducing stale errors
- only durable facts persist
- memory-aware RAGAS dataset scored

### Exit criteria
- long-term memory behaves predictably and safely
- sign-off required

---

## Phase 12 — MCP Client Integration (deferred — see ADR-0010, D-027, D-028)

**Status: deferred, not implemented.** The owner first reversed this phase from an MCP
server (exposing GrandMate's own tools externally) to an MCP client (consuming an
external tool) — D-027. Working through that reversal, no external MCP tool turned out
to have a real trigger anywhere in the current product (no chat flow invites a user to
paste a link; open-ended web search was rejected under rule 8/9). Rather than build an
integration to satisfy the letter of D-016 with no product need behind it, the owner
deferred this phase entirely — D-016's MCP requirement stands, unresolved, until a
genuine use case exists. The plan below is preserved as the direction to pick back up,
not a scope to build now.

### Goal
Demonstrate MCP by consuming an external MCP tool from GrandMate's chat agent — not by
exposing GrandMate's own capability over MCP. The owner reversed the original draft
(an MCP server exposing `analyze_pgn`, `get_game_analysis`, etc. to external callers)
before implementation began: GrandMate exposes nothing of its own over MCP. See
ADR-0010 and decision D-027 for the full rationale.

### Deliverables
- MCP client wiring in the backend, reached the same way any other tool dependency is
  (behind an adapter, configured via `.env`, no hardcoded endpoint or key)
- one or more external MCP tools (web search / fetch) registered in the existing chat
  agent tool set (`backend/app/orchestration/tools/registry.py`), alongside the internal
  tools already there
- tool schema and error-shaping for external-server failures (timeout, rate limit,
  malformed response)
- documentation of which external server is used and why

### Candidate tools
External web search / fetch, exposed to the chat agent as a new entry in `TOOL_DISPATCH`.
Exact external server package and whether it requires a credential is **open** — must be
resolved with the owner before coding (see D-027 follow-up).

### Tasks
- confirm the specific external MCP server package and any required `.env` credential
  with the owner
- implement an MCP client adapter and a tool wrapper consuming it, following the same
  calling convention every other entry in `TOOL_DISPATCH` uses
- add step/token budget and error handling consistent with existing agent tools
- document client setup and the external dependency

### Testing
- tool schema contract test for the wrapper
- external-server failure handling tests (timeout, rate limit, malformed response) using
  a mocked MCP client
- integration test exercising the real external MCP server, gated so it doesn't run
  unauthenticated in CI

### Evaluation
- tool call success rate against the external server
- spot-check that agent answers using the external tool stay consistent with the critic
  rule (rule 8): the external tool may inform explanation, never assert chess truth

### Exit criteria
- MCP client integration stable, external-server failures handled gracefully
- sign-off required

---

## Phase 13 — Multi-Agent Orchestration (new)

### Goal
Decompose complex coaching requests across specialised agents coordinated by a supervisor.

### Deliverables
- supervisor graph
- specialised agents: retriever, chess analyst, coach, critic
- **critic agent that verifies claims against deterministic analysis before delivery**
- handoff contracts and shared state schema
- trajectory tracing for debuggability

### Tasks
- define the agent roster and each agent's tool subset
- implement supervisor routing
- implement the critic verification pass
- add per-agent tracing and token accounting

### Testing
- routing correctness tests
- handoff state integrity tests
- critic catch-rate tests using deliberately wrong drafts
- cost ceiling tests

### Evaluation
- trajectory evaluation on a curated task set
- measure whether multi-agent output beats the single-agent baseline from Phase 10; if it
  does not, record that and keep the simpler path

### Exit criteria
- multi-agent path demonstrably better on the evaluation set, or consciously deferred
- sign-off required

---

## Phase 14 — Lichess and Chess.com Game Import Connectors

### Goal
Add account-based game ingestion beyond manual uploads.

### Deliverables
- Lichess game import using the authenticated user's OAuth token
- Chess.com import from the linked username via monthly archives
- recent-window import (last 10 / 30 / 60 games)
- source-specific job handling
- rate-limit protection with backoff

### Tasks
- implement connector adapters behind one interface
- profile-to-source linkage
- month and archive traversal for Chess.com
- NDJSON stream handling for Lichess
- dedupe across imported and uploaded games

### Testing
- connector integration tests with recorded fixtures
- rate-limit and retry tests
- partial import recovery tests
- mapping consistency tests

### Evaluation
- import completeness for the last 30 to 60 games
- source failure handling quality

### Exit criteria
- imports stable in practice
- sign-off required

---

## Phase 15 — Training Plan and Coaching Recommendations

### Goal
Convert insights into actionable improvement plans.

### Deliverables
- weekly training plans
- recurring theme prioritisation
- focus-area planner
- profile-specific recommendation engine

### Tasks
- define the recommendation policy
- map recurring issues to drills and study themes
- support persona-sensitive framing
- track prior recommendations and outcomes

### Testing
- recommendation consistency tests
- no-contradiction tests against profile findings
- user acceptance review

### Exit criteria
- recommendations feel actionable and grounded
- sign-off required

---

## Phase 16 — Evaluation, Synthetic Data, Golden Sets, and Fine-Tuning (expanded)

### Goal
Consolidate evaluation into a trended, gating system and decide whether fine-tuning earns
its place.

### Deliverables
- consolidated RAGAS suite across single-game chat, profile chat, memory-aware chat, and persona explanation
- **versioned golden sets, human-reviewed**
- **synthetic dataset generation pipeline with provenance and human spot-check**
- score ledger with run-over-run trending and regression flags
- LLM-as-judge rubrics for tone and persona fidelity
- fine-tuning experiment and go/no-go decision

### Fine-tuning position
Fine-tuning is evaluated last, deliberately. Retrieval quality, prompt design, and
grounding guardrails are cheaper and more auditable levers, and a fine-tuned model that
hides a retrieval defect is a worse outcome than a slower correct one. The candidate use
case is persona tone consistency, not chess knowledge — chess truth stays deterministic.
Proceed only if the evaluation set shows a measurable gain that prompting cannot reach.

### Tasks
- unify the harness across all datasets
- build the synthetic generator and label workflow
- implement the score ledger with thresholds
- run the fine-tuning experiment and record the comparison

### Threshold rule
If Faithfulness or Answer Accuracy falls below the agreed threshold, the phase stops and
the failure is reported. Evaluation is never run informally and discarded.

### Exit criteria
- all datasets scored and trended, thresholds met
- fine-tuning decision documented with evidence
- sign-off required

---

## Phase 17 — Observability, Security, and Production Hardening

### Goal
Prepare the platform for reliable real-world use.

### Deliverables
- structured logs with request and trace ids
- tracing across API, worker, and agent boundaries
- metrics dashboards
- job dead-letter handling
- rate limiting and LLM spend guardrails
- permission audits
- backup and recovery playbook
- incident runbooks
- **hosting decision made here, deferred from Phase 0**
- **managed data platform decision, deferred from Phase 2** — adopt Supabase per
  ADR-0002 or an alternative; write the Storage adapter and switch the connection
  string. No schema change is involved, since MVP already runs Postgres.

### Tasks
- request id and trace propagation
- worker job metrics
- engine resource monitoring
- chat latency, token, and cost monitoring
- auth and access auditing

### Testing
- load tests
- chaos and retry tests
- backup restore drill
- security review

### Exit criteria
- production baseline approved
- sign-off required

---

## Phase 18 — Beta Rollout and Evaluation Loop

### Goal
Validate product usefulness with real users and iterate safely.

### Deliverables
- beta cohort plan
- feedback rubric
- evaluation dashboards
- release checklist
- prioritised post-beta backlog

### Metrics
- analysis completion rate
- parsing success rate
- import success rate
- retrieval and answer quality trend
- chat usefulness rating
- memory usefulness rating
- training plan follow-through
- persona satisfaction by role
- cost per analysed game and per active user

### Exit criteria
- beta data supports continued investment
- sign-off required

## Testing Strategy

### Test pyramid

#### Unit tests
- parser behavior
- evaluators
- pattern detectors
- aggregators
- persona transformers
- memory policies

#### Integration tests
- API + DB
- API + worker
- engine adapter
- Lichess connector
- Chess.com connector
- LangGraph flows

#### End-to-end tests
- upload PGN to report
- import games to aggregate profile
- chat over current game
- chat over multi-game profile
- switch personas over same profile

#### Evaluation tests
- faithfulness of LLM outputs to deterministic analysis
- legality of referenced moves/lines
- stability of aggregate conclusions
- relevance of stored memories

### Special evaluation suites

#### Chess truthfulness suite
- no fabricated moves
- no illegal variations
- no unsupported tactical claims
- no contradiction of engine-backed findings

#### Persona fidelity suite
- same underlying facts across personas
- language and detail vary appropriately
- child/parent outputs remain comprehensible and safe

#### Memory quality suite
- short-term memory retains thread context accurately
- long-term memory stores only durable facts
- no leakage between profiles

#### Retrieval quality suite
- correct bucket selected for the query intent
- Context Precision and Context Recall above threshold per bucket
- hybrid retrieval outperforms the dense-only and sparse-only baselines, or the simpler
  retriever is kept
- `analysis` bucket results never cross a profile boundary

#### Agent behaviour suite
- correct tool selected for the task
- step and token ceilings respected
- critic agent catches deliberately falsified draft claims
- MCP and internal agent paths return identical results for the same tool call

## Engineering Standards

### Code quality
- type checking required
- linters required
- formatting required
- descriptive comments for non-obvious code
- docstrings for public modules/classes/functions
- avoid god files and god services
- each feature owns its interfaces, tests, and docs

### API design
- versioned API paths
- explicit request/response schemas
- idempotent job creation where possible
- structured error contracts

### Data and migrations
- all schema changes via migrations
- rollback plan for each migration
- seed fixtures for test environments

### Documentation
- ADR for major architectural choices
- per-feature README where useful
- sequence diagrams for critical flows
- operator runbooks for jobs and incidents

### Release gating
No phase proceeds unless:
- implementation complete
- tests pass
- evaluation suite passes
- docs updated
- demo provided
- user explicitly approves next phase

## Decision Baseline (locked in Phase 0)

These were the open decisions the implementation assistant was required to ask about
before guessing. They are now answered. The authoritative record with full rationale is
`final_docs/v2/decisions-log.md`; this table is the summary.

| Topic | Decision | Reference |
|-------|----------|-----------|
| Repository layout | Monorepo `grandmate-v2/` with `backend/` and `frontend/` as independently toolchained, independently CI'd subprojects | ADR-0001 |
| Primary database | Supabase Postgres, run locally via the Supabase CLI in development | ADR-0002 |
| Identity | Log in with Lichess via OAuth2 PKCE. Chess.com linked by username in MVP, since Chess.com OAuth is approval-gated | ADR-0007 |
| Viewing other players | Own-profile dashboard after login; other players viewed on a separate page reusing the same analysis and view logic under a permission gate | ADR-0012 |
| MVP personas | self-learner, coach, kid. Parent and analyst deferred | ADR-0011 |
| LLM provider | `gpt-4o-mini` by default, behind a provider abstraction so the model is swappable | ADR-0006 |
| Secrets and tunables | Everything from `.env` via a typed settings module. No hardcoded keys, no hardcoded engine constants | `configuration.md` |
| Engine policy | Baseline depth 12, configurable, with a tiered deep pass on candidate critical moments | ADR-0004 |
| Opening data | `lichess-org/chess-openings` `dist/` TSVs, matched on EPD. CC0 | ADR-0009 |
| Motif and strategy taxonomy | Starter taxonomy drafted in `glossary.md`, refined at Phase 6 | `glossary.md` |
| Knowledge corpus | Reuse verified material from `grandmate/`, curate the remainder from open sources with recorded provenance | ADR-0008 |
| RAG architecture | Agentic RAG with multi-bucket retrieval and hybrid search, retrieval exposed as agent tools | ADR-0008 |
| MCP | Analysis and retrieval exposed as MCP tools over the existing service layer | ADR-0010 |
| Memory retention | Principle approved: durable facts only, audited, user-deletable. Detailed policy set at Phase 11 | ADR-0005 |
| Reports | In-app HTML in MVP. PDF export deferred | ADR-0011 |
| Hosting | Deferred to Phase 17. Containers stay portable in the meantime | ADR-0001 |
| Evaluation | RAGAS from Phase 7 onward with a recorded score ledger; synthetic and golden sets consolidated at Phase 16 | `evaluation-strategy.md` |
| Fine-tuning | Evaluated at Phase 16, scoped to persona tone only, never to chess truth | `evaluation-strategy.md` |

### Still open, by design

These are deliberately deferred rather than unresolved. Each has a phase where it must be
answered before that phase can complete.

| Topic | Decided at | Why deferred |
|-------|-----------|--------------|
| Supabase project credentials | Phase 2 | User supplies local project details when Phase 2 starts |
| OpenAI API key placement | Phase 1 | `.env.example` lands with the backend scaffold; the real key goes in `.env` then |
| Exact memory retention windows | Phase 11 | Needs real chat behaviour to reason about |
| Chess.com partner OAuth | Phase 14 | Depends on an external approval process |
| Hosting target and deployment topology | Phase 17 | Premature before load characteristics are known |
| Fine-tuning go/no-go | Phase 16 | Requires an evaluation baseline to judge against |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Engine analysis too slow or costly | High | Configurable depth, selective deep analysis, background jobs |
| Persona outputs distort chess truth | High | Persona layer only transforms presentation, not facts |
| Memory stores stale or noisy facts | High | strict write policy, audit UI, human-confirmed durable facts |
| External APIs change or rate limit | Medium | connector abstraction, retries, backoff, cached imports |
| Pattern detectors overfit or create false positives | Medium | curated test corpus, confidence scores, manual review loop |
| Schema becomes tangled | High | domain ownership, ADRs, migration discipline |
| LLM hallucinations in chat | High | evidence-first prompts, deterministic context packets, critic verification pass, evaluation suite |
| Retrieval returns plausible but irrelevant context | High | multi-bucket routing, hybrid retrieval, Context Precision/Recall thresholds enforced per bucket |
| Corpus quality is poor or unattributed | High | provenance recorded per document, human review before a document enters a bucket |
| `analysis` bucket leaks between profiles | Critical | profile scoping enforced at the retriever interface, isolation tests in CI, permission checks on every tool call |
| Agent loops or runaway tool calls | Medium | step ceilings, token budgets, cost guardrails, trajectory tracing |
| Multi-agent adds cost without adding quality | Medium | measured against the single-agent baseline; kept only if the evaluation set improves |
| MCP surface exposes more than intended | High | curated tool list, permission-scoped execution, contract tests per tool |
| Fine-tuning masks a retrieval defect | Medium | fine-tuning scoped to tone only, gated behind evaluation evidence, chess truth stays deterministic |
| Chess.com OAuth never approved | Low | MVP designed around username linking, so approval is an upgrade rather than a dependency |

## Milestone Order Summary

1. Discovery baseline
2. Engineering foundation
3. Supabase + Lichess identity
4. Manual PGN ingestion
5. Canonical parsing
6. Engine analysis
7. Chess intelligence tags
8. **Knowledge corpus + RAG foundation**
9. Profile aggregation
10. Persona views
11. **Agentic RAG chat + short-term memory**
12. Long-term memory
13. **MCP server**
14. **Multi-agent orchestration**
15. External imports
16. Training plans
17. **Evaluation, synthetic + golden sets, fine-tuning decision**
18. Hardening
19. Beta

## Success Criteria

The project succeeds when it can:
- let a player log in with Lichess and see their own dashboard, and link a Chess.com username,
- ingest single and multiple PGNs reliably,
- import recent public games from Lichess and Chess.com reliably,[cite:393][cite:423]
- convert each game into one canonical enriched object,
- aggregate multiple games into meaningful profile patterns,
- retrieve grounded knowledge from a curated multi-bucket corpus with measured precision and recall,
- answer questions through an agent that chooses its own retrieval strategy and cites deterministic analysis,
- support multiple personas over one truth layer,
- provide chat with short-term and long-term memory via LangGraph-compatible patterns,[cite:407][cite:408][cite:411]
- expose its capabilities as MCP tools without duplicating logic,
- prove quality with recorded, trended RAGAS scores rather than impressions,
- remain modular, explainable, testable, and production-manageable,
- and advance phase by phase only after explicit user approval.
