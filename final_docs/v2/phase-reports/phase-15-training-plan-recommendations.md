# Phase 15 Report — Training Plan and Coaching Recommendations

**Date**: 2026-07-29
**Status**: Complete, pending sign-off
**Branch**: `P15-training-plan-recommendations`

## Goal

Convert Phase 8's deterministic recurring-weakness detection into an actionable,
persona-framed, citation-grounded training plan — a new report type on Phase 9's
existing report infrastructure, not a new chat tool or a second surface.

## Scope decisions confirmed before implementation (D-032)

Four open policy questions resolved with the owner, all recommended defaults accepted:

1. **Grounding: hybrid.** `ProfileAnalyticsService`'s recurring-weakness detection
   (Phase 8, deterministic) decides *what* to recommend; `hybrid_search` over the
   tactics/strategy corpus (Phase 7) supplies real, citable study content; the LLM
   phrases it per persona. No ungrounded LLM-generated study advice.
2. **Cadence: on-demand only**, no scheduler — "this week's focus" is framing, not a
   literal recurring job.
3. **Outcome tracking: history only** — what was recommended and when, so a plan
   deprioritises (never hard-excludes) a weakness it already surfaced recently.
   Automated before/after improvement detection was rejected as a real causal-inference
   problem out of proportion for this phase.
4. **Delivery: a new report type**, reusing Phase 9's report generation/critic/persona
   infrastructure rather than a new chat tool.

Two further scope questions came up mid-phase and were also confirmed with the owner
rather than decided silently:

- **Live-model evaluation**: Phase 15 isn't listed in `project-plan.md`'s
  evaluation-cadence table as adding a new suite, but this phase does add new LLM
  behaviour (`training_prompts.py`). Owner chose to build and run one — see below.
- **Frontend scope**: Phase 9's report feature shipped a full frontend as part of that
  same phase. Owner chose to do the same here rather than defer it.

## Completed

| Deliverable | Status |
|-------------|--------|
| `TrainingRecommendation` — profile-scoped, versioned storage (new row per generation, never overwritten) | ✅ |
| `domain/reports/training_facts.py` — turns `WeaknessStats` + retrieved chunks into the shared `Fact` vocabulary | ✅ |
| `domain/reports/training_selection.py` — persona ranking/capping, recently-recommended deprioritisation (never a hard exclusion) | ✅ |
| `domain/reports/training_prompts.py` — persona system prompts + the same strict JSON output contract reports use | ✅ |
| `domain/reports/training_fallback.py` — deterministic, LLM-free plan builder | ✅ |
| `domain/reports/training_service.py` — snapshot → retrieval → facts → selection → LLM → critic → retry → fallback → persist | ✅ |
| `domain/reports/queries.py::get_recently_recommended_themes` — reads the profile's own most recent prior plan | ✅ |
| `GET /api/v1/reports/profile/training?persona=&window=` — profile-scoped (`ScopedProfileIdDep`), always generates fresh (no cache branch, per D-032) | ✅ |
| Reused `critic.py::validate_report` as-is — no training-specific grounding logic needed | ✅ |
| `report_training_chunks_per_weakness` config (rule 11: no hardcoded tunables) | ✅ |
| Alembic migration, verified clean against a live Postgres (`alembic check`) | ✅ |
| Frontend: `features/training/` (api, hook, panel, view), wired into `ProfileDashboard` | ✅ |
| Live training-plan fidelity evaluation harness — run for real against `gpt-4o-mini` | ✅ |
| Verified live end to end in a real browser against the real stack and a real LLM call | ✅ |

## A design decision made during implementation, not pre-specified

`training_service.py` skips the LLM entirely when a profile has no recurring weakness
yet, going straight to the fallback's "not enough signal yet" message. `ReportService`
always attempts at least one LLM call even for a sparse game; a training plan can
legitimately have an empty `FACTS` list (a profile with too few games or no recurring
pattern), and calling the model with nothing to ground would spend budget and a retry on
a call with no possible good answer. `test_training_service.py`'s
`test_no_recurring_weakness_yields_an_empty_plan` covers this — the fake LLM is given
zero scripted responses and the test would fail loudly (an `AssertionError` from
`FakeLLMProvider`) if the service ever tried to call it in that state.

## A second design decision: no second window selector

The frontend originally gave the training-plan panel its own window selector, mirroring
`ProfileDashboard`'s. Running the full frontend suite live-caught this as a real
usability defect before it shipped: `ProfileDashboard.test.tsx`'s existing
`Last 30` button lookup started matching two elements once both selectors rendered on
the same page — the same ambiguity a real user would hit. Fixed by making `windowSize`
a prop `TrainingPlanPanel` receives from the dashboard it's embedded in rather than a
second independent control: a plan is built from the same windowed analytics snapshot
already on screen, so a second control would have been redundant, not a real second
choice.

## Files created or changed

**Backend**

```
backend/app/
  db/models/training.py           new — TrainingRecommendation
  db/models/__init__.py           +TrainingRecommendation export
  domain/reports/
    facts.py                      +recurring_weakness, +knowledge_chunk FactKinds
    training_facts.py             new
    training_selection.py         new
    training_prompts.py           new
    training_fallback.py          new
    training_service.py           new
    queries.py                    +get_recently_recommended_themes
    __init__.py                   +TrainingService export
  api/routes/reports.py           +GET /reports/profile/training
  schemas/reports.py              +TrainingRecommendationSummary
  core/config/groups.py           +ReportSettings.report_training_chunks_per_weakness
backend/alembic/versions/..._training_recommendations.py   new migration
backend/.env.example             +REPORT_TRAINING_CHUNKS_PER_WEAKNESS
backend/tests/  (5 new files, 30 new tests)
  test_training_facts.py, test_training_selection.py, test_training_fallback.py,
  test_training_service.py, test_training_routes.py
backend/evals/
  datasets/golden/training_fidelity.jsonl        new — 3 synthetic scenarios
  harness/training_fidelity_dataset.py, training_fidelity_eval.py   new
  suites/training_fidelity/test_training_fidelity_quality.py        new
  runs/20260729T063820Z_training_fidelity.json    new — real run, gpt-4o-mini
```

**Frontend**

```
frontend/src/features/training/
  api/training.ts                new
  hooks/useTraining.ts           new — useMutation, deliberately not an auto-firing query
  components/TrainingPlanView.tsx, TrainingPlanPanel.tsx (+test)   new
  index.ts                       new
frontend/src/features/analytics/components/ProfileDashboard.tsx   +TrainingPlanPanel section
```

## Tests

- Backend: 713 → 743 (30 new: facts, selection, fallback, service, routes). Full suite
  (`uv run pytest`), `ruff check`/`ruff format --check`, and `mypy app` all clean.
- Frontend: 68 → 72 (4 new: `TrainingPlanPanel.test.tsx`). `tsc -b --noEmit`, `oxlint`,
  `prettier --check` all clean. (Two unrelated test files timed out once under system
  load during a full-suite run and passed cleanly on immediate re-run in isolation and
  on a second full run — flakiness from resource contention, not a regression; not
  specific to this phase's files.)

## Evaluation — real run against `gpt-4o-mini`

Not in `project-plan.md`'s evaluation-cadence table (that table doesn't add a new suite
between Phase 13 and the Phase 16 consolidation), but this phase adds new LLM behaviour
of its own, so — per the owner's choice above — it gets its own small golden set and
live-model run rather than relying on Phase 9's persona-fidelity scores for a different
prompt/output surface. Structurally this is `persona_fidelity_eval.py` applied to
training plans: 3 synthetic scenarios (no citation, one citation, five weaknesses to
exercise persona capping) × 3 personas, real completions, no fake. Recorded at
`evals/runs/20260729T063820Z_training_fidelity.json`:

| Metric | Score | Gate |
|--------|-------|------|
| `grounded_rate` | 100% (9/9) | Informative only |
| `top_weakness_invariance_rate` | **100%** | Hard per this suite's own thresholds — never below 1.0 in this run |
| `kid_safety_rate` | **100%** | Hard per this suite's own thresholds — never below 1.0 in this run |

All three (scenario × persona) generations were grounded on the first attempt — no
retries or fallbacks needed on this run.

## Live verification

Ran the real stack — real Postgres, real `gpt-4o-mini`, a real browser (Chromium via
Playwright, `chromium-cli` unavailable in this environment) — against a real logged-in
profile (Lichess username `DrNykterstein`, MVP-trust login per ADR-0014) seeded with 3
games sharing a recurring opponent-fork motif, on top of that profile's existing game
history:

- **Self-learner**: generated a full plan naming forks, discovered attacks, pins, weak
  king safety, and skewers by name, with per-weakness findings and concrete
  recommendations, `source: "AI-generated"`.
- **Switched to Kid and regenerated**: a materially different plan for the *same*
  underlying weaknesses — one focused finding on the single most important pattern
  (pins/king safety), plain language, no centipawn numbers, "This week's focus" instead
  of a longer recommendation list — the same persona invariant `persona-matrix.md`
  states, observed live rather than only in the eval harness.
- Network trace confirmed `GET /api/v1/reports/profile/training?persona=kid&window=10`
  returned `200`; the only `401` observed was the expected pre-login `/auth/me` check,
  unrelated to this feature.
- Screenshots captured of both persona states, showing the training-plan panel
  integrated into the existing analytics dashboard.

## Known gaps

- **Golden training-fidelity dataset is self-authored and unreviewed** — same documented
  gap Phase 7's retrieval dataset and Phase 9's persona-fidelity dataset both have; the
  two hard-gated metrics scored 1.0 on this run but are not yet gating CI until a human
  spot-checks the 3 scenarios (`reviewed_by` stays `null` until then).
- **`grounded_rate` is informative, not gated** — same deliberate reasoning Phase 9's
  report documents: a real, cheap model occasionally missing a strict cap and falling
  back is the safety net working, not a defect worth blocking on.
- **No per-profile rate limiting on plan generation** — like Phase 9's game reports, the
  daily LLM token ceiling is the only spend guard; every `GET` on this endpoint is a real
  generation by design (D-032), so this is more load-bearing here than for game reports.
- **Demo data**: the live-verification profile (`DrNykterstein`) now has 3 extra seeded
  games with a synthetic fork-motif finding, added directly via a one-off script to
  produce a real recurring weakness to demonstrate against. Left in place pending the
  owner's preference — easy to identify and remove (`raw_pgn_path = 'pgn/demo.pgn'`) if
  unwanted.
- **Local dev servers left running** for continued exploration: backend on `:7575`
  (already running before this session resumed), frontend on `:3535`.

## Recommendation

Ready for sign-off. Backend and frontend both complete and tested, the two safety/truth
metrics this feature promises scored perfectly on a real model run, and the same
invariant was independently confirmed live in a browser — the kid persona rendered a
materially different, safe, single-focus version of the same underlying facts the
self-learner persona saw in full.
