# Phase 13a Report — Multi-Agent Handoff and Evaluation Repair

**Date**: 2026-08-03
**Status**: Complete, pending sign-off
**Branch**: `P13a-multi-agent-handoff`
**Decision records**: D-039, D-040

## Goal

Phase 13 recorded that multi-agent lost to the single-agent baseline. This sub-phase asked
a narrower question: **was that result measuring the architecture, or was it measuring
defects?**

It turned out to be defects — seven of them, across two rounds of investigation. The
verdict never moved. `use_multi_agent` stays `false` and `chat.py` keeps serving live
traffic, exactly as Phase 13 concluded. What changed is that the reason is now true.

The measurement narrative lives in the two addenda to
[`phase-13-multi-agent-orchestration.md`](phase-13-multi-agent-orchestration.md), which is
where the before/after tables belong. This report covers scope, files, tests, and gaps.

## What was fixed

### Round one — four handoff defects, plus two harness defects (D-039)

1. **The chess analyst was never told the open game id.** `get_game_analysis` and
   `list_critical_moments` both take a required `game_id`; its prompt carried none, so it
   answered questions about the user's own game with zero tool calls.
2. **Specialists received no thread history**, so follow-ups were unresolvable.
3. **The coach's retry replaced the question with the violation feedback**, leaving the
   second attempt nothing to answer.
4. **The coach was told to emit two citation kinds `validate_answer` rejects outright** —
   a guaranteed violation, hence a retry, hence (by 3) a hedge.

All four converge on a zero-citation hedge, and **a zero-citation answer passes the critic
trivially**, because the critic only checks citations that exist.

Two parity gaps were found alongside them: the graph had **no `write_memory` node**, and
`recall_memory` was assigned to **no agent**, so flipping `use_multi_agent` silently
disabled both halves of Phase 11.

The harness itself had two defects that had already destroyed results: a completed run
died at `json.dumps` on a NumPy `bool`, and a run that exhausted `LLM_DAILY_TOKEN_CEILING`
mid-way kept going while both graphs degraded silently to fallbacks.

### Round two — routing, and a fixture that never worked (D-040)

5. **The supervisor had no category for non-chess turns.** "How does this coaching
   assistant actually work?" routed to the retriever, because `needs_retrieval` covers
   "coaching concepts" and a question about a *coach* reads into that. A fourth field,
   `is_general_chat`, now covers greetings, sign-offs, questions about the assistant, and
   questions about the conversation. **Routing accuracy 0.833 → 0.917.**
6. **An empty context meant two opposite things** — "nothing needed gathering" and
   "gathering found nothing" — which call for opposite answers. The coach had been
   re-deriving which case it was in from the question, a judgement the supervisor made one
   node earlier and discarded. It is now passed through as state.
7. **The cross-game fixture had never worked, in any run ever recorded.**
   `load_analyzed_games` filters on `Game.canonicalized_at IS NOT NULL` and the harness
   never set it, so `get_profile_aggregate` returned an empty snapshot on **both** paths
   for the entire life of this evaluation. `ag-accuracy-trend` scored 0.00 in every run and
   both agents were right every time — they had no games to aggregate.
   **0.00 → 0.93 multi / 0.88 single.**

Defect 7 is the one that matters beyond this phase. Cross-game self-pattern finding is a
stated product priority and this evaluation had never once exercised it.

## Files created or changed

**Graph and prompts**
- `app/domain/chat/multi_agent_prompts.py` — `active_game_id` and thread history reach the
  specialists; `is_general_chat` added to the supervisor contract; coach turn-note split
  into general-chat and chess-turn variants; citation kinds corrected
- `app/orchestration/graphs/multi_agent.py` — `write_memory` node; `is_general_chat`
  threaded into state and into the coach prompt; retry keeps the question
- `app/orchestration/agents/specs.py` — `recall_memory` assigned to the Retriever
- `app/orchestration/dependencies.py` — shared builders so both graphs are constructed the
  same way (rule 13); closes a drift where multi-agent's `ToolContext` lacked `store`
- `app/domain/llm_usage/service.py` — `today_usage()` made public for the harness's
  pre-flight budget check

**Evaluation**
- `evals/harness/agent_trajectory_eval.py` — pre-flight budget refusal, token accounting,
  `json.dumps` hardening, real `chat_threads` rows, `canonicalized_at`/`played_at`/
  `focus_color` on seeded games, a real summary on the active game, history seeding
- `evals/harness/agent_trajectory_dataset.py` — `HistoryGameFixture`, additive `history`
  field, dataset version `v2-2026-08-03-synthetic`
- `evals/datasets/synthetic/agent_trajectory.jsonl` — 20 prior games for `ag-accuracy-trend`
- `evals/runs/` — three final replicates

**Corpus and docs**
- `data/corpus/tactics/check_patterns.md` (new) + `PROVENANCE.md` entry
- `docs/diagrams/multi_agent_graph.mermaid` — `write_memory` node
- `docs/evaluation_report.md` — regenerated from the final runs
- `final_docs/v2/decisions-log.md` — D-040
- `final_docs/v2/phase-reports/phase-13-multi-agent-orchestration.md` — second addendum,
  plus corrections to two "Known gaps" entries and the "6 of 6 replicates" claim

## Tests

**941 passing**, 93% coverage. New in this phase:

- `tests/test_multi_agent_prompts.py` (new) — the coach's carve-outs; `is_general_chat`
  suppressing both specialists even on contradictory model output; unparseable output
  gathering broadly rather than answering from nothing; the disclaimer-ordering rule
- `tests/test_agent_trajectory_fixtures.py` (new) — accuracy derived from counts rather
  than asserted; the trend scenario spanning two analytics windows; distinct `days_ago`;
  a detectable trend; single-game scenarios still loading with empty history
- `tests/test_multi_agent_graph.py` — analyst told the game id; specialists receive thread
  history; retry keeps the question; `write_memory` runs after the answer is final; a
  general-chat turn reaches the coach labelled as such; a budget-exhausted turn is *not*

The fixture tests exist because of defect 7 specifically: **a wrong fixture reads exactly
like a wrong answer**, which is why it survived three rounds of investigation into why
those scenarios scored zero.

## Evaluation

Three replicates, v2 dataset, final prompt state. No crashes, 394,783 tokens.

| metric | single-agent | multi-agent |
|---|---|---|
| faithfulness | 0.626 | **0.653** |
| response relevancy | **0.676** | 0.548 |
| routing accuracy | — | **0.917** ×3 |

**`multi_agent_wins` is `false` in all three.** Multi-agent leads faithfulness by 0.027 and
trails relevancy by 0.129; the exit criterion requires clearing the baseline on both.

**92% of the relevancy deficit is three scenarios** — `ag-motif-at-blunder` (46%, the
misroute), `ag-opening-plan` (30%, unstable across runs), and `ag-how-it-works` (16%, not a
chess question). The other nine are a wash, with multi-agent ahead on four.

The gap reads wider than the first addendum's because **single-agent improved**, ~0.56 →
0.676. The fixes here are path-neutral by construction and handed single-agent two
scenarios it had been scoring 0.00 on; multi-agent gained one and still cannot route the
other. Fixing the measurement helped the simpler architecture more, because the remaining
defect is one only multi-agent has.

## Known gaps

- **`ag-motif-at-blunder` still misroutes.** A supervisor rule to classify compound
  questions clause by clause was tried and moved nothing across four replicates; it was
  reverted rather than left in the prompt. Recorded as a dead end so it is not retried.
  The remaining option is a bounded repair pass — let the coach signal what it is missing
  and run the skipped specialist once — which changes what "plan-once supervisor" means and
  is deferred to its own decision.
- **The disclaimer-ordering rule helps but does not hold.** One replicate produced "I don't
  have specific analysis on the correctness of your moves in this game, but the moves
  played were classified as best according to the analysis" — disclaiming and then citing
  the thing disclaimed. RAGAS zeroes the answer wherever the phrase appears.
- **The harness has no retry on transient API failures.** One `Request timed out`
  propagating out of a graph node discards a full run's completed work, roughly 130k
  tokens. Observed once during this phase. Same class as the two harness defects in D-039.
- **Only one cross-game scenario exists**, now that cross-game tools work at all. It is
  also the scenario where multi-agent most clearly leads, which makes the absence of others
  the most valuable gap to close next.
- **`write_memory` is documented as best-effort but is not.** An exception in the node
  fails the whole graph invocation. Applies to the single-agent path too; deliberately not
  changed here, since this change set's first constraint was not touching the live path.
- **n=12, synthetic, `reviewed_by` still unset** (D-029). Replicates tightened the
  estimates; they did not make the set golden.

## Recommendation

Ready for sign-off. The phase delivered what it set out to: seven defects found and fixed,
a dead end recorded rather than hidden, and a verdict that survived three separate attempts
to overturn it — now resting on a measurement that tests what it claims to.

Two follow-ups are worth their own scope rather than being folded in here: **cross-game
scenarios**, which the evidence now says is where multi-agent's advantage would show if it
exists, and the **bounded repair pass** for the remaining misroute. Together they are the
honest prerequisite for any re-decision on `use_multi_agent`.
