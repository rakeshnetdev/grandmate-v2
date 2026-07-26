# Domain Modules

Business rules live here. Not in routes, not in worker task files, not in prompt builders.

## Module template

Every domain module follows the same shape. Copy this structure when adding one.

```
app/domain/<name>/
  __init__.py       # public surface — what other modules may import
  models.py         # domain models (Pydantic). Not API schemas, not DB rows.
  service.py        # the rules. Pure where possible; no I/O of its own.
  repository.py     # persistence Protocol. The implementation lives in app/repositories/.
  errors.py         # module-specific exceptions
```

Tests go in `backend/tests/domain/<name>/`.

## Rules

**Domain models are not API schemas.** `app/schemas/` holds what crosses the HTTP
boundary; `models.py` holds what the domain reasons about. They drift, and coupling them
means an API change forces a domain change.

**Repositories are Protocols here, implementations elsewhere.** The domain declares what
persistence it needs; `app/repositories/` provides it. This is what lets domain logic be
unit-tested without a database.

**Services take their dependencies as arguments.** No module-level singletons, no
`get_settings()` inside a service. Pass the settings slice the service needs.

**No cross-domain imports without thought.** If `analysis` needs something from `games`,
import from `app.domain.games` (the public surface), never from
`app.domain.games.service` internals.

## The layer boundary that is enforced in CI

`tests/test_layer_boundaries.py` fails the build if the deterministic chess core imports
LLM or prompt code. Per ADR-0003:

| Layer | Modules | May not import |
|-------|---------|----------------|
| Deterministic core | `games`, `analysis`, `patterns`, `aggregation` | anything LLM-related, `orchestration`, `domain.chat` |
| Explanation layer | `chat`, `reports`, `orchestration` | nothing restricted — it reads the core |

The dependency points one way. The core is reproducible and testable with exact
assertions; the explanation layer is stochastic. Mixing them makes the first untestable
and the second unaccountable.

## Planned modules

| Module | Phase | Responsibility |
|--------|-------|---------------|
| `profiles` | 2 | Profiles, relationships, permission rules |
| `imports` | 3 | Source normalisation, deduplication, job contracts |
| `games` | 4 | PGN representation, moves, positions, validation |
| `analysis` | 5 | Engine policy, move labelling, critical moments |
| `patterns` | 6 | Tactic and strategy detectors, training theme mapping |
| `knowledge` | 7 | Corpus model, chunking policy, provenance |
| `retrieval` | 7 | Retriever interfaces, bucket routing, fusion |
| `aggregation` | 8 | Rollups, trend scoring |
| `reports` | 9 | Persona transformation, report contracts |
| `chat` | 10 | Context building, answer contracts, grounding guardrail |
| `memory` | 11 | Short-term state, long-term memory, write policy |
