# Evaluation Strategy

Phase 0 design note. Harness built at Phase 7, extended through Phase 16.

## Principle

Evaluation that is run informally and discarded did not happen. Every run writes a record
to `eval_runs` and `evals/runs/`, carrying dataset version, model version, prompt version,
retriever version, timestamp, metric scores, and pass/fail against thresholds.

This is a hard rule from `claude.md`, and it exists because "the answers looked good" is
not a defensible basis for shipping a coaching product to a child.

## Layers

| Layer | What it checks | Determinism |
|-------|---------------|-------------|
| Chess correctness | Parsing, engine reproducibility, detector precision | Fully deterministic |
| Retrieval quality | Did the right context come back | Deterministic given a fixed corpus version |
| Answer quality | Faithfulness, relevancy, accuracy | LLM-judged, stochastic |
| Persona fidelity | Same facts, different phrasing | Mixed |
| Memory quality | Right things retained, nothing leaked | Deterministic |
| Agent behaviour | Correct tools, bounded cost, critic catches errors | Mixed |

The deterministic layers gate hard. The LLM-judged layers gate on thresholds with a
tolerance band, because judge variance is real and a single point below threshold is not
automatically a regression.

## Cadence

| Phase | Suite added | Metrics |
|-------|-------------|---------|
| 4 | Parser correctness | Parse success rate, replay consistency, failure taxonomy coverage |
| 5 | Engine determinism | Classification stability across runs, legal-line validity |
| 6 | Detector precision | Precision and recall per motif against a labelled set |
| 7 | **RAGAS retrieval** | Context Precision, Context Recall, per bucket |
| 9 | Persona fidelity | Fact-set invariance across personas, reading-level checks |
| 10 | **RAGAS answer** | Faithfulness, Response Relevancy, Response Groundedness |
| 11 | Memory quality | Retention precision, staleness, cross-profile isolation |
| 13 | Agent trajectory | Tool-choice accuracy, step counts, critic catch rate |
| 15 | Training-plan fidelity | Top-weakness invariance, kid safety, grounded rate (mirrors persona fidelity for the training-plan surface) |
| 16 | Consolidated suite + score ledger | All of the above, trended, plus fine-tuning comparison |
| 16 | Tone/persona-fidelity (LLM-as-judge) | `tone_fidelity_rate` per persona — a second, judge-scored layer on top of the structural persona-fidelity check |
| 16 | Move-classifier accuracy (D-033) | Detection F1, severity accuracy, per-class breakdown, against an independent deep-engine (depth 24) ground truth, with a demonstrated negative control |

## Thresholds

Gating values, all configurable per `configuration.md`:

| Metric | Threshold | Gating |
|--------|-----------|--------|
| Faithfulness | 0.85 | Hard once the golden set is human-reviewed. Phase 10's first real run scored 0.70 against an unreviewed set — see D-025 for why that did not stop the phase and what it likely means. |
| Answer Accuracy | 0.80 | Hard. |
| Context Precision | 0.75 | Soft; investigate and record |
| Context Recall | 0.75 | Soft |
| Illegal move rate | 0.00 | Hard. Any illegal move in a delivered answer is a failure. |
| Cross-profile leak rate | 0.00 | Hard. Non-negotiable. Verified for long-term memory specifically at Phase 11 — `cross_profile_isolated`, unconditionally hard-gated (not dataset-review-gated like the retention rates alongside it), since isolation is a code-level guarantee, not something a model's judgment could pass or fail. |
| Persona fact-set divergence | 0.00 | Hard. |
| Kid persona safety violation rate | 0.00 | Hard (added at Phase 9 implementation — not in the original plan; persona-matrix.md's kid safety rules had no scored metric until the report-generation critic gave something concrete to score). |
| Move-classifier detection F1 / severity accuracy | none set yet | Informative (Phase 16, D-033) — this phase established the metric and its negative control; a defensible pass/fail line needs more corpus than the current dev database provides. Recorded: detection F1 1.00, severity accuracy 0.75 on 24 real sampled moves. |
| Tone/persona-fidelity rate (LLM-as-judge) | none set yet | Informative (Phase 16) — a judge's own score has judge variance on top of the model being judged; not gated until there is a run history to calibrate normal variance against. Recorded: 0.92 overall. |

The three zero-tolerance metrics are zero-tolerance for different reasons: illegal moves
destroy credibility, leaks are a privacy breach, and persona divergence means the core
architectural claim of the product is false.

## Datasets

### Golden sets — authoritative
Human-reviewed. Versioned. Used for gating. Kept deliberately small so review stays real
rather than rubber-stamped.

| Set | Contents | Target size | Actual (Phase 16) |
|-----|----------|-------------|--------------------|
| `golden/retrieval` | Query → expected chunk ids, per bucket | ~80 | 41 |
| `golden/single-game-chat` | Question + game → reference answer + required facts | ~60 | 32 |
| `golden/profile-chat` | Question + profile → reference answer | ~40 | not built — no profile-level persona chat surface exists yet |
| `golden/memory-chat` | Multi-turn sessions with expected recall | ~30 | 30 |
| `golden/persona` | Analysis object → per-persona expectations | ~30 | 30 |
| `golden/training-fidelity` (Phase 15) | Recurring-weakness facts + citations → per-persona expectations | ~30 | 30 |

Every set above is still self-authored and unreviewed (`reviewed_by: null` throughout) —
grown to size in Phase 16 per the owner's explicit direction, but human review itself
was deliberately deferred (documented, not silently skipped): see this phase's own
sign-off report for the reasoning. Scores against these sets are informative; nothing
gates on them yet, exactly as the rule above states.

### Synthetic sets — coverage, not authority
Generated to cover the long tail. Always labelled synthetic. A human spot-checks a sample
before a synthetic set influences any gate.

The rule that matters: **a synthetic set never silently becomes the golden set.** They live
in separate directories, carry separate version strings, and the harness refuses to gate on
a set whose `reviewed_by` field is empty.

Generation pipeline (Phase 16): sample real analysed games → generate questions per intent
category → derive reference answers from deterministic analysis rather than from a model →
human spot-check → version and freeze.

Deriving references from deterministic analysis rather than from an LLM matters. A
reference answer generated by the same class of model being evaluated measures
self-consistency, not correctness.

## Layout

```
evals/
  datasets/
    golden/
    synthetic/
  suites/
    chess_correctness/
    retrieval/
    answer_quality/
    persona_fidelity/
    memory_quality/
    agent_trajectory/
    training_fidelity/   # Phase 15
    tone_fidelity/        # Phase 16 — LLM-as-judge, layered on persona_fidelity's output
    classifier_accuracy/  # Phase 16 — D-033, independent deep-engine ground truth
  runs/                # one scored record per run, committed
  reports/             # trend summaries (evals/harness/ledger.py writes reports/ledger.md)
  harness/             # RAGAS wiring, judges, score ledger, synthetic generator
```

## Trending and regressions

Each run is compared to the previous run on the same dataset version. A drop beyond the
tolerance band is flagged as a regression and reported in the phase sign-off, whether or
not the absolute threshold still passes. A metric sliding from 0.94 to 0.86 is a real
signal even though both clear 0.85.

## Fine-tuning (Phase 16)

Position: fine-tuning is the **last** lever, not the first.

Retrieval quality, prompt design, and grounding guardrails are cheaper, faster to iterate,
and far more auditable. A fine-tuned model that papers over a retrieval defect produces a
system that is harder to debug and no more correct.

If it proceeds, scope is **persona tone consistency only**. Never chess knowledge — chess
truth stays deterministic and engine-derived, and baking chess claims into weights would
undo the entire architectural premise.

Gate: a measurable gain on the persona fidelity and answer quality sets that prompting
demonstrably cannot reach, with the comparison recorded. If prompting gets there, no
fine-tuning happens and that is a successful outcome, not a failure.

**Outcome (Phase 16, D-034): no-go.** Prompting alone reaches 0.92-1.00 on every metric
in fine-tuning's actual scope (`tone_fidelity_rate`, `kid_safety_rate`,
`fact_invariance_rate`/`top_weakness_invariance_rate`) — no ceiling it is visibly
hitting. The metrics with real headroom (`single_game_chat` faithfulness 0.71,
`agent_trajectory` faithfulness 0.52-0.59) are grounding/retrieval quality, explicitly
out of scope for a persona-tone-only fine-tune. See D-034 for the full evidence table.

## Reporting

Every phase sign-off from Phase 7 onward includes: suites run, dataset versions, scores
against thresholds, deltas from the previous run, regressions flagged, and known
limitations. If a hard threshold fails, the phase report says so plainly and the phase does
not close.
