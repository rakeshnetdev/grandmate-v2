# Phase 12 Report — MCP Client Integration

**Date**: 2026-07-28
**Status**: Deferred, pending sign-off on the deferral (no implementation this phase)
**Branch**: `P12-mcp-server`

## Goal (as originally scoped)

Demonstrate MCP per D-016. The original draft (ADR-0010, written at Phase 0) planned an
MCP *server*: GrandMate's own tools (`analyze_pgn`, `get_game_analysis`,
`search_knowledge`, etc.) exposed to external clients, sharing implementation with the
internal LangGraph agent per rule 13.

## What happened this phase

No code was written. Two decisions were made and recorded before any implementation
began:

1. **Server → client reversal (D-027).** The owner rejected exposing any of
   GrandMate's own capability externally — no outward-facing MCP server, no external
   caller ever granted access to a profile's analysis or aggregate data. MCP would
   instead be demonstrated the other direction: GrandMate as an MCP *client*, consuming
   an external tool from inside the existing chat agent's tool set
   (`backend/app/orchestration/tools/registry.py`).

2. **Deferred entirely (D-028).** Working through what an external MCP tool would
   actually be used for surfaced that nothing in the current product invites it:
   - Open-ended web *search* was rejected outright — an LLM treating live web content as
     chess truth is exactly what rule 8/9 (deterministic chess truth vs. LLM framing)
     exist to prevent.
   - `fetch` (retrieving a user-pasted URL) was the only candidate that survived that
     scrutiny, but no chat flow today invites a user to paste a link for the agent to
     use.

   Rather than build an integration to satisfy D-016's letter with no product need
   behind it, the owner deferred this phase. D-016's MCP requirement is not dropped —
   it stays open until a genuine use case exists, most likely once a chat flow accepting
   user-supplied links or references is designed, possibly alongside Phase 13.

## Files changed

Documentation only, recording the decision trail so it survives for whoever revisits
this phase:

- `final_docs/v2/adr/0010-mcp-tool-interface.md` — rewritten; original server-side draft
  kept verbatim under "Superseded draft" for the record; status now **Deferred**
- `final_docs/v2/decisions-log.md` — D-027 (server→client reversal), D-028 (deferral)
- `project-plan.md` — Phase 12 section marked deferred, plan preserved as the direction
  to pick back up
- `final_docs/v2/phase-map.md` — Phase 12 row updated
- `backend/app/orchestration/tools/registry.py` — module docstring corrected; it
  previously described the superseded server-side plan

## Tests / evaluation

None — no code changed. Not applicable to a documentation-only deferral.

## Known gaps

- D-016's MCP requirement remains formally unresolved.
- No specific external MCP server package or credential has been chosen (correctly —
  there is no use case to size the choice against yet).

## Recommendation

Ready for sign-off as a **deferral**, not a completed build. Suggest moving on to
Phase 13 (Multi-Agent Orchestration) and revisiting MCP client integration if that phase
or a later one produces a real trigger (e.g., a chat flow that accepts user-supplied
links).
