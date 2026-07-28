# ADR-0016 — Private Study Profile for Unowned/Arbitrary PGN Analysis

- **Status**: Accepted
- **Date**: 2026-07-27
- **Phase**: 8b
- **Deciders**: Project owner

## Context

Phase 8's dashboard is only trustworthy to test against a profile whose games are
genuinely the logged-in user's own — but nothing in Phases 3–8 ever restricted *what*
could be imported into a `SELF` profile. Testing surfaced real accounts with games that
were plainly not the logged-in user's (e.g. historical Magnus Carlsen games, or games
whose header names didn't match the account's linked platform username at all), which
Phase 4's exact-match focus resolution correctly left `focus_color = NULL` for — but
Phase 8's aggregate metrics still counted them as part of that profile's own trend and
weakness data, because import never distinguished "my game" from "a game I uploaded to
study."

The owner's stated need: log in with Lichess/Chess.com, and any game matching that
identity should land on *their own* dashboard. Any other PGN — a game they weren't part
of, or one loaded purely to learn from — should go somewhere else entirely, and must
never affect their own trend/weakness numbers.

This runs directly into **ADR-0012** (Self Dashboard, Separate Permission-Gated Page for
Others), which deferred "analysing arbitrary opponents" in MVP specifically because
"a public game and a profiled weakness assessment are different artefacts," and a
weakness assessment about a real person who hasn't consented is a genuine artifact to be
careful about.

## Decision

**Every account gets a second, always-present profile** — `kind = OPPONENT`, created
alongside the existing `SELF` profile at first login (`display_name = "Study games"`).
This profile runs the **full** Phase 5–8 pipeline (engine analysis, opening/motif/theme
detection, aggregate trends, recurring weaknesses) — not a restricted, per-game-only
view.

**Import routing is automatic and per-game**, not a user choice at upload time. Before a
parsed game is persisted, its `White`/`Black` headers are checked against the account's
linked platform username(s) — the same check Phase 4 already does for `focus_color`, just
run earlier. A match routes the game to `SELF`; no match routes it to the study profile.
A single pasted batch can split across both.

**No sharing, ever.** The study profile is owned by, and only ever visible to, the
importing user's own account. No `profile_relationships` row is ever created for it; it
is not the "observed opponent" profile `profiles.kind = opponent` was originally sketched
for in `data-model.md` (a profile a *coach* might view via permission grant) — same enum
value, a different, more private usage: a personal scratch space, structurally identical
to a folder, not a shared record about a real tracked person.

## Rationale

ADR-0012's consent concern is about **exposure to other viewers** — a coach or parent
seeing a persistent weakness assessment of a specific real person who never agreed to
being profiled that way. This decision does not create that exposure: the study profile
has exactly one possible viewer, the same account that chose to import the material, for
exactly the same reason someone might replay a famous game in a personal notebook. There
is no scouting-report use case here and no mechanism to build one — `profile_relationships`
is simply never wired to this profile kind's rows.

That is a materially different case from "a coach building a trackable dossier on a
specific rival," which is what ADR-0012 deferred and remains deferred. This ADR narrows
that gap by exactly the amount needed to make personal study material safe, and no
further: it does not reopen cross-account viewing, does not add a way to name or persist
identity for the people in a studied game, and does not touch the `/players/:profileId`
permission-gated page ADR-0012 describes for Phase 9.

Running the full pipeline (not a restricted view) on the study profile was the
owner's explicit choice over a narrower alternative (Option B below) — the value of a
study dashboard is in seeing the same trend/weakness signal Phase 8 already computes,
applied to games chosen for learning, not just a per-game readout.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Restrict the study profile to Phase 8a's per-game view only, no aggregation | Would have stayed strictly inside ADR-0012 with zero new reasoning required, but loses the actual value (trend/weakness signal) the owner wants from study material |
| A manual "import target" picker on the upload form | Owner's stated model is identity-based auto-routing ("any game with my username"), not a manual choice per upload |
| A new `ProfileKind.STUDY` enum value instead of reusing `OPPONENT` | No added distinction at the schema level over documenting the second usage in this ADR; avoids a migration for a label-only change |
| Treat this as reopening ADR-0012 broadly | ADR-0012 governs cross-*account* viewing with permission grants; this is single-account, never viewed by anyone else — not the same mechanism, so not the same decision |

## Consequences

### Positive
- Own-vs-study separation happens automatically, matching how the owner actually thinks
  about their games, with no manual per-upload step
- Full Phase 8 value (trends, recurring weaknesses) available for study material
- No new permission surface, no `profile_relationships` wiring, no sharing mechanism —
  the privacy question ADR-0012 raised for cross-*account* viewing is untouched

### Negative
- `profiles.kind = opponent` now carries two distinct meanings in practice (a private
  single-user study bucket here; a potentially coach-viewable tracked profile per
  `data-model.md`'s original sketch) distinguished only by whether a
  `profile_relationships` row ever gets created for it — worth a real `STUDY` kind if
  Phase 9's `/players/:profileId` work makes the overlap confusing in practice
- A study profile with real people's games still generates and stores real
  motif/theme/weakness rows about them, even though never shown to anyone but the
  importer — acceptable for MVP per the rationale above, but worth remembering if data
  retention/export questions come up later

### Follow-up required
- Phase 9: when `/players/:profileId` (ADR-0012) is implemented, confirm it only ever
  operates on `profile_relationships`-linked profiles and never accidentally exposes a
  user's private study profile
- If the dual meaning of `kind = opponent` becomes confusing in practice, split it into a
  distinct `STUDY` kind — additive migration, not a redesign

## References
- ADR-0012 — Self Dashboard, Separate Permission-Gated Page for Others
- `final_docs/v2/data-model.md` — `profiles`, `profile_relationships`
- `final_docs/v2/decisions-log.md` — D-004, D-021
- `final_docs/v2/phase-reports/phase-08-multi-game-aggregation.md`
