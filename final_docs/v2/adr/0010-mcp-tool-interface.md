# ADR-0010 — MCP Server over a Shared Tool Layer

- **Status**: Proposed — pending owner sign-off (new to the plan)
- **Date**: 2026-07-25
- **Phase**: 0, implemented in Phase 12
- **Deciders**: Project owner

## Context

The owner requires MCP as one of the concepts the project demonstrates. The original plan
did not mention it.

The naive approach is to build an MCP server as a separate surface that reimplements what
the agents already do. That produces two code paths for the same capability, which drift.

## Decision

One tool layer, in `orchestration/tools/`, consumed by two surfaces:

```
LangGraph agents ─┐
                  ├─→ orchestration/tools/ ─→ services/ ─→ repositories/
MCP server ───────┘
```

Tools are thin wrappers over services. They contain schema validation, permission checks,
and error shaping — no business logic, which lives in services.

Initial tool set:

| Tool | Purpose |
|------|---------|
| `analyze_pgn` | Submit a PGN for analysis |
| `get_game_analysis` | Fetch a canonical analysis object |
| `list_critical_moments` | Pivotal plies with eval swings |
| `get_profile_aggregate` | Cross-game patterns for a window |
| `search_knowledge` | Retrieve from a corpus bucket |
| `lookup_opening` | ECO and name from an EPD |
| `validate_line` | Legality check for a variation |

Every tool call carries an authenticated identity and is permission-scoped. No tool
accepts a `profile_id` without checking the caller may access it.

Phase 12 includes a contract test asserting that the MCP path and the internal agent path
return identical results for the same call.

## Rationale

Sharing the implementation is the entire point. A capability that exists twice will behave
differently in the two places eventually — one gets a bug fix, one gets a new parameter —
and the divergence surfaces as a support problem nobody can reproduce. The equality
contract test makes drift a build failure rather than a discovery.

Permission scoping at the tool layer rather than at the service layer is deliberate: the
services are also called by internal code paths that have already established context,
whereas a tool call is the boundary where an external, less-trusted caller arrives. Putting
the check at the boundary keeps it where the untrusted input is.

MCP also has genuine value beyond satisfying a requirement. It lets a user point their own
assistant at their GrandMate analysis, which is a real use case for a companion product
whose value is the analysis rather than the interface.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| MCP server reimplementing logic independently | Two code paths, guaranteed drift |
| MCP server calling the public REST API over HTTP | Extra network hop and auth translation for an in-process capability |
| Exposing services directly as MCP tools | No place for schema validation, permission scoping, or error shaping |
| Skipping MCP | Explicitly required by the owner |

## Consequences

### Positive
- One implementation per capability
- External assistants can use GrandMate analysis
- Permission enforcement concentrated at the untrusted boundary
- Equality test prevents drift

### Negative
- Tool schemas are a public contract and become expensive to change
- MCP surface is an additional security boundary to audit
- Tool granularity needs care: too fine and agents make many calls, too coarse and responses are bloated

### Follow-up required
- Phase 12: tool schemas, permission tests per tool, MCP/internal equality test
- Phase 12: confirm the tool surface with the owner before publishing it
- Phase 17: include the MCP surface in the security review

## References
- `final_docs/v2/rag-architecture.md` §4
- Decision D-016
