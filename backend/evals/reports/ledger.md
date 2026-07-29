# Evaluation Score Ledger

Generated: 2026-07-29T08:39:20.145797

## Latest score per suite

### agent_trajectory
Run: `20260729T153535Z_agent_trajectory.json` (2026-07-29T15:35:35.542757+00:00)

| Metric | Value |
|--------|-------|
| multi_agent.avg_tool_call_count | 1.0833333333333333 |
| multi_agent.faithfulness | 0.5236111111111111 |
| multi_agent.grounded_rate | 1.0 |
| multi_agent.response_relevancy | 0.15242167691925684 |
| routing_accuracy | 0.9166666666666666 |
| single_agent.avg_tool_call_count | 1.4166666666666667 |
| single_agent.faithfulness | 0.5948412698412698 |
| single_agent.grounded_rate | 1.0 |
| single_agent.response_relevancy | 0.42398536655146035 |

### classifier_accuracy
Run: `20260729T092854Z_classifier_accuracy.json` (2026-07-29T09:28:54.107634+00:00)

| Metric | Value |
|--------|-------|
| detection_f1 | 1.0 |
| detection_precision | 1.0 |
| detection_recall | 1.0 |
| n_scored | 24.0 |
| negative_control_detection_f1 | 0.5 |
| negative_control_severity_accuracy | 0.125 |
| severity_accuracy | 0.75 |

### memory_quality
Run: `20260729T152936Z_memory_quality.json` (2026-07-29T15:29:36.367809+00:00)

| Metric | Value |
|--------|-------|
| cross_profile_isolated | True |
| retention_true_negative_rate | 1.0 |
| retention_true_positive_rate | 0.8421052631578947 |
| staleness_resolved | True |

### persona_fidelity
Run: `20260729T151313Z_persona_fidelity.json` (2026-07-29T15:13:13.410819+00:00)

| Metric | Value |
|--------|-------|
| fact_invariance_rate | 0.9444444444444444 |
| grounded_rate | 0.7333333333333333 |
| kid_safety_rate | 1.0 |
| n_scenarios | 30.0 |

### retrieval
Run: `20260729T153610Z_retrieval.json` (2026-07-29T15:36:10.755487+00:00)

| Metric | Value |
|--------|-------|
| dense.context_precision | 0.9068617723995137 |
| dense.context_recall | 0.9507936507936507 |
| dense.hit_rate_by_qtype.lexical | 1.0 |
| dense.hit_rate_by_qtype.semantic | 0.9473684210526315 |
| dense.mrr | 0.9138888888888889 |
| dense.mrr_by_qtype.lexical | 1.0 |
| dense.mrr_by_qtype.semantic | 0.8368421052631579 |
| dense.n_scored | 36.0 |
| dense.negative_false_positive_rate | 1.0 |
| hybrid.context_precision | 0.9358355378282864 |
| hybrid.context_recall | 0.976984126984127 |
| hybrid.hit_rate_by_qtype.lexical | 1.0 |
| hybrid.hit_rate_by_qtype.semantic | 1.0 |
| hybrid.mrr | 0.949074074074074 |
| hybrid.mrr_by_qtype.lexical | 1.0 |
| hybrid.mrr_by_qtype.semantic | 0.9035087719298246 |
| hybrid.n_scored | 36.0 |
| hybrid.negative_false_positive_rate | 1.0 |
| sparse.context_precision | 0.927166005200465 |
| sparse.context_recall | 0.9825396825396826 |
| sparse.hit_rate_by_qtype.lexical | 1.0 |
| sparse.hit_rate_by_qtype.semantic | 1.0 |
| sparse.mrr | 0.9212962962962963 |
| sparse.mrr_by_qtype.lexical | 0.9313725490196079 |
| sparse.mrr_by_qtype.semantic | 0.9122807017543859 |
| sparse.n_scored | 36.0 |
| sparse.negative_false_positive_rate | 1.0 |

### single_game_chat
Run: `20260729T152857Z_single_game_chat.json` (2026-07-29T15:28:57.072880+00:00)

| Metric | Value |
|--------|-------|
| faithfulness | 0.7130819024564187 |
| grounded_rate | 1.0 |
| intent_valid_rate | 1.0 |
| n_scenarios | 32.0 |
| response_relevancy | 0.6336553517031368 |

### tone_fidelity
Run: `20260729T074141Z_tone_fidelity.json` (2026-07-29T07:41:41.218002+00:00)

| Metric | Value |
|--------|-------|
| coach.tone_fidelity_rate | 1.0 |
| kid.tone_fidelity_rate | 0.8333333333333334 |
| n_generated | 30.0 |
| n_judged | 25.0 |
| self_learner.tone_fidelity_rate | 0.8888888888888888 |
| tone_fidelity_rate | 0.92 |

### training_fidelity
Run: `20260729T151922Z_training_fidelity.json` (2026-07-29T15:19:22.914063+00:00)

| Metric | Value |
|--------|-------|
| grounded_rate | 1.0 |
| kid_safety_rate | 1.0 |
| n_scenarios | 30.0 |
| top_weakness_invariance_rate | 0.9888888888888889 |

## Regressions (run-over-run)

| Suite | Metric | Previous | Current | Delta |
|-------|--------|----------|---------|-------|
| persona_fidelity | grounded_rate | 0.8666666666666667 | 0.7333333333333333 | -0.1333 |
| persona_fidelity | fact_invariance_rate | 1.0 | 0.9444444444444444 | -0.0556 |
| single_game_chat | response_relevancy | 0.7445377905181683 | 0.6336553517031368 | -0.1109 |
| memory_quality | retention_true_positive_rate | 1.0 | 0.8421052631578947 | -0.1579 |
| agent_trajectory | multi_agent.avg_tool_call_count | 1.1666666666666667 | 1.0833333333333333 | -0.0833 |

## Hard gate failures

None.
