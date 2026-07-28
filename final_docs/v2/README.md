# GrandMate v2 — Documentation

Phase 0 documentation set. Start here.

## Read in this order

| Document | What it answers |
|----------|----------------|
| [`prd.md`](prd.md) | What is being built and for whom |
| [`decisions-log.md`](decisions-log.md) | What has been decided, and what is still open |
| [`glossary.md`](glossary.md) | Shared vocabulary and the starter taxonomies |
| [`persona-matrix.md`](persona-matrix.md) | How the same truth is rendered for different audiences |
| [`data-model.md`](data-model.md) | Entities, relationships, and the storage boundaries |
| [`rag-architecture.md`](rag-architecture.md) | How retrieval, agents, and grounding fit together |
| [`evaluation-strategy.md`](evaluation-strategy.md) | How quality is measured and gated |
| [`configuration.md`](configuration.md) | Every environment variable and when the owner must supply one |
| [`metrics.md`](metrics.md) | Success metrics and targets |
| [`risk-register.md`](risk-register.md) | What could go wrong and what is being done about it |
| [`definition-of-done.md`](definition-of-done.md) | When a phase is actually finished |
| [`phase-map.md`](phase-map.md) | How the revised 19-phase plan maps to the original 15 |

## Architecture decision records

| ADR | Decision | Status |
|-----|----------|--------|
| [0001](adr/0001-monorepo-with-hard-boundaries.md) | Monorepo with hard boundaries | Accepted |
| [0002](adr/0002-supabase-as-system-of-record.md) | Supabase Postgres as system of record | Accepted |
| [0003](adr/0003-deterministic-core-vs-llm-layer.md) | Deterministic core separate from the LLM layer | Accepted |
| [0004](adr/0004-engine-analysis-policy.md) | Tiered engine analysis at baseline depth 12 | Accepted |
| [0005](adr/0005-three-layer-memory-model.md) | Three-layer memory model | Accepted (detail deferred) |
| [0006](adr/0006-llm-provider-abstraction.md) | LLM provider abstraction, `gpt-4o-mini` default | Accepted |
| [0007](adr/0007-identity-and-oauth-strategy.md) | Lichess OAuth login, Chess.com by username | **Proposed — needs sign-off** |
| [0008](adr/0008-agentic-rag-architecture.md) | Agentic, multi-bucket, hybrid RAG | **Proposed — needs sign-off** |
| [0009](adr/0009-opening-data-source.md) | Lichess openings dataset, matched on EPD | Accepted |
| [0010](adr/0010-mcp-tool-interface.md) | MCP server over a shared tool layer | **Proposed — needs sign-off** |
| [0011](adr/0011-persona-and-role-separation.md) | Persona and role are orthogonal | Accepted |
| [0012](adr/0012-cross-profile-viewing-permissions.md) | Self dashboard, separate page for others | Accepted |
| [0013](adr/0013-developer-insight-tracing.md) | Developer insight via out-of-band tracing | Accepted |
| [0015](adr/0015-postgres-for-mvp-supabase-deferred.md) | Plain Postgres + pgvector for MVP, Supabase deferred | Accepted |
| [0016](adr/0016-private-study-profile-for-unowned-pgns.md) | Private study profile for unowned/arbitrary PGN analysis | Accepted |

## Phase reports

| Phase | Report | Status |
|-------|--------|--------|
| 0 | [Discovery and Decision Baseline](checklists/phase-0-completeness.md) | Signed off |
| 1 | [Engineering Foundation](phase-reports/phase-01-engineering-foundation.md) | Pending sign-off |

## Other

- [`changes/0001-reuse-ledger.md`](changes/0001-reuse-ledger.md) — what is being adapted from the reference app, and what was rejected
- [`checklists/phase-0-completeness.md`](checklists/phase-0-completeness.md) — Phase 0 exit criteria assessment
- [`checklists/user-journeys.md`](checklists/user-journeys.md) — journey walkthrough and the gaps it found

## Conventions

- ADRs are numbered sequentially and never renumbered. A reversed decision gets a new ADR marked *Supersedes*.
- `decisions-log.md` is authoritative for product decisions; ADRs carry the architectural reasoning.
- Deviations from `project-plan.md` are documented and need explicit sign-off before implementation.
- Phase reports are added to this directory as each phase completes.
