# ADR-0011 — Persona and Role Are Orthogonal

- **Status**: Accepted
- **Date**: 2026-07-25
- **Phase**: 0, implemented in Phase 9
- **Deciders**: Project owner

## Context

`claude.md` requires that profile relationship (role) and persona presentation mode stay
distinct, and that one analysis core serve all personas without duplicating chess logic.

MVP personas are self-learner, coach, and kid. Parent and analyst are deferred.

## Decision

**Role** is a property of `profile_relationships` — owner, coach, parent, viewer, student.
It governs permission: whether a user may see a profile at all.

**Persona** is a rendering mode — self-learner, coach, kid. It governs presentation: tone,
depth, vocabulary, and which recommendations are offered.

They are independently selectable. Any permitted role may use any available persona.

The persona layer is a pure transformation over an already-computed analysis object. It
lives in `domain/reports` and `domain/chat`, downstream of everything deterministic. It
receives facts and emits phrasing.

**Fact-set invariance** is enforced by test: rendering the same analysis object through
every persona must yield the identical set of referenced fact ids. Zero tolerance.

MVP scope: self-learner, coach, kid. In-app HTML reports. PDF export deferred.

## Rationale

The concepts answer different questions. Role answers "may this user see this data".
Persona answers "how should it be worded". Merging them means a permission change silently
alters tone, or a tone change silently alters permission — both are confusing and one is a
security bug.

The concrete case that settles it: a parent (role) viewing their child's profile may well
want the coach persona's full detail rather than the kid persona's simplification.
Assuming otherwise would be both patronising and wrong. Equally, a coach may deliberately
render a student's analysis in the kid persona to prepare the language they will use in a
lesson. Neither combination is exotic; both are broken by conflation.

Fact-set invariance is the testable form of "personas must not alter chess truth". Without
it, the rule is an aspiration that erodes as prompts are tuned. With it, a persona that
quietly drops an inconvenient finding fails the build.

Three personas rather than five keeps the fidelity test matrix tractable while still
proving the layer works — self-learner and coach differ mainly in depth, while kid differs
in vocabulary and safety rules, so the three cover meaningfully different transformation
axes.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| One combined "view mode" concept | Conflates permission with presentation; breaks the parent-wants-detail case |
| Persona implied by role | Removes user choice; wrong for coach-drafting-kid-language |
| All five personas in MVP | Fidelity test matrix grows without proving anything the three do not |
| Persona-specific analysis pipelines | Directly violates "same analysis core"; would duplicate chess logic |

## Consequences

### Positive
- One analysis core serves every persona
- Permission and presentation evolve independently
- Fact-set invariance is machine-checkable
- Adding parent and analyst later is additive

### Negative
- Two orthogonal settings to expose in the UI without confusing users
- Persona × role combinations grow the manual review surface
- Kid persona needs suppression rules the others do not, so it is not purely a phrasing change

### Follow-up required
- Phase 9: persona contract tests, fact-set invariance suite, kid content safety tests
- Phase 9: resolve open question Q-5, the kid persona age band, which sets reading-level targets
- Post-MVP: parent and analyst personas; the analyst persona is permission-sensitive and gated on ADR-0012

## References
- `final_docs/v2/persona-matrix.md`
- Decisions D-002, D-014
