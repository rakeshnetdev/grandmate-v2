# ADR-0010 — MCP as a Client Capability, Not a Server Surface

- **Status**: Deferred — client direction confirmed, but no external MCP tool has a real
  use case in the product yet; implementation paused until one exists (see D-028)
- **Date**: 2026-07-28 (supersedes the 2026-07-25 draft below `## Superseded draft`)
- **Phase**: 0, deferred out of Phase 12 (see D-028)
- **Deciders**: Project owner

## Context

D-016 requires the project to demonstrate MCP. The original draft of this ADR (see
`## Superseded draft`) planned an MCP *server*: GrandMate's own tools
(`analyze_pgn`, `get_game_analysis`, `search_knowledge`, etc.) exposed for external
clients to call, sharing implementation with the internal LangGraph agent per rule 13.

Before Phase 12 implementation began, the owner reversed this direction: **GrandMate does
not expose any of its own capability over MCP.** No outward-facing server, no external
caller granted access to a profile's analysis or aggregate data. Recorded as D-027.

## Decision

MCP is demonstrated as a **client** capability instead. GrandMate's chat agent gains one
or more tools that are themselves thin wrappers around an *external* MCP tool (web search
/ fetch), reached over the MCP client protocol rather than a bespoke HTTP integration.

```
LangGraph chat agent ─→ orchestration/tools/registry.py (TOOL_DISPATCH)
                              │
                              ├─→ internal tools → services/ → repositories/  (unchanged)
                              │
                              └─→ external MCP tool wrapper → MCP client → external MCP server
```

The external tool is registered in the same `TOOL_DISPATCH` table the internal tools use
(`backend/app/orchestration/tools/registry.py`), so the agent has one place to look for
"what can I call," regardless of whether the implementation is local or a remote MCP
server. This preserves rule 13's spirit — one contract per capability — even though the
capability itself is now inbound rather than outbound.

No permission scoping is required on the *outbound* side (GrandMate is the caller, not the
callee), but the tool wrapper still validates and shapes whatever the external server
returns before the agent sees it — an external MCP server is untrusted input, the same as
any other third-party API response.

## Rationale

Exposing GrandMate's own analysis and profile data through an MCP server was assessed as
unnecessary surface for what this project actually needs: nobody outside GrandMate's own
chat currently needs to call `get_game_analysis` directly, and every external caller would
be a new authentication and permission boundary to design, build, and audit (per the
superseded draft's own "Negative consequences": *"MCP surface is an additional security
boundary to audit"*). Demonstrating MCP does not require taking on that risk — consuming
an external MCP tool satisfies D-016 with none of it: nothing about a profile leaves the
system, because GrandMate is the one placing calls, not answering them.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| MCP server exposing GrandMate's own tools (original ADR-0010 draft) | Real value (a user's own assistant could reach their analysis) but adds an external-facing auth/permission boundary purely to satisfy a demonstration requirement; owner judged the risk not worth it for this project |
| Skip MCP entirely | Conflicts with D-016, which is locked |
| Build a bespoke HTTP integration to a search API instead of MCP | Would satisfy the search need but not the MCP demonstration requirement |

## Consequences

### Positive
- Satisfies D-016 without creating any external-facing attack surface
- No new authentication/permission design needed — GrandMate's existing profile isolation
  is untouched, since no external caller ever reaches it
- Still exercises real MCP client/server protocol mechanics (tool discovery, schema
  negotiation, invocation) — the requirement is about demonstrating the protocol, and the
  client side demonstrates it as legitimately as the server side would

### Negative
- Drops the genuine product value the original draft identified (a user pointing their
  own assistant at their GrandMate analysis) — deferred, not ruled out permanently; can be
  revisited post-MVP if there's real demand
- The external MCP server's reliability, rate limits, and cost become GrandMate's problem
  whenever the chat agent calls it — same care as any third-party integration (rule 11:
  no hardcoded rate limits or keys; provider details behind an adapter)

### Follow-up required
- **Deferred (D-028)**: no external MCP tool has a concrete trigger in the product today.
  `fetch` (user-pasted URL) was the only candidate that survived rule 8/9 scrutiny — search
  was rejected outright — but nothing in the current chat flow invites a user to paste a
  link. Revisit once such a flow exists, likely alongside Phase 13's multi-agent work.
- When revisited: confirm the specific external MCP server package and any required
  `.env` credential with the owner before coding (claude.md: never invent a placeholder
  credential); tool schema for the wrapper; error shaping for external-server failures
  (timeout, rate limit, malformed response); step/token budget same as any agent tool
- Phase 17: include the MCP client dependency in the security review, once it exists

## References
- `final_docs/v2/decisions-log.md` D-016, D-027
- `backend/app/orchestration/tools/registry.py`

---

## Superseded draft (2026-07-25) — kept for record only, decision above supersedes it

> The owner requires MCP as one of the concepts the project demonstrates. The original
> plan did not mention it.
>
> The naive approach is to build an MCP server as a separate surface that reimplements
> what the agents already do. That produces two code paths for the same capability, which
> drift.
>
> **Decision (superseded)**: One tool layer, in `orchestration/tools/`, consumed by two
> surfaces — LangGraph agents and an MCP server, both calling through to
> `services/` → `repositories/`. Initial tool set: `analyze_pgn`, `get_game_analysis`,
> `list_critical_moments`, `get_profile_aggregate`, `search_knowledge`, `lookup_opening`,
> `validate_line`. Every tool call would carry an authenticated identity and be
> permission-scoped; a contract test would assert the MCP path and internal agent path
> return identical results.
>
> This plan is not being built. See the decision above.
