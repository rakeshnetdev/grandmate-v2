# Phase Map — Original Plan to Revised Plan

The original `project-plan.md` defined 15 phases (0–14). The revised plan defines 19
(0–18). This document records the mapping so nothing from the approved plan is lost.

## Why the plan changed

The project owner confirmed in Phase 0 that GrandMate must demonstrate agentic RAG,
multi-RAG, MCP, evaluations, synthetic and golden datasets, fine-tuning, agents,
multi-agents, and LangGraph — and that RAG in particular is central rather than
supporting.

The original plan covered LangGraph and RAGAS but did not cover MCP, multi-agent
orchestration, or fine-tuning at all, and it treated retrieval as an optional
"pgvector if semantic retrieval is needed later". That framing is incompatible with a
product whose chat must retrieve knowledge wherever knowledge is needed.

Rather than bolt these onto existing phases and produce three phases that each try to do
two jobs, three new phases were inserted and the evaluation phase was expanded.

Recorded per the deviation rule in `claude.md`: this is a documented, approval-pending
change, not a silent one.

## Mapping

| Original | Revised | Change |
|----------|---------|--------|
| 0 — Discovery and Decision Baseline | 0 | Expanded: adds RAG architecture note, evaluation strategy, configuration contract |
| 1 — Repository, CI/CD, Engineering Foundation | 1 — Engineering Foundation | Adds the configuration and secrets discipline as a first-class deliverable |
| 2 — Supabase Foundation and Auth | 2 — Supabase Foundation and Identity | **Materially changed**: Lichess OAuth PKCE replaces Supabase Auth; Chess.com username linking added |
| 3 — Ingestion MVP | 3 | Unchanged |
| 4 — Parsing and Canonical Game Object | 4 | Adds EPD generation per ply for opening lookup |
| 5 — Engine Analysis Core | 5 | Adds the tiered depth policy; baseline depth fixed at 12 |
| 6 — Opening Detection and Chess Intelligence Tags | 6 | Opening source changed to the Lichess CC0 dataset, matched on EPD |
| — | **7 — Knowledge Corpus and RAG Foundation** | **New** |
| 7 — Multi-Game Aggregation | 8 | Renumbered |
| 8 — Persona Layer and Report Generation | 9 | Renumbered; personas fixed at self-learner, coach, kid; PDF deferred |
| 9 — Chat with Short-Term Memory | 10 — Agentic RAG Chat with Short-Term Memory | Reshaped: retrieval exposed as agent tools rather than a fixed chain |
| 10 — Long-Term Memory | 11 | Renumbered |
| — | **12 — MCP Client Integration** | **New; reversed from server to client direction, then deferred entirely — no product use case yet, see ADR-0010/D-027/D-028** |
| — | **13 — Multi-Agent Orchestration** | **New** |
| 11 — Lichess and Chess.com Connectors | 14 | Renumbered; Lichess import now uses the login token |
| 12 — Training Plan and Coaching Recommendations | 15 | Renumbered |
| — | **16 — Evaluation, Synthetic Data, Golden Sets, Fine-Tuning** | **New / expanded** from the original plan's scattered evaluation requirements |
| 13 — Observability, Security, Hardening | 17 | Adds the deferred hosting decision |
| 14 — Beta Rollout | 18 | Renumbered |

## Nothing was dropped

Every deliverable in the original 15 phases appears in the revised 19. The additions are
additive. The two substantive changes to existing phases are:

1. **Phase 2 identity** — driven by the owner's requirement that users log in with their
   chess platform account, plus the discovered constraint that Chess.com OAuth is
   approval-gated. See ADR-0007.
2. **Phase 10 chat shape** — driven by the requirement that RAG be agentic. The original
   phase's deliverables all survive; the retrieval mechanism differs. See ADR-0008.

## Deferred, not dropped

| Item | Deferred to |
|------|-------------|
| Parent and analyst personas | Post-MVP |
| PDF export | Post-MVP |
| Chess.com OAuth login | Phase 14, contingent on external approval |
| Hosting and deployment topology | Phase 17 |
| Realtime job progress | Phase 17, only if needed |
