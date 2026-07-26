# Success Metrics

Phase 0 definition. Instrumented progressively; dashboards land at Phase 17.

## Product metrics

| Metric | Definition | Target | Measured from |
|--------|-----------|--------|---------------|
| Login completion rate | Lichess OAuth flows started that reach a session | > 95% | Phase 2 |
| Import success rate | Import jobs completing without error | > 98% | Phase 14 |
| Parse success rate | PGNs parsed into a canonical object | > 99% | Phase 4 |
| Analysis completion rate | Parsed games reaching completed analysis | > 98% | Phase 5 |
| Time to first insight | Login → first aggregate visible | < 5 min for 30 games | Phase 8 |
| Chat usefulness | User rating per answer | > 4.0 / 5 | Phase 18 |
| Memory usefulness | User rating of recalled context | > 4.0 / 5 | Phase 18 |
| Training plan follow-through | Plans with at least one theme marked worked-on | > 40% | Phase 18 |
| Persona satisfaction | Rating segmented by persona | > 4.0 / 5 each | Phase 18 |

## Quality metrics

Thresholds and gating rules in `evaluation-strategy.md`.

| Metric | Target |
|--------|--------|
| Faithfulness | ≥ 0.85 |
| Answer Accuracy | ≥ 0.80 |
| Context Precision | ≥ 0.75 |
| Context Recall | ≥ 0.75 |
| Illegal move rate in delivered answers | 0 |
| Cross-profile retrieval leaks | 0 |
| Persona fact-set divergence | 0 |
| Motif detector precision | ≥ 0.85 on shipped motifs |

## Engineering metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Analysis time per game | < 30s at depth 12 | Baseline sweep plus deep pass |
| Engine determinism | 100% identical classifications across runs | Requires `ENGINE_THREADS=1` |
| Chat p95 latency | < 8s single-agent, < 15s multi-agent | |
| Agent step overrun rate | 0 | Ceilings are hard limits |
| CI duration | < 10 min | |
| Job retry rate | < 2% | |

## Cost metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Cost per analysed game | Tracked from Phase 5 | Engine compute dominates |
| LLM tokens per chat turn | < `AGENT_TOKEN_BUDGET` | Hard ceiling |
| Cost per active user per month | Tracked from Phase 17 | Needed before any pricing conversation |

## Metrics deliberately not tracked

- Engine strength or Elo. Stockfish is a dependency, not a differentiator.
- Raw message volume. High chat volume may mean the reports are unclear, not that the
  product is working.
- Time on site. Faster resolution is better here, not worse.

Choosing what not to measure matters as much as choosing what to measure — an engagement
metric on a coaching tool rewards the wrong behaviour.
