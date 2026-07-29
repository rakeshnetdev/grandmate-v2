# Phase 13 Report — Multi-Agent Orchestration

**Date**: 2026-07-29
**Status**: Complete, pending sign-off
**Branch**: `P13-multi-agent-orchestration`

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
