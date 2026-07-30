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

### D-026 — Phase 11 long-term memory mechanics · Locked (D-013 detail resolved)
Three decisions confirmed with the owner before coding, all defaults recommended and
approved as proposed — the exact retention/conflict-resolution detail D-013 deferred to
"when there is real chat behaviour to reason about":

- **Write trigger**: silent, confidence-gated — not a confirmation prompt ("I'll
  remember that you're focusing on endgames — ok?"). The confidence floor
  (`MEMORY_WRITE_CONFIDENCE_FLOOR`, default 0.7) is the entire enforcement mechanism for
  ADR-0005's "only durable facts persist"; no in-chat friction on every new preference
  or goal.
- **Retention window**: no automatic expiry. An entry persists until superseded by a
  new one of the same kind (`preference`/`goal`) or manually deleted — staleness is
  handled by the write policy preferring recent signal, not a timer, matching the
  supersede-not-overwrite audit trail ADR-0005 already specifies.
- **`coach_note` scope**: deferred entirely, not even the data model. There is no
  coach-viewing feature for it to attach to yet (ADR-0012 still defers cross-account
  viewing) — `MemoryKind` ships with `preference` | `goal` | `recurring_finding` only.

**Supersession policy, an implementation detail beyond what was asked but worth
recording.** `preference` and `goal` are single-current-value-per-profile — a new one
supersedes whatever was active, matching how a coach actually thinks about "what does
this player want right now." `recurring_finding` accumulates instead (a player can have
several distinct recurring weaknesses at once), deduplicated only against an exact
repeat. A real semantic "does this update an existing entry" judgment is not attempted —
genuinely the class of decision D-013 said needed real chat behaviour first, and one
phase of real usage is not that yet.

A real evaluation run against `gpt-4o-mini`
(`evals/runs/20260728T204941Z_memory_quality.json`) scored retention true-positive and
true-negative rates at 100% across ten scenarios — including one designed to catch the
extraction prompt attributing a durable statement to the assistant's own words rather
than the player's — plus a real-Postgres check confirming staleness resolves to exactly
one active entry and memories never cross a profile boundary.
→ `final_docs/v2/phase-reports/phase-11-long-term-memory.md`

### D-027 — Phase 12 direction reversed: MCP client, not server · Locked
ADR-0010 (drafted at Phase 0, still "Proposed") assumed GrandMate would expose its own
analysis/retrieval tools through an MCP *server* for external clients to call. Before
Phase 12 implementation began, the owner reversed this: **GrandMate exposes nothing of
its own over MCP.** No outward-facing MCP server, no external caller granted access to
`get_game_analysis`, `get_profile_aggregate`, or any other internal capability.

Instead, MCP is demonstrated the other direction — GrandMate as an MCP **client**,
consuming an existing external MCP tool (web search / fetch) from inside the chat agent's
own tool set (`orchestration/tools/registry.py`), the same set the LangGraph agent already
calls per ADR-0009/rule 13.

This is a reversal of ADR-0010's decision, not a refinement of it — recorded per the
deviation rule in `claude.md` rather than silently overwritten. D-016's requirement that
the project demonstrate MCP still stands; only the direction of the integration changed.
Rationale: exposing GrandMate's own tools externally was judged unnecessary risk/surface
for this project's actual goals, whereas consuming external tools inside the existing
agent has no equivalent exposure — nothing about a profile's data leaves the system.

Still open, to be resolved before implementation: which specific external MCP server
package to connect to, and whether it requires a credential for `.env`.
→ ADR-0010 (rewritten), `project-plan.md` Phase 12, `phase-map.md`

### D-028 — Phase 12 deferred: no forced MCP integration without a real use case · Locked
Working through D-027's client direction surfaced that the only external MCP tool worth
adding (`fetch`, for a user-pasted URL) has no concrete trigger anywhere in the product
today — no chat flow currently invites a user to paste a link, and open-ended web
*search* was rejected outright because an LLM treating live web content as chess truth is
exactly what rule 8/9 exist to prevent.

Rather than build an integration to satisfy D-016's letter with no product need behind
it, the owner deferred Phase 12 entirely. D-016's MCP requirement is not dropped — it is
unresolved until a genuine use case exists (most likely once a chat flow that accepts
user-supplied links or references is designed, possibly alongside Phase 13's multi-agent
work). Revisit then rather than inventing a use case now.

ADR-0010 and `project-plan.md` Phase 12 are marked Deferred, not deleted, so the reasoning
survives for whoever picks this back up.
→ ADR-0010, `project-plan.md` Phase 12, `phase-map.md`

### D-029 — Phase 13 scope confirmed before coding · Locked
Two defaults proposed and confirmed with the owner before implementation began:

- **Agent-trajectory evaluation set**: synthetic first, human spot-checked — same
  discipline as every other synthetic set in this project (never silently becomes the
  golden set; a human must spot-check a sample before it gates anything). Built smaller
  than the ~30 originally proposed: 12 scenarios, three per routing category (retrieval
  only, analysis only, both, neither), sized to what this comparison actually needs to
  exercise every supervisor routing path at least a few times, not padded to a round
  number. Flagged here as a deliberate scope reduction from what was proposed, not a
  silent one.
- **Agent budget ceilings**: dedicated `MultiAgentSettings` (`MULTI_AGENT_MAX_STEPS=20`,
  `MULTI_AGENT_MAX_TOOL_CALLS=20`, `MULTI_AGENT_TOKEN_BUDGET=60000`), not a reuse of
  Phase 10's `AgentSettings`. Rationale: the supervisor graph spends that kind of budget
  across up to five agents in one turn, and reusing the single-agent ceiling unchanged
  would starve the multi-agent path before it could do enough work to fairly test
  whether it beats the Phase 10 baseline — the entire question Phase 13 exists to
  answer.

The agent roster and per-agent tool subsets (Supervisor/Retriever/Chess analyst/Coach/
Critic) were already locked in `rag-architecture.md` §7 at Phase 0 and are not
re-litigated here.
→ `rag-architecture.md` §7, `evaluation-strategy.md`, `final_docs/v2/phase-reports/phase-13-multi-agent-orchestration.md`

### D-030 — Phase 14 import proceeds without real Lichess OAuth · Locked
`project-plan.md`'s Phase 14 text ("Lichess game import using the authenticated user's
OAuth token") assumed real Lichess OAuth2 PKCE would have landed by this phase. It
hasn't — ADR-0014 (Phase 2) deferred it in favour of username-claim login, so there is
no OAuth token to reuse.

ADR-0014 gates real OAuth as required "before any private data or write-permission
feature ships." Reading a profile's own **public** game history — Lichess's
`GET /api/games/user/{username}` export, Chess.com's public monthly archives — is
neither: it is the same class of public, unauthenticated lookup `PlatformClient`
already performs for login. The owner confirmed Phase 14 proceeds on that basis: import
connectors read public archives for the profile's linked username, exactly as today's
username-claim login already trusts that username to identify the account. Chess.com's
planned username-verification token (ADR-0007) and real Lichess OAuth remain deferred
together, gated on the same "before private data or write access" line ADR-0014 already
drew — not re-opened here.

This is a documented deviation from `project-plan.md`'s literal Phase 14 text, not a
silent reinterpretation.
→ ADR-0007, ADR-0014, `project-plan.md` Phase 14

### D-031 — Phase 14 connectors fetch PGN, not NDJSON/structured JSON · Locked
`project-plan.md`'s Phase 14 task list literally says "NDJSON stream handling for
Lichess," implying the connector should consume Lichess's structured game-JSON stream
and Chess.com's structured JSON directly. Proposed instead, and confirmed with the
owner: both connectors fetch **PGN text** — Lichess's export endpoint via
`Accept: application/x-chess-pgn`, Chess.com's monthly archives via the `pgn` field
already embedded in each game object — and hand it to `ImportService.ingest()`
completely unchanged.

Rationale: `ingest()` already does parsing, dedup-by-content-hash, profile routing, and
canonicalization for any PGN blob, regardless of source (Phase 3/4). Consuming
structured JSON instead would mean building a second, source-specific parser mapping
that shape into the same canonical fields — a duplicated capability `claude.md` rule 13
forbids, for metadata (richer clock/rating-delta detail) nothing downstream currently
uses. A connector's entire job becomes "fetch PGN text over HTTP," nothing more.
→ `project-plan.md` Phase 14

### D-032 — Phase 15 recommendation-engine mechanics · Locked
`project-plan.md`'s Phase 15 lists "define the recommendation policy" as a task, not a
given — four real product decisions were open before implementation and were resolved
with the owner, all recommended defaults accepted as proposed:

- **Grounding model: hybrid.** `ProfileAnalyticsService`'s existing recurring-weakness
  detection (Phase 8) decides *what* to recommend — deterministic, unchanged. The
  recommendation engine then calls `search_knowledge` against the existing
  tactics/strategy corpus buckets (Phase 7) to pull real study content for that
  weakness, and the LLM phrases it persona-appropriately with citations — the same
  grounding pattern chat (Phase 10) and reports (Phase 9) already use. Rejected: a pure
  hand-curated mapping table (real content to author now, no corpus reuse) and letting
  the LLM generate a plan straight from profile stats with no retrieval step (an
  ungrounded study suggestion is exactly the class of claim rule 8 exists to prevent).
- **Cadence: on-demand only, no scheduler.** "Weekly training plan" is framing
  ("this week's focus"), not a literal recurring job — generated fresh whenever
  requested from current profile data. No new scheduling infrastructure, consistent
  with Phase 17 (hosting/deployment) not having happened yet.
- **Outcome tracking: history only.** Persist what was recommended and when, so a plan
  does not repeat itself and a coach can see history. Automated before/after
  improvement detection was rejected — attributing a later analytics change to one
  specific past recommendation among possibly several is a real causal-inference
  problem, not a lookup, and out of proportion for this phase.
- **Delivery surface: a new report type**, reusing Phase 9's report
  generation/critic/persona infrastructure rather than a new chat tool or a second
  surface — least new infrastructure, most consistent with the existing report pattern.

→ `project-plan.md` Phase 15

---

### D-033 — Agent observability: LangSmith, in Phase 17; classifier evaluation in Phase 16 · Locked

Raised after comparing this project against the sibling `grandmate/` reference app for
deliverables and architecture. Three questions were put to the owner and all three were
answered directly.

**1. LangSmith, not LangTrace.** LangTrace was the initial recommendation on
vendor-neutrality grounds; the owner chose LangSmith. The reasoning that supports that
choice: `langsmith` is already installed as a transitive dependency of `langchain-core`,
so this is configuration rather than new supply chain; its LangGraph integration is
node-aware rather than generic; and the portability an OpenTelemetry stack would buy is
portability away from LangChain, which this project's orchestration layer is built on and
has no plan to leave. ADR-0006's provider-abstraction posture is real but applies to the
*LLM provider*, which sits behind a `Protocol` for exactly that reason — LangGraph never
did. Full reasoning and rejected alternatives in
[ADR-0017](adr/0017-langsmith-tracing-and-langgraph-studio.md).

**2. Phase 17, not a new `P15a` sub-phase.** The original proposal was a separate phase
slotted before Phase 16. The owner placed it in Phase 17 instead. That is the better
fit: Phase 17 already carried "tracing across API, worker, and agent boundaries" as a
deliverable, and a separate sub-phase would have split one concern across two phases
while leaving Phase 17's existing line item ambiguous about whether it had been
satisfied. LangGraph Studio (`backend/langgraph.json`) rides along because it shares the
graph-factory refactor production tracing needs.

**3. The move-classifier accuracy evaluation goes to Phase 16.** The sibling comparison
surfaced a genuine coverage gap that is *not* an observability problem: every layer above
Phase 5 treats the five-way move classification as ground truth, and it has never been
validated against an independent, deeper engine run. `grandmate` does exactly that
(detection F1 0.9294, severity accuracy 0.9073) and — the part worth copying —
deliberately broke its own thresholds to prove the test could fail, watching F1 drop to
0.19. Assigned to Phase 16, where evaluation consolidation already lives, and kept
deliberately separate from Phase 17's tracing work so that "we added tracing" cannot be
mistaken for "we validated the classifier."

**Accepted cost, stated plainly.** LangSmith means user game history and prompt text
leave our infrastructure to a third party. ADR-0013 declined to send that data even to
the user's own browser by default; this is a strictly larger disclosure. It is acceptable
only with redaction reusing dev-insight's existing sanitiser, tracing defaulting to off,
and an explicit privacy statement in the deployment docs. Those are follow-up
requirements in ADR-0017, not optional refinements.

→ `project-plan.md` Phases 16 and 17, [ADR-0017](adr/0017-langsmith-tracing-and-langgraph-studio.md)

---

### D-034 — Phase 16 fine-tuning gate: no-go, evidence-based · Locked

Per `evaluation-strategy.md`'s own framing, fine-tuning is the last lever evaluated, and
only proceeds on a measurable gain the eval set shows that prompting cannot reach, scoped
to persona tone consistency alone — never chess knowledge. The consolidated Phase 16 eval
run (golden sets grown to 30 rows each, all six suites re-run for real, plus the new
tone/persona-fidelity LLM-judge harness) is that evidence:

| Area | Score | In fine-tuning's scope? |
|------|-------|--------------------------|
| `tone_fidelity_rate` (LLM-judged) | 0.92 overall (self-learner 0.89, coach 1.00, kid 0.83) | Yes |
| `kid_safety_rate` | 1.00 (persona reports and training plans) | Yes |
| `fact_invariance_rate` / `top_weakness_invariance_rate` | 0.94 / 0.99 | Yes |
| `single_game_chat` faithfulness/relevancy | 0.71 / 0.63 | No — grounding/retrieval quality |
| `agent_trajectory` faithfulness | 0.52–0.59 | No — same reason |

Prompting alone already reaches 0.92-1.00 on every metric fine-tuning is actually scoped
to touch; there is no ceiling it is visibly hitting. The metrics with real headroom
(chat faithfulness/relevancy) are explicitly out of scope — fine-tuning them would mean
baking chess-adjacent grounding behaviour into weights, which rule 8 and this project's
whole deterministic-core-vs-LLM-layer architecture (ADR-0003) forbid regardless of score.

**Decision: no-go this phase**, confirmed with the owner after the evidence above was
presented, not decided unilaterally. Per `evaluation-strategy.md`'s own words: "if
prompting gets there, no fine-tuning happens and that is a successful outcome, not a
failure." Revisit only if a future tone/persona-fidelity run shows prompting plateauing
below where a real gap opens up.

→ `project-plan.md` Phase 16, `final_docs/v2/evaluation-strategy.md`

---

### D-035 — Phase 16a frontend redesign scope · Locked

Raised by the owner directly: a frontend-only redesign, inserted before Phase 17,
consolidating navigation around "My Dashboard" and "Study Dashboard." Four scope
questions were put to the owner and all four recommended defaults were accepted.

**1. No visual chess board.** Moves render as a styled list (SAN + eval + classification
per ply), not an interactive rendered position. Matches both this app and the sibling
`grandmate/` reference today — a real board is a materially bigger scope (a new
rendering dependency, position-navigation state, board theming) not justified without a
concrete need for it yet.

**2. `react-markdown` for prose rendering**, not a hand-rolled parser. The sibling
reference hand-rolled markdown-like parsing (bullet/paragraph detection) and a
duplicated regex-based chess-notation highlighter in two separate files — a real,
standard library plus one shared, focused highlighting utility on top is less to
maintain and more correct.

**3. Profile-level analytics (`ProfileDashboard`) is the default middle-panel view**
when no game is selected. The panel is never empty; cross-game insight is the natural
default for a dashboard, not a “nothing selected” placeholder.

**4. Memory is a second tab inside the right-hand chat panel**, not a separate page or
menu entry — it is what the assistant remembers about the profile, chat-adjacent by
nature, not a distinct workspace.

**Phase numbering, proposed not decided.** The owner's request read "consider this
phase 17." Implemented as a lettered sub-phase (`P16a`, `claude.md`'s own convention)
inserted before the existing Phase 17 rather than a hard renumber, since renumbering
would invalidate D-033's and ADR-0017's existing by-number references to Phase 17/18.
Flagged explicitly as a proposal in `project-plan.md`'s own Phase 16a section — open to
a real renumber if the owner prefers it over the sub-phase.

**Backend touches, additive only.** Two small backend changes accommodate the redesign
without new functionality: real SAN move notation on the analysis payload (`GameMove.
san` is already stored, Phase 4, but no endpoint returns it), and persisted citations on
stored chat messages (currently only the live turn's response carries them — a reloaded
thread loses citation data). Both are additive fields on existing responses.

→ `project-plan.md` Phase 16a

---

### D-036 — Phase 16a addendum: self-learner-only game report format · Locked

Raised by the owner mid-Phase-16a-review, after spotting a persona report saying "Your
move 19 (Black) was a blunder, costing 99470 centipawns" while checking the redesigned
Analysis tab, and separately asking for a fixed report format with an explicit spec
(headers, word limit, exact classification-word tagging, no engine numbers, third
person). Both were folded into the still-uncommitted `P16a-frontend-redesign` branch at
the owner's direction rather than split into a new phase.

**The centipawn bug** was `domain/analysis/classification.py`'s `_MATE_SCORE_CP =
100_000` sentinel — used correctly to force mate-adjacent swings into the BLUNDER
bucket for classification — being stored and displayed as if it were a real centipawn
count (`MoveEvaluation.eval_swing_cp`) whenever either side of a swing was a forced
mate. Fixed with a new `MoveEvaluation.mate_swing` flag and a `display_swing_cp()`
helper every text-producing consumer now goes through (fallback report text, the LLM
report prompt, the `analysis` RAG bucket's projected text, and chat-agent tool
payloads). Backfilled for existing rows from data already on the table (both sides of a
swing are independently recoverable from adjacent plies' own `mate_in` values), not just
defaulted to false.

**The format request, four scope questions put to the owner:**

**1. Kid keeps its existing gentler format**, not this one. Kid already never says
"blunder" and never blames the player (a locked persona rule) — incompatible with the
new format's literal classification-word tagging requirement. Only self-learner adopts
the new format.

**2. Report tab only, not chat.** The new format's spec described both an "initial game
review" structure and separate "chat follow-up" behavior, but chat's system prompt is
untouched for now — scoped to `domain/reports` (the Analysis tab's report), deferred
extending it to chat's own "review my game" opening message.

**3. Coach stays on its Phase 9 "unbounded, high depth" design**, not the new fixed
2-positive/3-mistake structure — the owner chose not to extend this format to coach when
asked directly, since it would meaningfully cut coach's depth. `critic.py`'s new
self-learner-only rules (a `kind` tag, no second person, the split cap) are gated by a
`report_kind: "game" | "training"` parameter precisely so they can't leak into either
coach or the (self-learner-persona-using) Phase 15 training plan, which shares the same
critic function.

**4. "What Went Well" facts require a landed tactic**, not merely "the engine's top
choice" (`Best-move-facts` question) — a `BEST` classification plus a motif finding on
the mover's own side at that ply. The originally recommended alternative
(`BEST` + `is_critical_moment`) was implemented first, then found — via live
verification against the real dev database, not a test — to structurally never fire (0
of 1928 `BEST` rows were ever also `is_critical_moment`, since that flag is defined by a
large centipawn *loss*, which a best move has essentially none of by construction).
Corrected before shipping; documented in `persona-matrix.md`'s Phase 16a addendum as the
reason `is_critical_moment` was rejected.

**A fifth issue, found during the same live verification, not asked about:** the new
`"kind"` field was described only in prose ahead of the shared JSON output contract;
every real self-learner generation omitted it anyway, because the model pattern-matched
against the contract's own concrete JSON template, which didn't mention `"kind"`. Fixed
by giving self-learner its own copy of the output contract with `"kind"` in the literal
JSON shape, not just a rule stated near it — re-verified against a real LLM call with
zero critic violations after the fix.

→ `final_docs/v2/persona-matrix.md`'s Phase 16a addendum, `project-plan.md` Phase 16a

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
