# ADR-0012 — Self Dashboard, Separate Permission-Gated Page for Others

- **Status**: Accepted
- **Date**: 2026-07-25
- **Phase**: 0, implemented in Phases 2 and 9
- **Deciders**: Project owner

## Context

The owner's requirement: *"After login based on lichess or chess, they have their
dashboard or view. To see others it can be on separate page, leverage most of the logic
used for self view."*

The original plan left "whether opponents/other profiles can be analyzed in MVP" as an open
question with privacy implications.

## Decision

**Own dashboard.** After login, the user lands on a dashboard scoped to their own profile.
It never mixes in other players' data.

**Separate page for others.** Viewing another player happens at a distinct route
(`/players/:profileId`), reusing the same analysis pipeline, aggregation logic, and view
components as the self view. The differences are the permission gate and which persona
modes are offered.

**Permission gate.** Access requires a row in `profile_relationships` linking the viewer to
the subject profile with a role, not revoked. There is no implicit access.

**MVP scope.** Only owned profiles and explicitly linked profiles (coach↔student,
parent↔child) are viewable. Analysing arbitrary opponents is deferred with the analyst
persona.

**Audit.** Every cross-profile view emits an `audit_events` row.

## Rationale

Reusing the self-view logic is the owner's explicit instruction and is also the right
design: the analysis of a game does not depend on who is looking at it. Truth level 1 and
truth level 2 are viewer-independent by construction (ADR-0003, ADR-0011), so the only
thing that legitimately varies is permission and presentation. Building a second pipeline
for observed profiles would duplicate chess logic, which `claude.md` forbids.

A separate route rather than a profile switcher on the same page keeps the permission
boundary visible in the URL, which makes it far easier to reason about and to test. A
switcher invites the bug where a stale profile id from one render leaks into a query on the
next.

Restricting MVP to linked profiles is the conservative choice on a genuine privacy
question. Analysing an arbitrary opponent means generating findings about someone who has
not consented to being analysed. Their games may be public, but a public game and a
profiled weakness assessment are different artefacts. Deferring this until the permission
model has been exercised in practice costs little — opponent prep is not an MVP journey —
and avoids shipping something hard to walk back.

Audit events on cross-profile access exist because a coach viewing twelve students is
normal and an account viewing four hundred profiles is not. Without the log there is no way
to tell them apart.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Profile switcher on the same dashboard | Permission boundary becomes invisible; stale-id leakage risk |
| Separate page with its own analysis pipeline | Duplicates chess logic; violates the single-core rule |
| Allow analysing any public username in MVP | Consent question unresolved; deferred with the analyst persona |
| Implicit access to any profile the user imported games for | Importing someone's public games is not a relationship |

## Consequences

### Positive
- One analysis core, two entry points
- Permission boundary visible in routing and testable
- Cross-profile access auditable
- Conservative default on an unresolved privacy question

### Negative
- Coaches with many students navigate between pages rather than switching in place
- Relationship rows must be created before a coach can view a student, so an invitation flow is needed
- Opponent preparation, a genuinely valuable use case, is unavailable in MVP

### Follow-up required
- Phase 2: `profile_relationships` schema, permission dependency, audit events
- Phase 9: confirm which persona modes are offered on the observed-profile page
- Post-MVP: consent model for analysing unlinked public profiles, alongside the analyst persona

## References
- `final_docs/v2/data-model.md` — `profile_relationships`
- `final_docs/v2/persona-matrix.md` — deferred personas
- Decision D-004
