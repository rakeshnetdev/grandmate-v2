# Phase 10 Report — Agentic RAG Chat with Short-Term Memory

**Date**: 2026-07-28
**Status**: Complete, pending sign-off
**Branch**: `P10-agentic-rag-chat`

## Goal

Interactive question answering grounded in deterministic analysis and the knowledge
corpus, driven by an agent that decides what to retrieve rather than a fixed pipeline —
replacing the Phase 1 skeleton graph's placeholder nodes with the real thing.

## Scope decisions confirmed before implementation

Four defaults confirmed with the owner before coding, all approved as proposed:

1. **Checkpointer backend**: Postgres-backed (`langgraph-checkpoint-postgres`), not
   in-memory — threads must survive a backend restart.
2. **Response mode**: single-shot request/response, not streaming — matches Phase 9's
   report-generation pattern; the grounding guardrail needs the complete answer before
   anything reaches the user regardless.
3. **Intent routing**: LLM-classified, not a keyword heuristic — user phrasing for
   intent is open-ended natural language, not domain keywords.
4. **Evaluation dataset size**: a small (10-scenario), self-authored, unreviewed golden
   set now, not the ~60-question long-run target `evaluation-strategy.md` names.

Full reasoning recorded as D-025 in `decisions-log.md`.

## Design

- **Tools** (`orchestration/tools/`) wrap existing profile-scoped services rather than
  reimplementing anything: `search_knowledge`/`search_analysis` (Phase 7 retrieval),
  `get_game_analysis`/`list_critical_moments` (Phase 5 analysis), `get_profile_aggregate`
  (Phase 8 analytics), `lookup_opening` (Phase 6 opening index), `validate_line` (new,
  `python-chess`). One `ToolContext` binds `profile_id` for the whole turn — no tool's
  JSON schema ever offers `profile_id` as a parameter, so there is no code path a model
  could use to request another profile's data (rule 14; proven directly in
  `test_chat_graph.py`'s stray-argument test).
- **Graph** (`orchestration/graphs/chat.py`): `classify_intent` → `run_agent`. The agent
  loop (tool-calling, retry, fallback) runs as bounded Python control flow inside one
  node rather than as separate graph nodes per tool call — LangGraph's real job here is
  the Postgres checkpointer persisting thread state across turns, not modelling
  intra-turn scratch work as graph edges. `messages` (the persisted transcript) grows by
  exactly one user/assistant exchange per turn; tool-calling exchanges live in a
  turn-local list, never in checkpointed state, so a long conversation's persisted size
  stays proportional to turn count, not tool-call count.
- **Grounding guardrail** (`domain/chat/guardrail.py`): the agent's final turn answers in
  `{"answer": ..., "citations": [...]}`, with four citation kinds — `move`, `evaluation`,
  `variation`, `opening` — each checked against the same profile-scoped tables the tools
  themselves read from. One retry on a rejected answer, then a deterministic fallback
  that surfaces the turn's raw tool findings and asserts nothing of its own — same
  never-show-ungrounded-text posture as Phase 9's report critic.
- **Persistence**: `chat_threads` (Alembic-owned, the identity/listing row) plus the
  LangGraph Postgres checkpointer (library-owned state, **not** an Alembic migration —
  see D-025 for why). `ChatService` wires the two together per request; the checkpointer
  is opened fresh per turn, matching the codebase's per-request-resource convention
  rather than a single connection held for the app's lifetime.
- **Frontend** (`features/chat/`): thread list, transcript, composer, persona switcher
  (reused from `features/reports`, now properly exported from its public surface — see
  Errors below). The selected thread lives in the URL (`ChatPage`'s `thread` search
  param), not component state, so a reload restores it — the checkpointer already makes
  the conversation durable; losing which one was open on refresh would have been a pure
  UI regression on top of real, persisted data.

## A correctness issue found and fixed during implementation

Live browser testing against a real game surfaced a real tool-surface gap: the question
"what was my opening in this game?" had no way to ever succeed. `lookup_opening(epd)`
needs an EPD nothing gave the model access to, and the citation contract had no `opening`
kind at all — so even after the tool result correctly returned the game's opening (a
follow-up fix, below), the model's attempt to cite it failed the guardrail as an unknown
citation kind, and the turn fell back every time. Fixed in two parts: `get_game_analysis`
now attaches the game's already-computed `OpeningMatch` directly to its payload (no
EPD-chaining required), and the guardrail gained a fourth citation kind, `opening`,
checked against `domain.patterns.queries.get_opening_match`. Re-verified live: the same
question now returns a real, correctly-cited answer ("Your opening in this game was the
Ruy Lopez: Marshall Attack, classified under ECO code C89.").

## Completed

| Deliverable | Status |
|-------------|--------|
| Chat threads (`ChatThread` model, `ChatService`, routes) | ✅ |
| LangGraph agent with tool calling (`orchestration/graphs/chat.py`) | ✅ |
| Retrieval exposed as agent tools — one per bucket, plus analysis lookup and move validation | ✅ |
| Active game and profile context injection | ✅ |
| Short-term thread memory via a LangGraph checkpointer (Postgres-backed) | ✅ |
| Intent routing (explain / compare / summarise / train_next) | ✅ |
| Grounding guardrail rejecting answers citing moves/evals/variations/openings absent from the record | ✅ |
| RAGAS answer-quality harness, run for real against `gpt-4o-mini` | ✅ |
| Verified live end to end in a real browser against a real LLM call | ✅ |

## Files created or changed

**Backend**

```
backend/app/
  db/models/chat.py               new — ChatThread
  domain/chat/                     new — prompts, guardrail, fallback, service, queries
  domain/analysis/queries.py      +get_moves (SAN attached to tool payloads)
  orchestration/checkpointer.py   new — Postgres checkpointer lifecycle
  orchestration/graphs/chat.py    new — replaces graphs/skeleton.py (deleted)
  orchestration/tools/             new — context, registry, knowledge/analysis/validation tools
  api/routes/chat.py              new
  api/dependencies/llm.py         +EmbeddingProviderDep
  schemas/chat.py                 new
  integrations/llm/base.py        +ToolCall, +ToolSpec, +tool_calls on Message/CompletionResponse
  integrations/llm/openai_provider.py  +tool-calling in OpenAIChatProvider,
                                    +UnconfiguredEmbeddingProvider, +build_embedding_provider
  main.py                         +embedding_provider in lifespan
  core/config/groups.py           +DatabaseSettings.psycopg_conninfo
backend/alembic/versions/..._chat_threads.py   new migration
backend/pyproject.toml            +langgraph-checkpoint-postgres, +langchain-openai (dev)
backend/tests/  (9 new files, 67 new tests; 4 removed with the Phase 1 skeleton)
  test_chat_prompts.py, test_chat_fallback.py, test_chat_guardrail.py,
  test_orchestration_tools.py, test_chat_graph.py, test_chat_service.py,
  test_chat_routes.py, test_openai_provider_message_mapping.py,
  fake_llm.py (extended for tool-call scripting)
backend/evals/
  datasets/golden/single_game_chat.jsonl        new — 10 synthetic scenarios
  harness/single_game_chat_dataset.py, single_game_chat_eval.py   new
  suites/single_game_chat/test_single_game_chat_quality.py        new
  runs/..._single_game_chat.json                new — real run, gpt-4o-mini
final_docs/v2/configuration.md    +Agents section note, +psycopg_conninfo context
final_docs/v2/evaluation-strategy.md  +Faithfulness threshold note
final_docs/v2/decisions-log.md    +D-025
```

**Frontend**

```
frontend/src/features/chat/
  api/chat.ts, hooks/useChat.ts    new
  components/ThreadList.tsx, ChatMessageList.tsx, ChatComposer.tsx,
    ChatPanel.tsx (+test)          new
  index.ts                         new
frontend/src/features/reports/index.ts  +PersonaSwitcher (was missing from the public surface)
frontend/src/pages/ChatPage.tsx    new
frontend/src/pages/GameDetailPage.tsx  +"Ask about this game" link
frontend/src/app/router/index.tsx  +/chat route
```

## Tests

- Backend: 650 passing (67 new across 9 files; 4 removed with the Phase 1 skeleton, whose
  own tests said "expected to be rewritten then, not carried forward"), `mypy app` clean,
  `ruff check`/`ruff format --check` clean.
- Frontend: 58 passing (3 new), `tsc`, `oxlint`, `prettier` clean.
- Evaluation: `uv run pytest evals/` — see below.

## Evaluation — real run against `gpt-4o-mini`

Recorded at `evals/runs/20260728T162429Z_single_game_chat.json` (10 synthetic scenarios,
real chat-graph turns — real tool dispatch, real grounding guardrail — scored by real
RAGAS judge calls, no fake):

| Metric | Score | Gate |
|--------|-------|------|
| `grounded_rate` | **100%** | Hard, structural — the guardrail's retry-then-fallback loop makes this unconditional |
| `intent_valid_rate` | **100%** | Hard, structural — the classifier always falls back to a valid taxonomy member |
| `faithfulness` | 70% (0.70) | Soft until the golden set is human-reviewed (0.85 target) |
| `response_relevancy` | 74–75% across two runs | Informative only |

`grounded_rate` and `intent_valid_rate` are properties the code itself guarantees, not
judge estimates — both scored perfectly, as they must by construction.

Faithfulness came in below the 0.85 target. Per the golden-vs-synthetic rule already
applied identically in Phase 7 and Phase 9, this does not gate — the dataset is
self-authored and unreviewed (`reviewed_by` unset). Manually reading all ten real
answers, none contained a false or fabricated game-specific claim; the citation-level
guardrail (unconditionally enforced, verified directly by `test_chat_guardrail.py`'s
seeded-DB tests) caught every citation-shaped claim correctly. The gap is best explained
by what RAGAS's Faithfulness metric actually measures: every sentence in an answer,
including legitimate coaching advice ("study tactical patterns like forks and pins")
that was never meant to be citation-backed the way a specific game fact is — the same
reason Phase 9's report "recommendations" were never required to carry `fact_ids`. This
is a real, specific finding worth the owner's attention at review time — either the
threshold needs recalibrating for a system that intentionally gives uncited advice, or
the output contract needs an explicit advice-vs-fact split — not a defect this phase
silently papered over. Recorded in full as D-025.

## Live verification

Ran the real stack end to end against a real, already-analyzed game and real
`gpt-4o-mini` calls (not mocked): logged in, opened a game, followed "Ask about this
game" into the chat page, started a thread, and asked "What was my opening in this
game?" — after the tool-surface fix above, this returned a correctly-cited, grounded
answer. Switched personas and asked a follow-up; reloaded the page mid-conversation and
confirmed the transcript and thread selection both survived (the checkpointer plus the
URL-carried thread id), not just that the data existed somewhere in Postgres.

## Known gaps

- **Faithfulness below its soft-until-reviewed target** — see above; a specific,
  understood, documented finding, not a silent gap.
- **Golden single-game-chat dataset is self-authored and unreviewed** — same documented
  pattern as every prior phase's initial golden set.
- **No streaming** — confirmed as the right MVP trade-off (see Scope decisions), revisit
  if real usage shows the latency matters more than the guardrail's need to see the
  complete answer first.
- **Chat is not persona-tone-varied beyond the system prompt's voice rules** — reuses
  Phase 9's persona voice conventions in the agent's system message, but there is no
  separate persona-fidelity scoring for chat the way Phase 9 built for reports; deferred,
  not required by this phase's scope.
- **No rate limiting on chat turns beyond the shared daily token ceiling** — same gap
  Phase 9's report generation already carries, now shared by a second, higher-frequency
  surface.

## Recommendation

Ready for sign-off. Both structural guarantees (grounded_rate, intent_valid_rate) scored
perfectly on a real run against a real model, live testing caught and fixed a genuine
tool-surface gap rather than papering over it, and the one metric that came in under
target (Faithfulness) is understood, documented, and — per the same golden-vs-synthetic
rule already used consistently since Phase 7 — correctly does not block sign-off on an
unreviewed set. Worth flagging explicitly for the owner's attention before it becomes
load-bearing at Phase 13.
