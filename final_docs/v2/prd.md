# GrandMate v2 — Product Requirements

Status: Phase 0 draft, pending sign-off.

## 1. Problem

A club player finishes a game, runs the engine, sees `-2.4` at move 23, and learns almost
nothing. Engine output tells you *what* changed, not *why you keep doing it*. Playing
platforms optimise for the game you just played; nobody optimises for the pattern across
your last sixty.

Coaches solve this, but a coach reviewing thirty games by hand is expensive and slow. A
parent watching a child's rating chart has no idea whether the child is improving in ways
that matter. A player studying alone cannot tell a one-off blunder from a habit.

## 2. What GrandMate is

A companion layer over the platforms people already play on. It ingests games, computes
deterministic engine-backed analysis, detects recurring patterns across many games, and
explains findings differently depending on who is reading.

Two engineering halves, deliberately kept apart:

- a **deterministic chess core** that must be reproducible and boring, and
- an **agentic RAG layer** that must be grounded, observable, and continuously evaluated.

The core computes what is true. The agent decides what to retrieve and how to say it.

## 3. What GrandMate is not

- Not a chess engine. Stockfish is a dependency, not a differentiator.
- Not a playing platform. No game hosting, no matchmaking.
- Not an opening database product.
- Not a replacement for a human coach. It is leverage for one.

## 4. Users

| User | Wants | Persona served |
|------|-------|----------------|
| Club player, self-directed | To know which mistakes are habits, and what to drill | self-learner |
| Coach with several students | Fast per-student prep before a lesson | coach |
| Junior player | Feedback they can actually read and act on | kid |
| Parent of a junior | Whether the child is genuinely improving | deferred |
| Tournament preparer | An opponent's tendencies | deferred |

MVP serves the first three. The persona layer is built so the last two are additions, not
rewrites.

## 5. Core principle: three truth levels

1. **Game Analysis Object** — one enriched, deterministic object per game.
2. **Profile Aggregate Object** — trends and recurring patterns across a window of games.
3. **Persona View / Chat Layer** — different explanations over identical underlying facts.

Personas change language, depth, framing, and recommendations. They never change chess
truth. This is testable and is tested: the persona fidelity suite asserts that the same
analysis facts appear across all persona renderings of the same game.

## 6. MVP scope

### In scope

**Identity**
- Log in with Lichess (OAuth2 PKCE)
- Link a Chess.com username
- Own-profile dashboard on login
- Separate, permission-gated page for viewing another player

**Ingestion**
- Upload a PGN file
- Paste PGN text
- Batch upload
- Import recent games from Lichess (authenticated) and Chess.com (public archives)
- Deduplication across all sources

**Analysis**
- Canonical game object with per-ply FEN/EPD
- Stockfish evaluation, baseline depth 12, tiered deep pass on critical moments
- Move classification: best, good, inaccuracy, mistake, blunder
- Critical moment extraction
- Opening/ECO identification via EPD lookup
- Tactical motif and strategic theme detection with confidence scores

**Profile analytics**
- Windows over the last 10 / 30 / 60 games
- Recurring weakness detection
- Opening-family performance
- Colour and time-control segmentation
- Progress deltas

**Knowledge and chat**
- Curated, attributed, multi-bucket knowledge corpus
- Hybrid retrieval, dense + sparse, with bucket routing
- Agentic chat that selects its own retrieval strategy
- Short-term thread memory and long-term profile memory, kept separate
- Grounding guardrail rejecting claims not supported by analysis

**Reporting**
- In-app HTML reports per persona
- Training plan generation

**Platform**
- MCP server exposing analysis and retrieval tools
- Recorded, trended evaluation scores

### Out of scope for MVP
- PDF export
- Parent and analyst personas
- Chess.com OAuth login
- Real-time collaborative coach views
- Mobile native apps
- Payment and subscriptions

## 7. Primary user journeys

**J1 — First login.** User visits GrandMate, clicks "Log in with Lichess", authorises,
returns to a dashboard. The dashboard is empty and prompts an import.

**J2 — Import and analyse.** User imports their last 30 Lichess games. A job runs. Progress
is visible. On completion the dashboard shows aggregate patterns.

**J3 — Single game review.** User opens one game, steps through moves, sees critical
moments flagged with evaluation swings and detected motifs.

**J4 — Ask about a game.** In chat on a game, the user asks "why was 23...Nxe4 bad?" The
agent retrieves that game's analysis, retrieves motif knowledge if needed, and answers
citing the actual evaluation swing and the actual continuation.

**J5 — Ask about a habit.** User asks "what do I keep getting wrong?" The agent retrieves
the profile aggregate rather than a single game and answers with frequency evidence.

**J6 — Switch persona.** A coach viewing a student toggles from coach to kid persona. The
facts stay identical; the wording, depth, and recommendations change.

**J7 — Coach views a student.** A coach opens the separate player-view page for a linked
student, seeing the same analysis surfaces under a permission gate.

**J8 — Memory continuity.** A user returns days later. The assistant recalls their stated
preference for concise answers and their standing goal of fixing time trouble, without
having been re-told.

**J9 — Upload a PGN.** A user with games from neither platform pastes a PGN and gets the
same analysis pipeline.

## 8. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Modularity | No god files or god services. Domain logic in domain modules. |
| Reproducibility | Identical engine settings on the same game produce identical classifications. |
| Separation | Deterministic analysis never imports prompt-building code, and vice versa. |
| Isolation | Profile-scoped retrieval enforced at the retriever interface, tested in CI. |
| Configuration | Zero hardcoded secrets or tunables. |
| Observability | Structured logs with request and trace ids across API, worker, and agent. |
| Cost control | Step ceilings and token budgets on every agent path. |
| Auditability | Every evaluation run recorded, versioned, and trended. |
| Testability | Every phase ships unit, integration, and where user-visible, E2E coverage. |

## 9. Success criteria

The product succeeds when a user can log in with Lichess, import their recent games, ask
"what do I keep getting wrong", and receive an answer that is specific, grounded in their
actual games, correct about the chess, and phrased appropriately for who is asking — with
evaluation scores proving the grounding rather than impressions asserting it.

## 10. Open questions

Tracked in `decisions-log.md` under "Open questions raised back to the owner".
