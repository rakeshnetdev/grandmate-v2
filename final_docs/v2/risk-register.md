# Risk Register

Reviewed at every phase gate. Impact is on the product; likelihood is the honest estimate,
not the comfortable one.

## Critical

| ID | Risk | Impact | Likelihood | Mitigation | Owner phase |
|----|------|--------|------------|------------|-------------|
| R-01 | `analysis` retrieval crosses a profile boundary, exposing one user's games to another | Privacy breach, trust loss | Medium | Isolation enforced inside the retriever interface with a required `profile_id`; dedicated CI isolation suite; audit events on cross-profile access | 7, 11 |
| R-02 | LLM asserts chess claims that contradict engine truth | Users learn something false | High without mitigation | Grounding guardrail, critic agent, `validate_line` tool, Faithfulness gate at 0.85 | 10, 13 |
| R-03 | Kid persona delivers a false or harshly framed finding to a child | Real harm to a learner | Medium | Suppress low-confidence findings entirely for kid persona; content safety tests; grounding applies before persona rendering | 9 |
| R-04 | Secrets committed to the repository | Credential compromise | Medium | `.env` gitignored, `.env.example` blank, pre-commit secret scanning, Claude never prints key values | 1 |

## High

| ID | Risk | Impact | Likelihood | Mitigation | Owner phase |
|----|------|--------|------------|------------|-------------|
| R-05 | Engine analysis too slow or costly at scale | Product unusable on large imports | High | Tiered depth policy, depth 12 baseline, background workers, measured cost per game | 5 |
| R-06 | Retrieval returns plausible but irrelevant context | Confidently wrong answers | High | Multi-bucket routing, hybrid retrieval, Context Precision and Recall gates per bucket | 7 |
| R-07 | Corpus contains unlicensed or unattributed material | Legal exposure | Medium | Provenance required per document; no licence, no ingestion | 7 |
| R-08 | Pattern detectors overfit and produce false positives | Users drill the wrong things | High | Curated positive and false-positive sets; confidence scores; high-difficulty motifs held behind engine corroboration | 6 |
| R-09 | Memory stores stale or wrong durable facts | Assistant confidently repeats a falsehood for months | Medium | Confidence floor on writes, supersede-not-overwrite, user-visible audit and delete | 11 |
| R-10 | Persona layer distorts chess truth while simplifying | Core product claim is false | Medium | Fact-set invariance test with zero tolerance | 9 |
| R-11 | MCP surface exposes more capability than intended | Unauthorised data access | Medium | Curated tool list, permission-scoped execution, per-tool contract tests | 12 |
| R-12 | Schema becomes tangled across 19 phases | Velocity collapse | Medium | Domain ownership, ADRs, migration discipline with rollback plans | ongoing |

## Medium

| ID | Risk | Impact | Likelihood | Mitigation | Owner phase |
|----|------|--------|------------|------------|-------------|
| R-13 | Agent loops or runaway tool calls | Cost spike, latency | Medium | Step ceilings, tool-call ceilings, token budgets, trajectory tracing | 10 |
| R-14 | Multi-agent adds cost without adding quality | Wasted complexity | Medium | Measured against the single-agent baseline; kept only on evidence | 13 |
| R-15 | External APIs change or rate-limit | Imports break | Medium | Connector abstraction, recorded fixtures, backoff, conservative rate limits | 14 |
| R-16 | Fine-tuning masks a retrieval defect | Harder-to-debug system | Low | Scoped to tone only, gated on evidence, chess truth stays deterministic | 16 |
| R-17 | Scope creep from the agentic capability list | Phases never close | High | Phase gates with explicit sign-off; capabilities land in their own phases | ongoing |

## Low

| ID | Risk | Impact | Likelihood | Mitigation | Owner phase |
|----|------|--------|------------|------------|-------------|
| R-18 | Chess.com partner OAuth never approved | No Chess.com login | Medium | MVP designed around username linking, so approval is an upgrade not a dependency | 14 |
| R-19 | Stockfish unavailable in the deployment target | Analysis unavailable | Low | Path configurable; containerised with the binary; verified locally | 17 |
| R-20 | Lichess dataset licence changes | Opening detection rebuild | Low | CC0 material already retrieved and vendored with its licence recorded | 6 |

## Accepted risks

| Risk | Why accepted |
|------|-------------|
| Analysis of opponent profiles raises consent questions | Analyst persona deferred; MVP restricts analysis to owned and explicitly linked profiles |
| LLM judge variance affects gating | Tolerance band plus trend comparison rather than single-run gating |
| Depth 12 is shallower than serious analysis | Deliberate cost trade-off; tiered deep pass covers the positions that matter; configurable |
