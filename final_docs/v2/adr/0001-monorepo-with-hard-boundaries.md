# ADR-0001 — Monorepo with Hard Boundaries

- **Status**: Accepted
- **Date**: 2026-07-25
- **Phase**: 0
- **Deciders**: Project owner

## Context

`claude.md` rule 1 requires backend and frontend to remain separate. That rule can be
satisfied by two repositories or by one repository with enforced boundaries. The project
is being built by a small team and needs coordinated phase-by-phase delivery where a
backend contract change and its frontend consumer land together.

## Decision

A single repository, `grandmate-v2/`, containing `backend/` and `frontend/` as separate
subprojects with independent toolchains, dependency manifests, test suites, and CI jobs.

Boundaries are enforced by:
- no shared build system or dependency graph between the two,
- separate CI jobs that can fail independently,
- a typed API contract as the only coupling point,
- no imports across the boundary at any level.

## Rationale

Two repositories would enforce separation by construction but impose a coordination cost
on every contract change — two PRs, two reviews, a version skew window. For a phase-gated
project where each phase delivers a vertical slice, that cost is paid constantly and buys
little, because the same people own both sides.

The separation that actually matters here is architectural, not physical. What must never
happen is domain logic leaking across the boundary or the frontend reaching into backend
internals. A directory boundary with no shared dependency graph prevents that just as
effectively as a repository boundary, and the project structure discipline in `claude.md`
enforces the rest.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Two separate repositories | Coordination overhead on every contract change; version skew during phase delivery |
| Monorepo with a shared workspace and common tooling | Creates exactly the coupling rule 1 forbids |
| Monorepo with shared TypeScript types generated from Pydantic | Attractive, but adds a build step in Phase 1 for a benefit not needed until Phase 3; revisit later |

## Consequences

### Positive
- One clone, one branch, one PR per vertical slice
- Phase gates apply cleanly to the whole system
- Easier to keep documentation and code in sync

### Negative
- Deployment must select a subdirectory; both services cannot be deployed from the repo root naively
- CI must scope jobs by path to avoid running frontend tests on backend-only changes
- The boundary is a convention, so it requires review discipline rather than being impossible to violate

### Follow-up required
- Phase 1: path-scoped CI jobs
- Phase 17: deployment topology, deferred per D-006

## References
- `claude.md` non-negotiable rule 1
- `project-plan.md` — suggested folder structures
