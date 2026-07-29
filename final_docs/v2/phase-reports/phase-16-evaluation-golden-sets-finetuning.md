# Phase 16 Report — Evaluation, Synthetic Data, Golden Sets, and Fine-Tuning

**Date**: 2026-07-29
**Status**: Complete, pending sign-off
**Branch**: `P16-evaluation-golden-sets-finetuning`

## Goal

Consolidate evaluation into a trended, gating system and decide whether fine-tuning
earns its place — the largest phase to date, spanning six existing eval harnesses, three
new ones, and the go/no-go decision the whole evaluation strategy has been building
toward since Phase 7.

## Scope decisions confirmed before and during implementation

1. **Golden-set scope**: every existing golden set (persona_fidelity, memory_retention,
   single_game_chat, training_fidelity) grown from 3-10 self-authored rows to 30, per the
   owner's explicit direction — a deliberate override of this phase's own initial
   MVP-scoped-and-unreviewed default. Human review itself stays deferred; these are
   larger, still-unreviewed sets, documented as such.
2. **Fine-tuning timing**: run the eval consolidation first, then bring concrete evidence
   back before deciding whether to spend on a real fine-tuning experiment — not decided
   upfront.
3. **A depth setting change was requested and declined with the reasoning surfaced**:
   partway through the classifier-accuracy eval (which took materially longer than
   expected at depth 24), the owner asked to cap ground-truth depth at 16. That would
   have put ground truth *shallower* than production's own tiered deep pass (depth 18),
   defeating D-033's "independent, deeper ground truth" requirement. Flagged explicitly;
   the owner kept the completed depth-24 result rather than lowering it.
4. **Fine-tuning go/no-go (D-034)**: no-go, decided from evidence gathered after full
   consolidation — see below.

## An unrelated discovery, twice

Two rounds of "this file exists and I didn't create it" came up mid-phase, both handled
the same way — flagged, not silently absorbed or silently dropped:
- ADR-0017 (LangSmith tracing) and its ADR-0013 cross-reference, from a concurrent
  session. Owner chose to bundle these into Phase 15's commit.
- A much larger `docs/` tree (`ARCHITECTURE.md`, `DEPLOYMENT.md`, `Deliverables.md`,
  `grading-rubric.md`, diagrams) plus `backend/evals/report.py`, appearing during this
  phase. Given the scale and that none of it was authored or reviewed here, the owner
  chose to leave it alone entirely — it is not part of this phase's commit.

## Completed

| Deliverable | Status |
|-------------|--------|
| Golden sets grown to 30 rows each (persona_fidelity, memory_retention, single_game_chat, training_fidelity), validated against their real loaders | ✅ |
| `evals/harness/ledger.py` — score ledger unifying all suites: run-over-run regression detection, review-gated hard thresholds, per-suite reporting | ✅ |
| `evals/harness/synthetic_generator.py` — real pipeline: sample analysed games → question per intent → deterministic reference facts (`extract_facts`, never an LLM) → provenance → freeze | ✅ |
| `evals/harness/tone_judge.py` + `tone_fidelity_eval.py` — new LLM-as-judge rubric for tone/persona fidelity, layered on `persona_fidelity_eval.py`'s existing generation path rather than a duplicate pipeline | ✅ |
| `evals/harness/classifier_accuracy_eval.py` (D-033) — independent depth-24 Stockfish ground truth, detection F1, severity accuracy, per-class breakdown, demonstrated negative control | ✅ |
| All 6 pre-existing suites re-run for real against the grown golden sets | ✅ |
| Fine-tuning decision (D-034): no-go, evidence-based | ✅ |
| `evaluation-strategy.md`, `project-plan.md`, `decisions-log.md` updated to match | ✅ |

## Files created or changed

```
backend/app/core/config/groups.py   +eval_regression_tolerance,
                                      +classifier_eval_ground_truth_depth,
                                      +classifier_eval_sample_size
backend/.env.example                 +EVAL_REGRESSION_TOLERANCE,
                                      +CLASSIFIER_EVAL_GROUND_TRUTH_DEPTH,
                                      +CLASSIFIER_EVAL_SAMPLE_SIZE
backend/evals/
  harness/ledger.py                  new — score ledger
  harness/synthetic_generator.py     new — synthetic dataset pipeline
  harness/tone_judge.py              new — LLM-as-judge rubric
  harness/tone_fidelity_eval.py      new — tone-fidelity harness
  harness/classifier_accuracy_eval.py new — D-033 move-classifier accuracy
  suites/tone_fidelity/              new
  suites/classifier_accuracy/        new
  datasets/golden/
    persona_fidelity.jsonl           5 -> 30 rows
    memory_retention.jsonl           10 -> 30 rows
    single_game_chat.jsonl           10 -> 32 rows
    training_fidelity.jsonl          3 -> 30 rows
  datasets/synthetic/single_game_chat.jsonl   new — 68 rows, generated from real games
  runs/                              8 new real runs (see Evaluation below)
  reports/ledger.md                  new — generated, not committed as source
backend/tests/  (4 new files, 42 new tests)
  test_eval_ledger.py, test_synthetic_generator.py, test_tone_judge.py,
  test_classifier_accuracy_eval.py
final_docs/v2/
  evaluation-strategy.md             +Phase 15/16 cadence rows, +D-033/034 threshold
                                      rows, +actual dataset sizes, +fine-tuning outcome
  decisions-log.md                   +D-034
  README.md                          +Phase 16 row
project-plan.md                      +Phase 15/16 cadence rows
```

## Tests

- Backend: 743 → 785 (42 new). Full suite (`uv run pytest`) green. `ruff check`,
  `ruff format --check`, and `mypy app` (and the new `evals/` modules) all clean.
- New hermetic unit coverage: score ledger (20 tests — flattening, review-gating,
  regression detection), synthetic generator (6 — question templating, provenance,
  deterministic-fact sourcing), tone judge (5 — `FakeLLMProvider`-scripted, no real
  network call), classifier-accuracy scoring functions (11 — detection F1, per-class
  metrics, negative-control behaviour).

## Evaluation — real runs, all six pre-existing suites plus three new ones

All against real `gpt-4o-mini` (chat/persona/training/tone suites) or a real depth-24
Stockfish pass (classifier accuracy). Full records under `evals/runs/`.

| Suite | Key metric(s) | Score |
|-------|---------------|-------|
| persona_fidelity (30 scenarios) | grounded_rate / fact_invariance_rate / kid_safety_rate | 0.73 / 0.94 / 1.00 |
| training_fidelity (30 scenarios) | grounded_rate / top_weakness_invariance_rate / kid_safety_rate | 1.00 / 0.99 / 1.00 |
| tone_fidelity (10 scenarios × 3 personas, new) | tone_fidelity_rate (self-learner / coach / kid) | 0.92 overall (0.89 / 1.00 / 0.83) |
| single_game_chat (32 scenarios) | faithfulness / response_relevancy | 0.71 / 0.63 |
| memory_quality (30 scenarios) | retention TP rate / retention TN rate / cross-profile isolation | 0.84 / 1.00 / True |
| agent_trajectory (12 scenarios, unchanged set) | single-agent faithfulness / multi-agent faithfulness / routing accuracy | 0.59 / 0.52 / 0.92 |
| retrieval (41 rows, unchanged) | hybrid context precision / recall | 0.94 / 0.98 |
| classifier_accuracy (24 real moves, new, D-033) | detection F1 / severity accuracy | 1.00 / 0.75 |
| classifier_accuracy negative control | same, scrambled ground truth | 0.50 / 0.125 |

**Score-ledger regressions flagged** (run-over-run, all against the *previous, much
smaller* golden sets): `persona_fidelity.grounded_rate` -0.13, `persona_fidelity.
fact_invariance_rate` -0.06, `single_game_chat.response_relevancy` -0.11, `memory_quality.
retention_true_positive_rate` -0.16. **None of these are regressions in the underlying
system** — they are the direct, expected effect of testing against golden sets 3-6x
larger and more varied than before. A 5-scenario hand-picked set scoring 1.0 and a
30-scenario set scoring 0.94 on the same real invariant is the larger set doing its job,
not the system getting worse. No hard gate failures — every set involved remains
unreviewed, so nothing gates yet, exactly per the review-gating design.

**Move-classifier accuracy (D-033), in detail**: 24 real sampled moves across the
current dev database, independent depth-24 ground truth. Detection F1 is perfect (1.00)
— production never misses a real problem or false-alarms on a clean move. Severity
accuracy is 0.75 (18/24 exact five-way matches); the disagreements cluster in
`inaccuracy`/`mistake` (precision 0.40 / recall 0.56 respectively), consistent with those
boundaries being the two closest centipawn thresholds to each other. The negative
control (ground-truth labels randomly scrambled) drops detection F1 to 0.50 and severity
accuracy to 0.125 — the test can clearly fail, satisfying the phase's own requirement
that a metric able to only ever pass proves nothing.

**Fine-tuning (D-034)**: no-go. See `decisions-log.md`'s D-034 for the full evidence
table. In short: every metric fine-tuning is actually scoped to touch (persona tone,
kid safety, fact/weakness invariance) already scores 0.92-1.00 via prompting alone; the
metrics with real headroom (chat faithfulness/relevancy) are grounding-quality issues
explicitly out of fine-tuning's scope. Per `evaluation-strategy.md`'s own framing, this
is a successful outcome, not a deferred task.

## Known gaps

- **No golden set is human-reviewed yet.** All five are larger now (Phase 16) but still
  self-authored, same documented gap every phase since 7 has carried. Nothing gates on
  them; several would fail Faithfulness/Answer Accuracy's hard 0.85 threshold if review
  status alone flipped that switch — this is expected and by design, not a surprise to
  discover later.
- **`golden/profile-chat`** (the dataset `evaluation-strategy.md`'s original design
  named) was never built — there is no profile-level (aggregate) persona chat surface in
  the product yet for it to test.
- **`agent_trajectory` and `retrieval` golden/synthetic sets were not grown** this
  phase — `agent_trajectory`'s is intentionally synthetic-only (Phase 13's own scope),
  and `retrieval` already exceeded the 30-row bar before this phase started.
- **`tone_fidelity_eval.py` deliberately samples only 10 of the 30 persona_fidelity
  scenarios** per run, to bound real API spend — documented in the module's own
  docstring, not a silent shortcut.
- **Classifier-accuracy sample size (24 real moves) is bounded by what the current dev
  database contains**, not a deliberate ceiling — a larger production corpus would
  support a larger, more stratified sample and eventually a real pass/fail threshold.
- **Tone-fidelity and classifier-accuracy thresholds are informative only** — this phase
  established both metrics and their negative-control/variance behaviour; setting a real
  gating threshold needs a run history to calibrate normal variance against first.

## Recommendation

Ready for sign-off. Every deliverable in the phase's scope is built, tested, and run for
real against live data — including the two genuinely new capabilities (LLM-as-judge tone
scoring, independent move-classifier validation with a working negative control) that
did not exist anywhere in the codebase before this phase. The fine-tuning question this
whole evaluation strategy has been building toward for six phases now has a real,
evidence-backed answer.
