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

---

## Open questions raised back to the owner

Recorded here so they are not lost between phases.

| # | Question | Needed by |
|---|----------|-----------|
| Q-1 | Confirm `gpt-4o-mini` is the intended model (the request read "gpt-40-min") | Phase 1 |
| Q-2 | Supabase local project details and service role key | Phase 2 |
| Q-3 | Should email/password be offered as a fallback login for users with neither platform account? | Phase 2 |
| Q-4 | Is there a monthly LLM spend ceiling to encode as a hard guardrail? | Phase 1 |
| Q-5 | Should the kid persona have an age band, which affects reading level targets? | Phase 9 |
