# Phase 13 Report — Multi-Agent Orchestration

**Date**: 2026-07-29
**Status**: Complete, pending sign-off
**Branch**: `P13-multi-agent-orchestration`

> **Superseded in part — read both addenda at the foot of this document before citing any
> evaluation number above them.**
>
> - **2026-08-02 (D-039):** the comparison that produced the "multi-agent loses" verdict was
>   measuring four handoff defects in the multi-agent graph, plus two harness defects,
>   rather than the architecture.
> - **2026-08-03 (D-040):** three further defects, including one that had disabled every
>   cross-game tool in every run ever recorded.
>
> The headline decision (`chat.py` stays the live path) has survived both. The reasoning
> for it has been rewritten twice.
>
> The scope, files, tests and gaps for that work are in
> [`phase-13a-multi-agent-handoff.md`](phase-13a-multi-agent-handoff.md); the addenda below
> carry the measurement narrative.

## Goal

Decompose coaching requests across specialised agents (Supervisor, Retriever, Chess
analyst, Coach, Critic) coordinated by a supervisor, per `rag-architecture.md` §7 — and
prove, on real evidence, whether that architecture beats the Phase 10 single-agent
baseline before it ever touches live traffic. Per the exit criterion locked into the
plan: if it does not win, that result is recorded and the simpler architecture stays.

## Scope decisions confirmed before implementation (D-029)

Two defaults proposed and confirmed with the owner before coding:

1. **Agent-trajectory evaluation set**: synthetic first, human spot-checked — 12
   scenarios, three per routing category (retrieval only / analysis only / both /
   neither), smaller than the ~30 originally proposed. Flagged as a deliberate scope
   reduction, not a silent one.
2. **Agent budget ceilings**: dedicated `MultiAgentSettings`
   (`MULTI_AGENT_MAX_STEPS=20`, `MULTI_AGENT_MAX_TOOL_CALLS=20`,
   `MULTI_AGENT_TOKEN_BUDGET=60000`), not a reuse of Phase 10's `AgentSettings` — the
   supervisor graph spends that kind of budget across up to five agents in one turn, and
   the single-agent ceiling would starve it before it could fairly compete.

The agent roster and tool subsets were already locked at Phase 0 (`rag-architecture.md`
§7) and were not re-litigated.

## Design

- **Plan-once supervisor, not loop-and-return.** The supervisor classifies
  `needs_retrieval`/`needs_analysis` exactly once per turn; the one real cycle in the
  graph is coach ↔ critic, bounded at 2 attempts (same shape as Phase 10's own
  retry-then-fallback).
- **The critic is `validate_answer`, unchanged from Phase 10 — not a second LLM judge.**
  `rag-architecture.md` §7 lists the critic's tools as `validate_line`/
  `get_game_analysis`, exactly what the Phase 10 guardrail already reaches. Building a
  new LLM-based critic would both duplicate a capability (rule 13) and contradict rule
  8 (chess truth is never asserted by an LLM alone — including one playing critic).
- **Coach has no tools; specialists gather, coach only phrases.** The handoff contract
  the plan calls for: `retrieval_context`/`analysis_context` are read-only input the
  coach cannot add to or fetch itself.
- **Shared, cross-turn ceilings, not one guardrail owning it.** `steps_taken` means the
  same thing `AgentSettings.agent_max_steps` means for the single agent — one LLM call,
  anywhere in the turn — threaded through up to five callers instead of one loop's own
  counter, checked *before* every would-be call rather than after.
- **`search_analysis` assigned to the Retriever, not the Chess analyst** — an
  implementation clarification the Phase 0 table (predating that tool) left open: it
  groups by retrieval *mechanism* (`domain/retrieval`'s hybrid search) rather than
  subject matter, consistent with every Chess analyst tool being a structured
  deterministic lookup instead.
- **Not wired into `ChatService`.** This graph exists to be measured against `chat.py`,
  not to replace it pre-emptively — see Exit criterion result below for why that
  caution was warranted.

## Files created or changed

- `backend/app/core/config/groups.py`, `settings.py`, `__init__.py` — `MultiAgentSettings`
- `backend/.env.example` — `MULTI_AGENT_MAX_STEPS`/`MAX_TOOL_CALLS`/`TOKEN_BUDGET`
- `backend/app/orchestration/agents/specs.py` (new) — the agent roster and tool subsets
- `backend/app/domain/chat/multi_agent_prompts.py` (new) — supervisor/retriever/
  chess-analyst/coach prompts; `prompts.py`'s `_PERSONA_VOICE` promoted to public
  `PERSONA_VOICE` so both modules share one definition instead of a private cross-import
- `backend/app/orchestration/graphs/multi_agent.py` (new) — the supervisor graph
- `backend/tests/test_multi_agent_specs.py`, `test_multi_agent_graph.py` (new) — 11 tests
- `backend/evals/datasets/synthetic/agent_trajectory.jsonl` (new) — 12 scenarios
- `backend/evals/harness/agent_trajectory_dataset.py`, `agent_trajectory_eval.py` (new)
- `backend/evals/suites/agent_trajectory/test_agent_trajectory_quality.py` (new)
- Housekeeping while in the area: `app/mcp/__init__.py`, `app/orchestration/tools/__init__.py`,
  `final_docs/v2/adr/0008-agentic-rag-architecture.md`, `rag-architecture.md` §7 — stale
  MCP-server-direction language corrected to match the Phase 12 reversal (D-027/D-028)

## Tests

20 tests (11 new, plus the full existing hermetic suite re-run for regressions):

- Roster/spec correctness: supervisor/coach/critic have no tools; retriever and chess
  analyst are scoped to exactly their design-table tool subset; every offered tool
  actually dispatches.
- Routing correctness: neither/retrieval-only/analysis-only/both, each producing the
  expected node sequence.
- Handoff/state integrity: a specialist's gathered context reaches the coach unchanged;
  a specialist routing never visits leaves its context key present but empty, not
  absent.
- **Critic catch-rate test**: a fabricated citation is rejected, retried once, then
  falls back — the project-plan's specific "deliberately wrong drafts" requirement,
  covered here (hermetic, `FakeLLMProvider`) rather than in the live evaluation harness,
  where reliably forcing a real model to fabricate isn't a meaningful test.
- **Cost ceiling tests**: a zero step ceiling short-circuits to a grounded fallback with
  *zero* LLM calls made; a token budget sized to fit only the supervisor's own call
  proves the ceiling is a shared running total that stops every downstream agent's spend
  mid-turn, not a per-node allowance.

Result: **20/20 passing.**

## Evaluation — the exit criterion

Real run against `gpt-4o-mini` and Postgres (not a dry run):
`evals/runs/20260729T012314Z_agent_trajectory.json`.

| Metric | Single-agent (Phase 10) | Multi-agent (Phase 13) |
|---|---|---|
| Faithfulness | 0.600 | 0.504 |
| Response Relevancy | 0.406 | 0.118 |
| Grounded rate | 1.000 | 1.000 |
| Avg tool calls/turn | 1.25 | 1.17 |

Routing accuracy (multi-agent's `needs_retrieval`/`needs_analysis` vs. each scenario's
expected routing): **11/12 (0.917)** — the one miss classified a "both" scenario as
analysis-only, a real supervisor judgment call, not a wiring defect.

**Result: multi-agent does not beat the single-agent baseline. Per the pre-committed
exit criterion, the Phase 10 single-agent graph stays the live path — this graph is not
wired into `ChatService`.**

### Why, on inspection of the transcripts

Both paths hit the same structural fact: `validate_answer` only checks citations that
*are present* — an answer with **zero citations trivially passes** the critic regardless
of how unhelpful it is. That creates a hedging incentive, and the two architectures
respond to it differently:

- The **single agent** is in the loop with the tools directly and, even when a claim's
  citation fails validation twice, degrades to the deterministic fallback — which at
  least echoes real tool findings verbatim (`_SOMETHING_FOUND`'s "here is what the
  underlying analysis actually shows").
- The **multi-agent coach** never touches a tool itself and depends entirely on
  whatever the retriever/chess-analyst handed it. When that handoff is thin, the coach's
  cheapest path to a guaranteed-grounded answer is a generic, zero-citation hedge ("I
  currently don't have access to..." — a real example from `ag-motif-at-blunder`) —
  answers RAGAS's Response Relevancy scores near zero, since they don't actually address
  the question.

A second, symmetric limitation: the eval fixtures seed **games only, no knowledge-corpus
chunks**, so `search_knowledge` returns empty results on both paths for every
general-knowledge question. This does not bias the comparison (both architectures face
the identical empty corpus), but it does mean retrieval *quality* itself was never really
exercised here — a real gap for a future dataset iteration, not a defect in this one's
verdict on routing/grounding/relevancy.

### Caveats on the result itself

- **n=12, synthetic, unreviewed** (`reviewed_by` unset on every scenario per D-029) —
  directional evidence, not a statistically powered comparison. `evaluation-strategy.md`'s
  own precedent (D-025, Phase 10's 0.70-vs-0.85 faithfulness run) is that RAGAS judge
  variance is real; this report does not overclaim what 12 scenarios can support.
- The margin here (relevancy 0.406 vs 0.118, faithfulness 0.600 vs 0.504) is large enough,
  and consistent enough across routing categories, that it reads as a real architectural
  effect rather than noise — but a larger, human-reviewed set is the right next step
  before treating this as final.

## Known gaps

- Multi-agent path not promoted to live chat — correctly, per its own result.
- Agent-trajectory dataset needs a human spot-check of a sample before any future score
  from it gates a decision (D-029).
- No knowledge-corpus content seeded in the eval fixtures — retrieval quality itself is
  untested by this harness.
- `final_docs/v2/prd.md` still describes the original MCP-server framing from Phase 0;
  out of this phase's scope (Phase 12's own reversal), noted here so it isn't lost.

## Recommendation

Ready for sign-off. The phase delivered exactly what it set out to: a working,
tested multi-agent implementation, evaluated honestly against its own pre-committed
bar, and a evidence-backed decision *not* to ship it yet — recorded rather than
suppressed. Suggest this stands as Phase 13's outcome (a validated "no" is a successful
result per the plan's own framing, same posture as the fine-tuning gate elsewhere in
this project) rather than iterating further on the architecture within this phase.

---

# Addendum — 2026-08-02: the comparison was measuring bugs

**Status**: re-measured. Verdict unchanged in outcome, invalidated in reasoning.
**Decision record**: D-039.

## Why this was re-opened

The original report explained multi-agent's loss structurally: the coach never touches a
tool, so a thin handoff leaves it hedging. That explanation was correct about the
*mechanism* and wrong about the *cause*. The handoff was thin because of four defects, and
each one is repaired by passing information the single agent had all along.

| # | Defect | Measured symptom |
|---|---|---|
| 1 | Chess analyst's prompt carried no `active_game_id`, but `get_game_analysis`/`list_critical_moments` both **require** `game_id` | `ag-my-opening`, `ag-critical-moment`: **0 tool calls**, relevancy 0.00, against the single agent's 1 call and 0.82/0.72 |
| 2 | Specialists received no thread history | follow-up questions unresolvable |
| 3 | Coach's retry **replaced** the question with the violation feedback | `ag-fork-vs-pin`, `ag-pawn-structure`: "I do not have sufficient information to provide a corrected response" |
| 4 | Coach prompt offered `aggregate`/`critical_moment` citations that `validate_answer` rejects as `unknown kind` | guaranteed violation → retry → (via 3) hedge |

All four converge on the same output: a zero-citation hedge. **A zero-citation answer
passes the critic trivially**, because the critic only checks citations that are present.
The architecture was being scored on that hole.

Two further gaps were parity bugs rather than scoring bugs: the graph had **no
`write_memory` node**, and `recall_memory` was assigned to **no agent**, so flipping
`USE_MULTI_AGENT` silently disabled both halves of Phase 11.

## Results — 3 replicates per side

Same harness, dataset, model and judge on both sides. **The single-agent path is the
control**: it was not modified, so its spread across replicates bounds the harness's own
noise, and any multi-agent movement smaller than that is not a result.

| metric | before (mean ±half-range) | after | Δ |
|---|---|---|---|
| multi faithfulness | 0.666 ±0.021 | **0.713 ±0.049** | +0.047 |
| multi response relevancy | 0.228 ±0.001 | **0.529 ±0.005** | **+0.301** |
| single faithfulness *(control)* | 0.596 ±0.019 | 0.569 ±0.037 | −0.027 |
| single relevancy *(control)* | 0.575 ±0.003 | 0.561 ±0.059 | −0.014 |
| routing accuracy | 0.833 ±0.000 | 0.833 ±0.000 | 0.000 |

Per-scenario, the movement lands exactly where the defects predicted — the four scenarios
that scored 0.00 because a specialist never gathered:

| scenario | category | before | after |
|---|---|---|---|
| `ag-my-opening` | analysis_only | 0.00 | **0.88** |
| `ag-critical-moment` | analysis_only | 0.00 | **0.81** |
| `ag-motif-at-blunder` | both | 0.00 | **0.69** |
| `ag-opening-plan` | both | 0.00 | **0.60** |
| `ag-mistake-and-hanging` | both | 0.00 | **0.62** |
| `ag-fork-vs-pin` / `ag-italian-idea` / `ag-pawn-structure` | retrieval_only | 0.83/0.76/0.90 | 0.83/0.78/0.89 |

Retrieval-only scenarios are unchanged, as expected: none of the four defects touched the
retriever.

## Verdict: still no — but for a different reason

Multi-agent beats single-agent on **faithfulness in 6 of 6 replicates**. The 0.35
relevancy deficit is gone. But the exit criterion requires clearing the baseline on *both*
metrics, and pooled relevancy is now a **tie** (0.529 vs 0.561) that passes in only 1 of 3
replicates. A coin flip is not a win.

> **The "6 of 6" no longer holds.** Later replicates on the same code state had
> single-agent ahead on faithfulness in 3 consecutive runs. Six replicates were enough to
> establish a direction, not to fix a margin this narrow. Read the figure as "multi-agent
> tends to lead on faithfulness", not as a streak. See the second addendum.

**`USE_MULTI_AGENT` stays `false`.** What changed is that the honest description is now
"statistically indistinguishable, with a faithfulness advantage and a relevancy question",
not "multi-agent is worse".

Restricted to the 9 substantive scenarios — dropping the 3 `neither` rows, where RAGAS
relevancy scores a greeting against no meaningful target — multi-agent leads on both
(relevancy 0.677 vs 0.665; faithfulness 0.923 vs 0.759). **This is recorded as an
observation, not as the criterion.** Choosing the slice after seeing the scores is how a
tie gets talked into a win; re-cutting the dataset is a prerequisite for a future verdict,
not a way to settle this one.

## Two harness defects, both of which had corrupted results

1. **A completed run died at `json.dumps`** on a NumPy `bool` (`np.float64` subclasses
   `float` and survives; `np.bool_` does not, and under NumPy 2 reports its type name as
   plain `"bool"`). Every score in that run was lost after it had been paid for.
2. **A run that exhausted `LLM_DAILY_TOKEN_CEILING` mid-way kept going.** Both graphs check
   the budget before every LLM call and degrade to a grounded fallback when it is gone — so
   the run finished, scored the fallbacks, and reported a confident architecture verdict
   built on answers no model produced. One observed run spent 500,970 of a 500,000 ceiling;
   the scenarios after the crossover degraded on *both* paths, which is precisely why it did
   not look like a bug.

The harness now refuses to start a run it cannot afford to finish, and records
`tokens_spent_by_run` and remaining budget in every run file. Both graphs are also built
through the shared `dependencies.py` builders, closing a drift where the multi-agent
`ToolContext` was constructed without `store`.

A third, intermittent fixture defect: the harness invented a random `thread_id`, which
`write_memory` then wrote as `long_term_memory.source_thread_id`, violating an FK whenever
extraction actually produced a memory. It now creates real `chat_threads` rows.

## Test results — 2026-08-02

Full backend CI gate, every step of `.github/workflows/backend.yml`, run locally:

| Step | Result |
|---|---|
| `ruff check .` | pass — all checks passed |
| `ruff format --check .` | pass — 390 files already formatted |
| `mypy app` | pass — no issues in 221 source files |
| `pytest --cov=app` | **917 passed** in 235.88s, 93% total coverage |
| `pytest tests/test_layer_boundaries.py` | pass — 52 passed (ADR-0003) |

`multi_agent.py` sits at 86% line coverage after the change set. The frontend workflow is
not part of this gate: the change set touches no `frontend/**` path, and `frontend.yml` is
path-scoped, so CI would not trigger it.

## Known gaps

> **Two entries below were overtaken by the 2026-08-03 work (D-040) and are kept, struck
> through, as the record of what was believed at the time.** See the second addendum.

- ~~**Routing accuracy is unchanged at 0.833** — 2 of 12 misrouted. The supervisor prompt
  was deliberately not touched, so this measurement stays comparable across the
  before/after.~~ Routing is **0.917**, and the supervisor prompt now carries an
  `is_general_chat` rule. Plan-once routing still cannot escalate when a specialist finds
  nothing, which is the remaining miss.
- ~~**`ag-accuracy-trend` scores 0.00 relevancy on both paths.** It asks for a 10-game
  trend and the fixture seeds one game, so there is no correct answer to give.~~ The
  diagnosis was wrong. The fixture never set `canonicalized_at`, so **no** seeded game was
  visible to any cross-game tool in any run — seeding ten more would have changed nothing.
  Fixed; the scenario now scores 0.93 multi / 0.88 single.
- **The 3 `neither` scenarios are noise on both paths.** RAGAS relevancy is not a meaningful
  quality signal for "see you next time!". They should be scored differently or dropped.
- **`write_memory` is documented as best-effort but is not.** `chat.py`'s docstring says a
  failure there "does not fail the turn"; an exception in the node fails the whole graph
  invocation. Surfaced by the FK violation above. Applies to the single-agent path too, and
  was deliberately **not** changed here — out of scope for a change set whose first
  constraint was not touching the live path.
- **n=12, synthetic, `reviewed_by` still unset.** Three replicates tightened the estimates
  considerably but did not make the set golden (D-029).
- **The single-agent path was not as controlled as this document claims.** It is described
  above as an unmodified control whose spread bounds harness noise. Two changes in this set
  reach it anyway: the fixture now creates real `chat_threads` rows, so `write_memory`
  actually persists on *both* paths, and `strategy/strategic_principles.md` gained a
  checkmate-patterns section that the strategy retriever serves to both. The data shows the
  movement — single-agent relevancy spread went from ±0.003 before (0.579/0.573/0.574) to
  ±0.060 after (0.499/0.565/0.618), and its mean tool-call count rose from 1.08–1.17 to
  1.25–1.58. A control held genuinely constant does not move like that. **The consequence is
  narrow but real**: the *before-vs-after* deltas in the table above are not clean, because
  the two sides differ by more than the four defect fixes. The *within-run* after comparison
  — multi vs single scored in the same run under identical conditions — is unaffected, and
  that is the comparison the exit criterion actually reads. The verdict below stands; the
  before/after Δ column should be read as directional only.

---

# Second addendum — 2026-08-03: routing, and a fixture that never worked

**Status**: re-measured again. Verdict unchanged for the third time; reasoning revised again.
**Decision record**: D-040.

## Why this was re-opened again

The first addendum fixed four handoff defects and concluded the architectures were
"statistically indistinguishable". Reading the per-scenario transcripts rather than the
aggregates turned up three more defects. None of them are in the multi-agent architecture.
Two are in the supervisor's prompt and one is in the evaluation fixture — which is to say
the comparison was *still* not measuring what it claimed to measure.

## 1. The supervisor had no category for non-chess turns

"How does this coaching assistant actually work?" was routed to the retriever, because
`needs_retrieval` is defined as covering "coaching concepts" and a question about a *coach*
reads straight into that. The retriever found nothing and handed the coach an empty context.

A fourth field, `is_general_chat`, now covers greetings, thanks, sign-offs, questions about
the assistant, and questions about the conversation itself. `parse_supervisor_plan` forces
both specialist flags false when it is set — a model that calls a sign-off general chat
while leaving `needs_retrieval` true is contradicting itself, and honouring both fields as
written would send that sign-off to the retriever.

The defaults are deliberately asymmetric: `is_general_chat` defaults `False` while the
specialist flags default `True`. A chess question wrongly marked general is answered with
no facts at all; a general message wrongly marked chess merely wastes a call.

**Routing accuracy: 0.833 → 0.917**, stable in every replicate since.

## 2. An empty context meant two opposite things

"No specialist ran, because nothing needed gathering" and "a specialist ran and found
nothing" arrived at the coach identically, and call for opposite answers — answer directly,
versus say plainly you lack the material. The coach had been re-deriving which case it was
in by reading the question, a judgement the supervisor made one node earlier and discarded.
It is now passed through as state.

The prompt-level carve-outs from the first addendum are **kept** as a misroute safety net,
so a supervisor mistake degrades to the previous behaviour rather than to a hedge.

## 3. The cross-game fixture had never worked, in any run ever recorded

`load_analyzed_games` filters on `Game.canonicalized_at IS NOT NULL`. The harness never set
it. `get_profile_aggregate` therefore returned an empty snapshot on **both** paths for the
entire life of this evaluation.

`ag-accuracy-trend` scored 0.00 relevancy in every run from Phase 13 onward, and both agents
were right every time:

> single: *"It seems that there isn't enough data to analyze your accuracy trend."*
> multi: *"I don't have the material to provide information about your accuracy trend."*

The first addendum called this "a dataset bug — it asks for a 10-game trend and the fixture
seeds one game". That diagnosis was wrong in a way worth recording: seeding ten more games
would have changed nothing, because none of them would have been visible either.

**A wrong fixture reads exactly like a wrong answer.** That is why it survived three rounds
of investigation into why these scenarios scored zero.

The dataset gains an additive `history` field (`v2-2026-08-03-synthetic`). Prior games carry
only a result, colour, classification counts and a date, because the analytics path reads
`GameAnalysis.summary` and never the plies — seeding twenty full move lists would add
thousands of lines of JSON that nothing reads. Accuracy is *computed* from those counts by
the same rule `AnalysisService._summarize` applies, rather than asserted, so a fixture
cannot drift from how production derives the number.

**`ag-accuracy-trend`: 0.00 → 0.93 multi-agent, 0.88 single-agent.** The first scenario
anywhere in this evaluation where multi-agent clearly leads — and, not coincidentally, the
only one that asks a cross-game question.

## An attempted fix that did not work

`ag-motif-at-blunder` — *"where was my critical moment in this game, and what tactical motif
was I missing there?"* — is still routed analysis-only, so the retrieval clause is dropped
and the motif half has no corpus material to answer from. It is the remaining 1-in-12 miss.

A supervisor rule instructing clause-by-clause classification of compound questions was
tried and **moved nothing across four replicates**. It was reverted rather than left in the
prompt as decoration. Recorded here because a dead end that is not written down gets tried
again.

The remaining option is a bounded repair pass: let the coach signal what it is missing, run
the skipped specialist once, re-draft. That is the same shape as the existing coach/critic
retry and would not turn the supervisor into a loop — but it does change what "plan-once
supervisor" means, so it is deferred to its own decision rather than folded in here.

## A regression introduced and caught within this change set

Telling the coach to say plainly when it has nothing was obeyed on *partial* context too.
It began opening answers with "I don't have specific information on whether your opening was
played correctly" and then answering the rest correctly. RAGAS reads the leading disclaimer
and scores the whole answer 0.000; `ag-opening-plan` did exactly that in three consecutive
replicates on substance that had not changed.

The rule now orders the answer — what the context supports first, gaps at the end. That is
better coaching regardless of who is scoring it; the score recovery is a consequence, not
the justification.

## Harness robustness gap, unfixed

One replicate died on a transient `Request timed out` propagating out of the single agent's
`classify_intent` node. There is no retry around transient API failures, so one timeout
discards a full run's completed work — roughly 130k tokens. Same class as the two harness
defects in the first addendum. **Not fixed here**, and recorded as a known gap.

## Results — 3 replicates, v2 dataset, final prompt state

`20260803T160427Z`, `20260803T161304Z`, `20260803T162112Z`. Same harness, dataset, model
and judge on both sides, scored within the same run. No crashes; 394,783 tokens.

| metric | single-agent | multi-agent |
|---|---|---|
| faithfulness | 0.626 (0.589, 0.668, 0.621) | **0.653** (0.720, 0.617, 0.622) |
| response relevancy | **0.676** (0.699, 0.674, 0.657) | 0.548 (0.574, 0.543, 0.526) |
| grounded rate | 100% | 100% |
| avg tool calls / turn | 1.14 | 1.42 |
| routing accuracy | — | **0.917** (0.917, 0.917, 0.917) |

**`USE_MULTI_AGENT` stays `false`.** `multi_agent_wins` is `false` in all three replicates:
multi-agent leads faithfulness by 0.027 and trails relevancy by 0.129, and the exit
criterion requires clearing the baseline on both.

### The relevancy deficit is three scenarios, not a general weakness

| scenario | single | multi | share of the 0.129 gap |
|---|---|---|---|
| `ag-motif-at-blunder` | 0.71 | 0.00 | 46% |
| `ag-opening-plan` | 0.64 | 0.17 | 30% (cumulative 76%) |
| `ag-how-it-works` | 0.57 | 0.32 | 16% (cumulative **92%**) |

The remaining nine scenarios are a wash — multi-agent is ahead on four of them, including
both cross-game and analysis-only rows. Each of the three has a known, specific cause:

1. **`ag-motif-at-blunder` is the misroute.** Routed analysis-only, so the retrieval clause
   never gathers and the motif half cannot be answered. Fix A was the attempt at this and
   failed. Nearly half the headline gap is one unrouted specialist on one scenario.
2. **`ag-opening-plan` is unstable, three different outcomes in three runs** — a good
   answer (0.52), the deterministic fallback after the critic rejected two drafts (0.00),
   and a well-ordered answer that still ends "I don't have specific analysis on the
   correctness of your moves in this game, **but the moves played were classified as best
   according to the analysis**" (0.00). That last one is the interesting failure: the coach
   disclaims and then immediately cites the very thing it disclaimed. The single agent, with
   the same data, simply answered "your opening was played correctly — 100% accuracy, all
   moves classified as best." The disclaimer-ordering rule moved these to the end of the
   answer but does not stop the coach emitting them, and RAGAS's noncommittal classifier
   zeroes the answer wherever the phrase appears.
3. **`ag-how-it-works` is not a chess question at all.** Both paths answer it correctly;
   RAGAS scores a description of the assistant against no meaningful target.

### Read this against the first addendum's numbers with care

The gap looks wider than the first addendum's (0.548 vs 0.676, against 0.529 vs 0.561), but
the movement is almost entirely **single-agent improving**, from ~0.56 to 0.676. The
fixture and prompt fixes in this change set are path-neutral by construction, and they
handed single-agent two scenarios it had been scoring 0.00 on — `ag-accuracy-trend`
(0.00 → 0.89) and `ag-motif-at-blunder` (0.00 → 0.71). Multi-agent gained the first and
still cannot route the second. **Fixing the measurement helped the simpler architecture
more, because the remaining defect is one multi-agent only has.**

### What would change the verdict

Not a better coach prompt. On the evidence here, closing `ag-motif-at-blunder` alone would
recover ~46% of the deficit, and it needs the supervisor to be able to escalate when a
specialist finds nothing — the bounded repair pass deferred above. That, plus cross-game
scenarios beyond the single one this set now has, is the honest prerequisite for a
re-decision. Neither is in this change set.
