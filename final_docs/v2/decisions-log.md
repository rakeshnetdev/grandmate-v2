# Decision Log

Authoritative record of product and architecture decisions for GrandMate v2. Every entry
records what was decided, who decided it, and when. Decisions here are binding on
implementation; changing one requires an explicit new entry, not a quiet edit.

Status legend: **Locked** (decided, implement against it) · **Deferred** (intentionally
open, with a phase where it must be answered) · **Superseded**.

---

## Phase 0 decisions

Decided by the project owner on 2026-07-25 in response to the Phase 0 decision request.

### D-001 — Repository layout · Locked
Monorepo at `grandmate-v2/` containing `backend/` and `frontend/` as separate subprojects
with independent toolchains, dependencies, and CI jobs. Satisfies the "backend and
frontend must remain separate" rule without the overhead of two repositories.
→ ADR-0001

### D-002 — MVP personas · Locked
Three personas ship in MVP: **self-learner**, **coach**, **kid**. Parent and analyst
personas are deferred. Rationale: three personas is enough to prove the persona layer
genuinely separates presentation from truth, while keeping the persona fidelity test
matrix tractable.
→ ADR-0011

### D-003 — Identity and login · Locked
Every user logs in with a chess platform account rather than an email/password pair.
Primary provider is **Lichess** via OAuth2 Authorization Code with PKCE. After login the
user lands on a dashboard scoped to their own games.

**Chess.com constraint discovered during Phase 0**: Chess.com's Published-Data API is
unauthenticated and read-only, and its OAuth login is an approval-gated partner
programme. It therefore cannot be a login provider in MVP. Chess.com is instead linked by
**username**, which is sufficient to import public game archives. The connector interface
is designed so Chess.com can be promoted to a login provider if approval is granted.
→ ADR-0007

**Timing deviation decided in Phase 2**: real Lichess OAuth2 PKCE is deferred. MVP login
for *both* Lichess and Chess.com checks that a username exists on the platform (via its
public API) and logs the caller in as that account — no proof of ownership, every identity
row marked `verified = false`. This must close before any private-data or write feature
ships. The direction in ADR-0007 (Lichess as the eventual OAuth login provider, Chess.com
as source-only) is retained; only the Phase 2 implementation is simplified.
→ ADR-0014

### D-004 — Viewing other players · Locked
The post-login dashboard shows only the authenticated player's own profile. Viewing
another player happens on a **separate page** that reuses the same analysis pipeline,
aggregation logic, and view components as the self view, differing only in the permission
gate and in which persona modes are offered.
→ ADR-0012

### D-005 — LLM provider · Locked
Default model is **`gpt-4o-mini`**, accessed through a provider abstraction so the model
can be swapped without touching domain code. The API key is supplied by the project owner
and lives in `.env`. Claude must prompt the owner to add the key when the backend scaffold
lands in Phase 1, and must not invent placeholder values.
→ ADR-0006

### D-006 — Hosting · Deferred to Phase 17
No hosting target is chosen now. Containers stay portable in the meantime so the decision
is not foreclosed.

### D-007 — Database · Locked
Supabase Postgres, run **locally via the Supabase CLI** during development. The project
owner has a Supabase account and will supply project details when Phase 2 begins.
pgvector is enabled from the start because retrieval is core to the product.
→ ADR-0002

### D-008 — Configuration discipline · Locked
No hardcoded keys and no hardcoded constants. Engine depth, severity thresholds, model
names, retrieval parameters, and rate limits are all read from `.env` through a typed
settings module. This was called out explicitly by the owner and is elevated to a
non-negotiable rule in `claude.md`.
→ `configuration.md`

### D-009 — PGN corpus · Locked
Reuse the existing corpus from `grandmate/` where it is fit for purpose, and curate the
remainder from open sources. The reference repo already contains substantial material:
Carlsen (7,818 games) and Praggnanandhaa (2,775 games) PGN collections. These cover
volume and realistic master play but not edge cases, so a small curated edge-case set is
added: games with variations, comments, NAGs, malformed headers, aborted games, and
non-standard time controls.
→ `changes/0001-reuse-ledger.md`

**Amended in Phase 4**: the owner asked for a smaller MVP fixture footprint after seeing
the full collections committed (7.5MB, 10,594 games). Trimmed to the first 75 games of
each collection (150 total) plus the 8 curated edge cases — small enough to run in the
default test suite with no separate slow tier. The full-corpus run performed once before
trimming found one real data artifact (a zero-move forfeit record) and established a
99.99% canonicalization accuracy baseline; those findings are recorded in the Phase 4
report rather than re-verified against 10k+ games on every change.

### D-010 — Engine analysis budget · Locked
Baseline analysis depth is **12**, read from `ENGINE_DEPTH`. Tiered policy approved: a
shallow sweep across all plies at the baseline depth, then a deeper pass only on candidate
critical moments. Severity thresholds carried over from the reference app as starting
values — inaccuracy 50cp, mistake 100cp, blunder 300cp — all configurable.
→ ADR-0004

### D-011 — Opening data source · Locked
The reference app's `openings.tsv` is rejected: it holds only 65 hand-written openings
with prose descriptions, which is far too thin and not authoritative. Replaced with
**`lichess-org/chess-openings`** `dist/` TSVs, which carry `eco`, `name`, `pgn`, `uci`,
and `epd` columns under a CC0 public domain dedication.

The owner asked whether FEN or PGN is needed. The answer is **EPD**, which the dataset
provides directly. EPD is a FEN without the move counters, so it identifies a position
independently of how many moves it took to reach — which is exactly what transposition
handling requires. Detection walks the played positions, looks each EPD up in an index,
and keeps the deepest match. The prose descriptions from the old TSV are still useful and
are folded into the `openings` corpus bucket as explanatory text rather than as
identification data.
→ ADR-0009

### D-012 — Motif and strategy taxonomy · Locked
Starter taxonomy drafted in `glossary.md` — 16 tactical motifs and 10 strategic themes —
seeded from the reference app's tactics notes, which are of good quality and reusable.
Refined and confirmed at Phase 6 against detector precision results.

### D-013 — Memory retention · Principle locked, detail deferred to Phase 11
Approved in principle: long-term memory stores only durable facts, writes are gated by a
confidence floor, all stored memory is visible in an audit surface, and the user can
delete any entry. Exact retention windows and conflict resolution rules are decided at
Phase 11 when there is real chat behaviour to reason about.
→ ADR-0005

### D-014 — Report formats · Locked
In-app HTML report views in MVP. PDF export deferred.

### D-015 — RAG is a core capability · Locked
The owner was explicit that RAG is very important and that the knowledge corpus must be
properly built and used wherever knowledge is needed, chat included. This changes RAG from
a supporting detail into a first-class subsystem with its own phase, domain modules,
tests, and evaluation.
→ ADR-0008

### D-016 — Agentic scope · Locked
The project must demonstrate agentic RAG, multi-RAG, MCP, evaluations, synthetic and
golden datasets, fine-tuning, agents, multi-agents, and LangGraph.

This is a material expansion of the original plan, which mentioned none of MCP,
multi-agent orchestration, or fine-tuning. Three new phases were inserted and the
evaluation phase was expanded. Deviation recorded per the documentation rule in
`claude.md`.
→ ADR-0008, ADR-0010, `phase-map.md`

### D-017 — Fine-tuning position · Locked
Fine-tuning is evaluated at Phase 16, last in the sequence, and is scoped to **persona
tone consistency only** — never to chess knowledge. Chess truth stays deterministic and
engine-derived. Fine-tuning proceeds only if the evaluation set shows a gain that
prompting and retrieval cannot reach.

### D-018 — Phase 3 ingestion mechanics · Locked
Three implementation defaults proposed and confirmed with the owner before coding:

- **Job processing**: in-process, DB-backed (a generic `jobs` table), not a Redis-backed
  queue. No new infrastructure for MVP-scale imports; Phase 3 processes synchronously
  within the request, Phase 9's external-API imports are the first caller expected to
  need real async work.
- **Batch semantics**: one endpoint handles pasted text, one file, or many files
  together, and any file may itself contain one game or many concatenated games. A
  single-game upload is the N=1 case of this path, not a separate mode — confirmed with
  the owner, who asked that it "work even with a PGN with a single game" and noted scale
  can grow later without a different code path.
- **Dedup key**: sha256 over normalised movetext + result + players + date, scoped to
  `(profile_id, content_hash)`. Catches the same game re-exported with different
  comments/clock annotations; a raw-text hash would not.

### D-019 — Phase 5 engine analysis dispatch · Locked
Two decisions confirmed with the owner before coding, after benchmarking real Stockfish
timing on the target machine (depth 12 ~46ms/position, depth 18 ~1.06s/position, ~7s/game
including the deep pass):

- **Trigger**: automatic background job, not inline with import (unlike Phases 3–4) and
  not a manual-only trigger. `ImportService` queues a `pending ENGINE_ANALYSIS` job per
  canonicalized game; the route dispatches it via `BackgroundTasks` after the response is
  sent, using the existing `jobs` table's `kind` discriminator — no new table.
- **Concurrency**: bounded, not sequential — `ENGINE_MAX_CONCURRENT_GAMES` (default 4)
  caps how many games' analysis jobs run at once, each in its own single-threaded
  Stockfish process (`ENGINE_THREADS` stays 1 for determinism; parallelism is at the game
  level, not the thread level, per the existing `EngineSettings` rationale). Reduces a
  60-game batch's background completion time from ~7 minutes sequential to ~1.75 minutes
  at 4-way concurrency.

### D-020 — Phase 8 aggregation mechanics · Locked
Three decisions confirmed with the owner before coding:

- **Recurring weakness definition**: a motif/theme that recurs, on the player's own
  side, at a mistake-or-worse cost where that's checkable, above a configurable
  occurrence rate (`ANALYTICS_WEAKNESS_MIN_OCCURRENCE_RATE`, default 0.3). Reuses Phase
  6's existing taxonomy; no new categories invented. Implementation turned up that motif
  vs. theme "side" polarity is not uniform (most motifs mean the mover benefited, one —
  `HANGING_PIECE` — means the mover blundered; most themes mean bad-for-that-side, four
  are achievements) — documented in `domain/analytics/metrics.py` and confirmed correct
  by live verification, not just unit tests.
- **Compute trigger**: on demand, recomputed and re-persisted as a new versioned
  `ProfileAggregateSnapshot` row on every dashboard request, not a background job.
  Aggregation only reads already-computed per-game data, so this is cheap — same
  reasoning Phase 3 originally used for inline ingestion.
- **Small-sample guard**: 5 games minimum (`ANALYTICS_MIN_GAMES_FOR_TREND`) before
  trends/weaknesses are asserted rather than caveated with `sufficient_sample = false`.
→ `final_docs/v2/phase-reports/phase-08-multi-game-aggregation.md`

### D-021 — Phase 8b: private study profile for unowned PGNs · Locked
Every account gets a second, always-present profile (`kind = opponent`, "Study games"),
created alongside `SELF` at first login. Import routing between the two is automatic and
per-game: a parsed game's `White`/`Black` headers are checked against the account's
linked platform username(s) before persisting — a match routes to `SELF`, no match routes
to the study profile. The study profile runs the full Phase 5–8 pipeline (not a
restricted per-game-only view) and is never shared — no `profile_relationships` row is
ever created for it. This narrows, but does not reopen, ADR-0012's deferral of analysing
arbitrary opponents: that deferral is about cross-*account* viewing exposure, which this
decision does not create.
→ ADR-0016

### D-022 — LLM daily spend ceiling · Locked (Q-4 resolved)
`LLM_DAILY_TOKEN_CEILING` (blank/uncapped since Phase 1, deferred as Q-4) is enforced
starting Phase 9, the first phase that makes a real completion spend — embeddings
(Phase 7) never needed it. Default `500,000` tokens/day, an MVP starting point (worst
case a few tens of cents/day at `gpt-4o-mini` pricing), not a load-tested production
figure. Enforcement is a soft-overflow, hard-stop-next guard (`LLMBudgetTracker`): a call
already in flight is allowed to finish, but the next one is refused before it starts,
falling back to the deterministic report rather than erroring — see D-023.
→ `final_docs/v2/phase-reports/phase-09-persona-layer-report-generation.md`

### D-023 — Phase 9 report generation mechanics · Locked
Three decisions confirmed with the owner before coding:

- **Scope**: per-game reports only. Profile-level (aggregate) persona reports over
  Phase 8's trend data are not part of this phase — a smaller surface lets the
  grounding/critic pattern get proven before extending it.
- **Critic failure handling**: one retry on an ungrounded LLM response, then fall back to
  a deterministic, facts-only report — never an error surfaced to the reader. The
  fallback is not a degraded state; `persona-matrix.md`'s invariant ("a persona changes
  how a finding is said, never whether it is true") holds exactly as well for a plain
  fact listing as for LLM prose.
- **Persistence**: reports are stored and versioned (`GameReport`, keyed by
  `analysis_version`), the same pattern `GameAnalysis` and `ProfileAggregateSnapshot`
  already use — avoids re-paying LLM cost per view and keeps old reports reproducible.

Live verification against a real `gpt-4o-mini` call confirmed the safety design is not
theoretical: the kid persona's stricter constraints (no centipawn values, exactly one
recommendation) were not met on either attempt for a real game, and the system correctly
fell back to the deterministic summary rather than show an ungrounded report to a child,
while the self-learner and coach personas produced real, well-grounded LLM prose for the
same game in the same run.
→ `final_docs/v2/phase-reports/phase-09-persona-layer-report-generation.md`

### D-024 — Kid persona age bands · Deferred (Q-5 resolved)
Stays a single kid persona covering the whole "roughly 8-14" range `persona-matrix.md`
already specifies — matches D-002's locked MVP persona scope (exactly self-learner,
coach, kid). Splitting into age bands (e.g. 8-10 / 11-14) is real additional scope — new
matrix rows, prompts, critic rules, tests — deferred until real usage data motivates it,
not built speculatively now.

### D-025 — Phase 10 agentic chat mechanics · Locked
Four decisions confirmed with the owner before coding, all defaults recommended and
approved as proposed:

- **Checkpointer backend**: Postgres-backed (`langgraph-checkpoint-postgres`), not
  in-memory. Threads must survive a backend restart for a coaching product users return
  to. Its tables (`checkpoints`, `checkpoint_writes`, ...) are deliberately **not** an
  Alembic migration — they are library-owned state versioned by the package's own
  `.setup()` call (idempotent, run on every turn via `orchestration/checkpointer.py`),
  and pinning that DDL into our migration history would fight the library's own upgrade
  mechanism the next time the installed version changes. `chat_threads` (the
  identity/listing row a route can query without touching LangGraph internals) *is* a
  normal Alembic-owned table — only the checkpointer's own internal state is exempt.
- **Response mode**: single-shot request/response, not streaming. Matches Phase 9's
  report-generation pattern; the grounding guardrail needs to see the complete answer
  before anything reaches the user regardless, so streaming would not have shortened the
  real latency, only added transport complexity.
- **Intent routing**: LLM-classified (`explain`/`compare`/`summarise`/`train_next`), not
  a keyword heuristic like Phase 7's bucket router. User phrasing for intent is
  open-ended natural language, not domain keywords — exactly the judgment call agentic
  RAG is meant to hand to the model. Falls back to `explain` on any parse failure or
  off-taxonomy response.
- **Evaluation dataset size**: a small (10-scenario) self-authored, unreviewed golden
  set now, not the ~60-question target `evaluation-strategy.md` names for the mature
  system — that number is a long-run target, not a Phase 10 gate, matching Phase 9's
  identical reasoning for its own persona-fidelity set.

**Grounding contract**: the agent's final turn answers in a structured shape —
`{"answer": ..., "citations": [...]}` — with four citation kinds (`move`, `evaluation`,
`variation`, `opening`), each checked against the same profile-scoped tables the tools
themselves read from. Discovered during live testing: the tool set initially omitted a
way to answer "what was my opening in this game" at all (`lookup_opening(epd)` needs an
EPD nothing gave the model access to) — fixed by attaching the game's already-computed
`OpeningMatch` directly to `get_game_analysis`'s payload and adding the corresponding
`opening` citation kind, rather than requiring the model to chain three tool calls for a
question this common.

**RAGAS answer-quality finding**: a real run against `gpt-4o-mini`
(`evals/runs/20260728T162429Z_single_game_chat.json`) recorded Faithfulness 0.70 against
`evaluation-strategy.md`'s 0.85 hard threshold. Per the golden-vs-synthetic rule already
applied identically in Phase 7 and Phase 9, this does not block sign-off — the dataset is
unreviewed (`reviewed_by` unset on every scenario) — but the number itself is a real,
specific finding, not noise: manual review of all ten real answers found no false or
fabricated game-specific claim; RAGAS's Faithfulness scores every sentence, including
legitimate coaching advice ("study tactical patterns like forks and pins") that was never
meant to be citation-backed the way a game fact is. The citation-level grounding
guardrail — which *is* unconditionally enforced, not dataset-gated — caught every
citation-shaped claim correctly in testing. Worth revisiting once the golden set is
human-reviewed: either the threshold needs owner recalibration for a system that
intentionally gives uncited advice, or the output contract needs an explicit
advice-vs-fact split so Faithfulness can be scored against the fact portion only.
→ `final_docs/v2/phase-reports/phase-10-agentic-rag-chat.md`

---

## Open questions raised back to the owner

Recorded here so they are not lost between phases.

| # | Question | Needed by | Status |
|---|----------|-----------|--------|
| Q-1 | Confirm `gpt-4o-mini` is the intended model (the request read "gpt-40-min") | Phase 1 | Resolved — D-001 era, confirmed |
| Q-2 | Supabase local project details and service role key | Phase 2 | Superseded — ADR-0015, plain Postgres for MVP |
| Q-3 | Should email/password be offered as a fallback login for users with neither platform account? | Phase 2 | Open |
| Q-4 | Is there a monthly LLM spend ceiling to encode as a hard guardrail? | Phase 1 | Resolved — D-022 |
| Q-5 | Should the kid persona have an age band, which affects reading level targets? | Phase 9 | Resolved — D-024, deferred |
