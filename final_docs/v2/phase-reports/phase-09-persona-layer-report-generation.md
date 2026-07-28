# Phase 9 Report — Persona Layer and Report Generation

**Date**: 2026-07-28
**Status**: Complete, pending sign-off
**Branch**: `P9-persona-layer-report-generation`

## Goal

Render the same analysis facts differently for three audiences (self-learner, coach,
kid) without ever changing the underlying truth — the first phase to make a real LLM
completion call (Phase 7 built RAG infrastructure with no consumer; embeddings are the
only prior LLM-adjacent spend).

## Scope decisions confirmed before implementation

1. **Scope**: per-game reports only. Phase 8's aggregate/profile-level data does not get
   a persona report in this phase — a smaller surface to prove the grounding/critic
   pattern on before extending it.
2. **Critic failure handling**: one retry on an ungrounded LLM response, then fall back
   to a deterministic, facts-only report — never an error surfaced to the reader.
3. **Persistence**: reports are stored and versioned (`GameReport`, keyed by
   `analysis_version`), same pattern as `GameAnalysis`/`ProfileAggregateSnapshot`.
4. **LLM daily spend ceiling** (Q-4, open since Phase 1): enforced starting now, since
   this is the first real completion spend. Default 500,000 tokens/day (D-022).
5. **Kid persona age bands** (Q-5, open since Phase 0): stays deferred — one kid persona
   for the whole 8-14 range, matching D-002's locked MVP scope (D-024).

## A correctness issue found and fixed during implementation

Building recurring-weakness-style logic for report facts required the same "is this
finding the player's own problem" polarity judgement Phase 8 already solved
(`domain/analytics/metrics.py`'s private `_SELF_INFLICTED_MOTIFS`/`_WEAKNESS_THEMES`
tables). Rather than re-derive (and risk silently diverging from) that judgement call, it
was extracted to a shared `domain/patterns/polarity.py` module both Phase 8's analytics
and Phase 9's report facts now import — refactored with the full existing Phase 8 test
suite (37 tests) re-run to confirm zero behaviour change, plus 7 new dedicated tests for
the extracted module itself.

A second real bug was caught by running the full test suite, not just changed files:
constructing `OpenAIChatProvider` unconditionally at app startup broke every test/route
that never touches an LLM at all (`test_health.py`, `test_devinsight_api.py`) whenever
`OPENAI_API_KEY` is blank — the OpenAI SDK raises immediately on an empty key rather than
deferring to first use. Fixed with `UnconfiguredLLMProvider`, a stand-in that lets the
app start regardless and only fails — with a clear, actionable message — if something
actually tries to generate a completion, matching this app's own stated "permissive in
development" posture (`app/main.py`'s lifespan docstring).

## Completed

| Deliverable | Status |
|-------------|--------|
| `OpenAIChatProvider` — first real `LLMProvider.complete()` implementation | ✅ |
| `LLMBudgetTracker` — atomic daily token ceiling (Postgres upsert, not read-then-write) | ✅ |
| `domain/reports/facts.py` — structured, stably-IDed facts extracted from analysis + patterns | ✅ |
| `domain/patterns/polarity.py` — motif/theme "whose problem is this" logic, shared with Phase 8 | ✅ |
| `domain/reports/selection.py` — persona-specific ranking and capping (self ≤5, kid ≤3 + confidence floor, coach unbounded) | ✅ |
| `domain/reports/prompts.py` — persona system prompts + strict JSON output contract | ✅ |
| `domain/reports/critic.py` — deterministic grounding checks (fact-id existence, finding caps, kid centipawn suppression) | ✅ |
| `domain/reports/fallback.py` — deterministic, LLM-free report builder, persona-aware wording | ✅ |
| `domain/reports/service.py` — get-or-generate orchestration: budget check → attempt → critic → retry → fallback | ✅ |
| `GameReport` — versioned storage | ✅ |
| `GET /api/v1/reports/games/{id}?persona=` — profile-scoped (Phase 8b `ScopedProfileIdDep`) | ✅ |
| Frontend: persona switcher, report view (with source transparency badge), wired into the game detail page | ✅ |
| Persona fidelity evaluation harness — run for real against `gpt-4o-mini` | ✅ |
| Verified live end to end in a real browser against a real LLM call | ✅ |

## Files created or changed

**Backend**

```
backend/app/
  db/models/llm_usage.py         new — LLMUsageDaily
  db/models/reports.py           new — GameReport, ReportSource
  domain/llm_usage/               new — LLMBudgetTracker
  domain/patterns/polarity.py    new — extracted from analytics/metrics.py
  domain/analytics/metrics.py    refactored to use the shared polarity module
  domain/reports/                 new — facts, selection, prompts, critic, fallback,
                                    service, queries
  integrations/llm/base.py       +response_format on CompletionRequest
  integrations/llm/openai_provider.py  +OpenAIChatProvider, +UnconfiguredLLMProvider,
                                    +build_llm_provider
  api/dependencies/llm.py        new — LLMProviderDep
  api/routes/reports.py          new
  main.py                        +llm_provider in lifespan (build_llm_provider, not a
                                    bare OpenAIChatProvider — see the bug above)
  core/config/groups.py          +ReportSettings
backend/alembic/versions/..._persona_reports_and_llm_usage.py  new migration
backend/.env.example             +ANALYTICS ceiling default, +3 REPORT_* keys
backend/tests/  (12 new files, 60 new tests)
  test_patterns_polarity.py, test_llm_usage_service.py,
  test_reports_facts.py, test_reports_selection.py, test_reports_critic.py,
  test_reports_fallback.py, test_reports_service.py, test_reports_routes.py,
  fake_llm.py
backend/evals/
  datasets/golden/persona_fidelity.jsonl   new — 5 synthetic scenarios
  harness/persona_fidelity_dataset.py, persona_fidelity_eval.py   new
  suites/persona_fidelity/test_persona_fidelity_quality.py        new
  runs/..._persona_fidelity.json           new — real run, gpt-4o-mini
final_docs/v2/configuration.md   +LLM_DAILY_TOKEN_CEILING default, +Persona reports section
final_docs/v2/evaluation-strategy.md  +Kid persona safety threshold row
final_docs/v2/decisions-log.md   +D-022, D-023, D-024; Q-4/Q-5 marked resolved
```

**Frontend**

```
frontend/src/features/reports/
  api/reports.ts, hooks/useReports.ts   new
  components/PersonaSwitcher.tsx, ReportView.tsx,
    PersonaReportPanel.tsx (+test)       new
  index.ts                               new
frontend/src/pages/GameDetailPage.tsx   +PersonaReportPanel
```

## Tests

- Backend: 526 → 587 (61 new: polarity, LLM budget, facts, selection, critic, fallback,
  service, routes), `mypy app` clean, `ruff check`/`ruff format --check` clean.
- Evaluation: `uv run pytest evals/suites/persona_fidelity` — 1 passed (grounded_rate
  recorded), 2 skipped (fact-invariance and kid-safety hard gates, per
  `evaluation-strategy.md`'s own thresholds table — both zero-tolerance metrics —
  skipped rather than asserted because the golden set is self-authored and unreviewed,
  same golden-vs-synthetic rule Phase 7's retrieval suite already established).
- Frontend: 51 → 55 (4 new), `tsc`, `oxlint`, `prettier` clean.

## Evaluation — real run against `gpt-4o-mini`

Recorded at `evals/runs/20260728T080750Z_persona_fidelity.json` (5 synthetic scenarios ×
3 personas, real completions, no fake):

| Metric | Score | Gate |
|--------|-------|------|
| `grounded_rate` | 86.7% (13/15) | Informative only |
| `fact_invariance_rate` | **100%** | Hard per `evaluation-strategy.md` — never below 1.0 in this run |
| `kid_safety_rate` | **100%** | Hard per `evaluation-strategy.md` — never below 1.0 in this run |

The two hard-gated metrics scored perfectly. The 13.3% of (scenario, persona) pairs that
fell back did so on the single most complex scenario (8 candidate facts) for
self-learner and kid — both cap-constrained personas — consistent with a small, cheap
model occasionally over-generating findings past its cap, which the critic correctly
caught both times rather than silently allowing.

## Live verification

Ran the real stack against a real, already-analyzed game and a real `gpt-4o-mini` call
(not mocked): self-learner and coach personas both produced accurate, well-grounded,
correctly-toned prose (self-learner: direct/second-person; coach: technical/third-person
"the student", lesson-plan-style recommendations) referencing the game's actual accuracy,
opening, development lag, and bad bishop findings. The kid persona, on the same game in
the same session, fell back to the deterministic summary after two ungrounded attempts —
observed directly, not simulated: concrete confirmation that the safety design behaves
correctly under real model output, not just in tests.

## Known gaps

- **No profile-level (aggregate) persona reports** — explicitly out of scope per the
  confirmed decisions above; Phase 8's dashboard remains deterministic-only.
- **Golden persona-fidelity dataset is self-authored and unreviewed** — same documented
  gap Phase 7's retrieval dataset has; the two hard-gated metrics scored 1.0 on this run
  but are not yet gating CI until a human spot-checks the scenarios.
- **`grounded_rate` is informative, not gated** — deliberate: a real, cheap model
  occasionally missing a strict finding cap and falling back is the safety net working,
  not a defect worth blocking a phase on.
- **No profile-level rate limiting on report generation** — a request can trigger a real
  LLM call per (game, persona); the daily budget ceiling is the only spend guard for now.

## Recommendation

Ready for sign-off. Both hard-gated safety/truth metrics scored perfectly on a real
run against a real model, and the one time the model's output couldn't be trusted (the
kid persona, live, not scripted), the fallback path activated exactly as designed rather
than showing anything ungrounded to a child.
