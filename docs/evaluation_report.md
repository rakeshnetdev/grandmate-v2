# Evaluation Report — GrandMate v2

> **Generated from recorded runs by `backend/evals/report.py`.** No figure in this report is hand-written. Regenerate with `cd backend && uv run python -m evals.report` after any evaluation run.

Generated: 2026-08-03 09:23 PDT

Eight evaluation suites, each with a versioned dataset and a recorded run under `backend/evals/runs/`. Dataset design and provenance are documented in [`evaluation_data_design.md`](evaluation_data_design.md); thresholds and gating rules in [`../final_docs/v2/evaluation-strategy.md`](../final_docs/v2/evaluation-strategy.md).

## The rule that makes these numbers falsifiable

**Ground truth never comes from the code being graded**, and a metric that could not be measured is reported as *not measured* — never silently defaulted to a passing score. The move classifier is scored against an independent, deeper engine run; retrieval queries have a known correct chunk by construction; and the classifier harness carries a negative control that deliberately corrupts the thresholds to prove the test can fail.

## Summary

| Suite | Run recorded | Golden set reviewed |
|---|---|---|
| Move classifier accuracy | `20260729T092854Z_classifier_accuracy.json` | n/a |
| Retrieval quality | `20260729T153610Z_retrieval.json` | ⚠️ 0 / 41 |
| Single-game chat quality | `20260729T152857Z_single_game_chat.json` | ⚠️ 0 / 32 |
| Persona fidelity | `20260729T151313Z_persona_fidelity.json` | ⚠️ 0 / 30 |
| Persona tone fidelity | `20260729T074141Z_tone_fidelity.json` | ⚠️ 0 / 10 |
| Training plan fidelity | `20260729T151922Z_training_fidelity.json` | ⚠️ 0 / 30 |
| Long-term memory quality | `20260729T152936Z_memory_quality.json` | ⚠️ 0 / 30 |
| Single-agent vs multi-agent trajectory | `20260803T162112Z_agent_trajectory.json` | ⚠️ 0 / 12 |

Every golden set in this project is currently **self-authored and unreviewed**. Per `evaluation-strategy.md`'s golden-vs-synthetic rule, that makes these scores informative rather than gating, except where a metric is structural — guaranteed by the code rather than estimated by a judge. Those are marked *Hard, structural* below.

---

## Move classifier accuracy

Does the deterministic core get the chess right? Every layer above Phase 5 treats the five-way move classification as ground truth, so this is the measurement the rest of the system rests on.

Ground truth: an **independent Stockfish run at depth 24**, against a production classifier that runs at depth 12 with its own thresholds. The oracle never sees the classifier's output.

Sample size: 24 positions (24 scored).

| Metric | Score | Negative control |
|---|---|---|
| Detection F1 | 1.000 | 0.500 |
| Detection precision | 1.000 | — |
| Detection recall | 1.000 | — |
| Severity accuracy | 0.750 | 0.125 |

**The negative control is the load-bearing column.** It is the same harness run against deliberately corrupted classifier thresholds. A test that cannot fail proves nothing, so the collapse from 1.000 to 0.500 on detection — and 0.750 to 0.125 on severity — matters more than the passing score itself.

**Per class** — accuracy is not uniform, and an aggregate number hides that:

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| `best` | 0.667 | 1.000 | 0.800 | 4 |
| `good` | 1.000 | 0.667 | 0.800 | 6 |
| `inaccuracy` | 0.400 | 1.000 | 0.571 | 2 |
| `mistake` | 1.000 | 0.556 | 0.714 | 9 |
| `blunder` | 0.750 | 1.000 | 0.857 | 3 |

<sub>Source: `backend/evals/runs/20260729T092854Z_classifier_accuracy.json` · run at 2026-07-29T09:28:54.107634+00:00</sub>

---

## Retrieval quality

Dense vs sparse vs hybrid (reciprocal rank fusion), scored with RAGAS's non-LLM context precision and recall against a corpus-derived query set.

**Dataset** `v1-2026-07-27` · **retriever** `phase-7-v1` · **embeddings** `text-embedding-3-small`

**Golden-set status**: ⚠️ **unreviewed** — 0 of 41 human-reviewed, so scores are informative, not gating

| Strategy | Context precision | Context recall | MRR | Negative FP rate |
|---|---|---|---|---|
| Dense | 0.907 | 0.951 | 0.914 | 100.0% |
| Sparse | 0.927 | 0.983 | 0.921 | 100.0% |
| Hybrid | 0.936 | 0.977 | 0.949 | 100.0% |

**MRR by query type** — reported separately, because a query set of exact names would structurally favour sparse retrieval:

| Strategy | Lexical | Semantic |
|---|---|---|
| Dense | 1.000 | 0.837 |
| Sparse | 0.931 | 0.912 |
| Hybrid | 1.000 | 0.904 |

Soft thresholds: context precision ≥ 0.75, context recall ≥ 0.75.

**Hybrid does not beat both baselines** on context precision/recall at this corpus size — sparse alone matches or exceeds it. Recorded as the honest outcome rather than smoothed over; note that hybrid still has the best MRR, which asks a narrower question (how far down the list is the *first* relevant hit).

Recommendation on record: *ship the simpler retriever (see rag-architecture.md section 3)*

<sub>Source: `backend/evals/runs/20260729T153610Z_retrieval.json` · run at 2026-07-29T15:36:10.755487+00:00</sub>

---

## Single-game chat quality

Real chat-graph turns — real tool dispatch, real grounding guardrail — scored by real RAGAS judge calls.

**Model** `gpt-4o-mini` · **harness** `phase-10-v1` · 32 scenarios, real graph turns and real judge calls

**Golden-set status**: ⚠️ **unreviewed** — 0 of 32 human-reviewed, so scores are informative, not gating

| Metric | Score | Gate |
|---|---|---|
| `grounded_rate` | 100.0% | Hard, structural |
| `intent_valid_rate` | 100.0% | Hard, structural |
| `faithfulness` | 0.713 | ⚠️ soft, target 0.85 |
| `response_relevancy` | 0.634 | Informative |

`grounded_rate` and `intent_valid_rate` are properties the code guarantees — the retry-then-fallback loop and the classifier's taxonomy fallback make any other value structurally impossible. They are not judge estimates.

⚠️ **Faithfulness is below its 0.85 target.** It does not gate, per the golden-vs-synthetic rule — the dataset is self-authored and unreviewed. Reading the answers manually found no fabricated game-specific claim; RAGAS scores *every* sentence, including legitimate uncited coaching advice that was never meant to carry a citation. Either the threshold needs recalibrating for a system that intentionally gives advice, or the output contract needs an explicit advice-vs-fact split.

<sub>Source: `backend/evals/runs/20260729T152857Z_single_game_chat.json` · run at 2026-07-29T15:28:57.072880+00:00</sub>

---

## Persona fidelity

Does the same analysis render for three audiences without the facts changing?

**Model** `gpt-4o-mini` · 30 scenarios × 3 personas, real completions

**Golden-set status**: ⚠️ **unreviewed** — 0 of 30 human-reviewed, so scores are informative, not gating

| Metric | Score | Gate |
|---|---|---|
| `fact_invariance_rate` | 94.4% | ⚠️ Hard — never below 1.0 |
| `kid_safety_rate` | 100.0% | ✅ Hard — never below 1.0 |
| `grounded_rate` | 73.3% | Informative |

`fact_invariance_rate` is the measurement behind the product's central claim: the same analysis facts appear across every persona rendering of the same game. Personas change language, depth, and framing — never chess truth.

A `grounded_rate` below 100% is the safety net working, not a defect: a small model over-generating past a strict persona finding cap, caught by the critic and replaced with the deterministic report.

<sub>Source: `backend/evals/runs/20260729T151313Z_persona_fidelity.json` · run at 2026-07-29T15:13:13.410819+00:00</sub>

---

## Persona tone fidelity

Does an answer sound like the persona it claims to be? Separate from whether its facts are correct.

**Model** `gpt-4o-mini` · 30 generated, 25 judged

**Golden-set status**: ⚠️ **unreviewed** — 0 of 10 human-reviewed, so scores are informative, not gating

| Persona | Tone fidelity |
|---|---|
| `self_learner` | 88.9% |
| `coach` | 100.0% |
| `kid` | 83.3% |
| **overall** | **92.0%** |

Tone fidelity asks whether an answer *sounds* like the persona it claims to be — a separate question from whether its facts are right, which `fact_invariance_rate` already answers. A gap between generated and judged counts means some outputs could not be scored and were reported as unscored rather than counted as passes.

<sub>Source: `backend/evals/runs/20260729T074141Z_tone_fidelity.json` · run at 2026-07-29T07:41:41.218002+00:00</sub>

---

## Training plan fidelity

Do generated training plans address the weakness the deterministic analytics actually identified?

**Model** `gpt-4o-mini` · 30 scenarios

**Golden-set status**: ⚠️ **unreviewed** — 0 of 30 human-reviewed, so scores are informative, not gating

| Metric | Score | Gate |
|---|---|---|
| `top_weakness_invariance_rate` | 98.9% | ⚠️ Hard |
| `kid_safety_rate` | 100.0% | ✅ Hard |
| `grounded_rate` | 100.0% | Informative |

Training plans are recommendations, so the invariant that matters is that the *weakness being addressed* is the one the deterministic analytics identified — not that the prose is identical across personas.

<sub>Source: `backend/evals/runs/20260729T151922Z_training_fidelity.json` · run at 2026-07-29T15:19:22.914063+00:00</sub>

---

## Long-term memory quality

Is a durable statement retained, a non-durable one ignored, a superseded one resolved, and one profile's memory invisible to another?

**Model** `gpt-4o-mini` · 30 scenarios, real extraction calls plus a real-Postgres structural check

**Golden-set status**: ⚠️ **unreviewed** — 0 of 30 human-reviewed, so scores are informative, not gating

| Metric | Score | Gate |
|---|---|---|
| `retention_true_positive_rate` | 84.2% | Soft until reviewed |
| `retention_true_negative_rate` | 100.0% | Soft until reviewed |
| `staleness_resolved` | **yes** | ✅ Hard, structural |
| `cross_profile_isolated` | **yes** | ✅ Hard, structural |

The two hard metrics are verified against real Postgres, not a fake. The retention set includes an adversarial case: the assistant says *"I will remember that you want to focus on defense"* and the user replies only *"ok"* — nothing should be written, because the durable statement was never the user's.

<sub>Source: `backend/evals/runs/20260729T152936Z_memory_quality.json` · run at 2026-07-29T15:29:36.367809+00:00</sub>

---

## Single-agent vs multi-agent trajectory

The head-to-head comparison Phase 13 was scoped to decide on evidence.

**Model** `gpt-4o-mini` · 12 scenarios, both graphs run against the same seeded games and scored identically

**Dataset status**: ⚠️ **unreviewed** — 0 of 12 human-reviewed, so scores are informative, not gating (synthetic — marked as such in the dataset version)

| Metric | Single agent | Multi-agent |
|---|---|---|
| `faithfulness` | 0.621 | 0.622 |
| `response_relevancy` | 0.657 | 0.526 |
| `grounded_rate` | 100.0% | 100.0% |
| avg tool calls / turn | 1.17 | 1.42 |

Supervisor `routing_accuracy`: 91.7%

**Exit criterion**: multi-agent must match or beat single-agent on both faithfulness and response_relevancy to be adopted; otherwise the Phase 10 baseline stays (rag-architecture.md §7)

**Multi-agent wins**: no — so the Phase 10 single-agent baseline stays in production and the supervisor graph remains built, tested, and unrouted. A negative result recorded rather than buried is the point of running the comparison at all.

⚠️ Marked **directional only** — the sample is too small for these differences to be statistically meaningful. It is enough to say multi-agent did not clear the bar; it is not enough to quantify by how much.

<sub>Source: `backend/evals/runs/20260803T162112Z_agent_trajectory.json` · run at 2026-08-03T16:21:12.719058+00:00</sub>

---

## Reproducing these numbers

```bash
cd backend

# Hermetic suite — no API key, no corpus needed
uv run pytest -q

# Evaluation suites — need OPENAI_API_KEY and an ingested corpus
uv run python -m scripts.ingest_corpus
uv run pytest -q evals/

# Regenerate this report from whatever runs are recorded
uv run python -m evals.report
```

Deterministic metrics (retrieval hit rate and MRR, classifier F1, the structural guarantees) reproduce exactly for a fixed dataset. Judge-scored metrics (faithfulness, response relevancy, tone fidelity) will vary run to run, and engine-derived figures carry the small non-determinism noted in the Phase 5 report. Read the judged numbers as approximate; read the structural ones as exact.
