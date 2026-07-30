# Phase 16b Report — Full Game-Story Report

**Date**: 2026-07-29
**Status**: Complete, pending sign-off
**Branch**: `P16b-full-game-story`

**Process note**: at the owner's explicit request, this phase used a lighter-touch
process than Phase 16a/D-036 — no separate `decisions-log.md` entry, no
`persona-matrix.md` update, no `project-plan.md` phase section. This one report plus the
reuse-ledger entry (below) is the full documentation trail. Scope decisions made along
the way are recorded inline below instead of via `AskUserQuestion` rounds.

## Goal

A new "Story" tab: a complete opening/middlegame/endgame narrative of a game — what
opening was played and how it went for both sides, the middlegame and endgame, and
lessons — as opposed to the existing Analysis tab's short list of the player's own
mistakes. Self-learner only, requested directly by the owner after asking Claude to study
the sibling `grandmate/` app's prompt design first for inspiration.

## What the sibling app actually had

Investigated before writing any code (agent-researched, see chat history). Finding: the
sibling's "full report" is the *same* Overview/What Went Well/Mistakes & Blunders/
Strategy format already ported into this codebase as D-036 — it has no existing
opening/middlegame/endgame narrative feature to copy. It does have an abandoned, unused
longer prompt (`NARRATOR_SYSTEM_PROMPT`) for something richer that was never shipped —
worth noting, not a good sign for going long-form. The sibling's own opening/endgame
ply-count and material-count heuristic (`themes.py::classify_theme`) was reused for phase
segmentation here (see reuse ledger), the one piece of real prior art.

## Scope decisions (made directly with the owner before implementation)

1. **Self-learner only.** No coach/kid equivalent yet.
2. **Lighter-touch process** (see note above).

## Design

- **Phase segmentation** (`domain/reports/game_phases.py`): opening ends at the matched
  book ply (or a 12-ply default), endgame starts at the first ply with combined Q/R/B/N
  count ≤ 6 — same thresholds the sibling app uses, computed once for the whole game
  rather than per move. No middlegame/endgame section for a short/sharp game where the
  boundaries collapse (handled, not an error).
- **Facts** (`domain/reports/story_facts.py`): reuses `facts.py`'s existing per-move/
  motif/theme extraction with `focus_color=None` — so both sides' moves are candidates,
  not just the profile's own (the findings-format report never shows the opponent's
  play at all) — plus new per-phase, per-side move-quality aggregate facts. `_move_facts`/
  `_positive_move_facts` gained a `side` field on their data (additive, harmless to the
  existing self-learner findings report) so the story prompt can unambiguously say
  "White's ..." / "Black's ..." for either side.
- **`GameReport.report_type`** (new column, migration `b7c1a04ab97c`): "findings"
  (default, existing) vs. "story" (new) — the same `(game_id, persona)` pair now holds
  two independent report *shapes* without colliding; `get_latest_report` takes
  `report_type` as part of its lookup key.
- **Prompt + critic** (`story_prompts.py`, `critic.py`): reuses the exact `{summary,
  findings[{fact_ids, text, kind}], recommendations}` JSON contract D-036 established,
  with a new `kind` vocabulary (`opening`/`middlegame`/`endgame`/`lesson` instead of
  `strength`/`mistake`). `critic.py`'s `validate_report` gained a third `report_kind`
  value (`"story"`), generalized to hold a `kind` vocabulary per report kind rather than
  one hardcoded set. Same no-engine-numbers/no-second-person rules as the findings
  report. Word budget: 500 (vs. 250 for the compact findings report) — a fuller story,
  still not an essay, my own judgment call, flagged here per the "lighter touch"
  agreement rather than asked about separately.
- **Fallback** (`story_fallback.py`): one deterministic finding per phase fact plus up
  to 2 "lesson" findings from the player's own mistake-tier moves — a safe minimum, not
  as narratively rich as the LLM path.
- **Service/route**: `ReportService.get_or_generate_story` (same class, same
  budget/critic/retry machinery as `get_or_generate`, new methods) and
  `GET /reports/games/{id}/story` (no `persona` query param — self-learner only).
- **Frontend**: new "Story" tab in the workspace's content panel, `StoryView` rendering
  four named sections (Opening/Middlegame/Endgame/Lessons) as visually distinct cards —
  not model-authored markdown headers, the same reasoning D-036 used for its own
  section grouping.

## A design flaw caught before it was implemented, not after

The recommended "What Went Well" criterion from D-036 (`BEST` + `is_critical_moment`)
was already known, from that phase's own report, to essentially never fire on real data.
Rather than reuse it for anything phase-related here, phase segmentation was built on the
sibling app's own material/ply heuristic instead, verified directly against real
analysis data before calling this phase done (see "Live verification").

## Files created or changed

**Backend**

```
backend/app/domain/reports/game_phases.py       new
backend/app/domain/reports/story_facts.py       new
backend/app/domain/reports/story_prompts.py     new
backend/app/domain/reports/story_fallback.py    new
backend/app/domain/reports/facts.py             +side on move/positive-move fact data, +"phase" FactKind
backend/app/domain/reports/critic.py            report_kind gains "story"; kind-vocabulary generalized
backend/app/domain/reports/service.py           +get_or_generate_story, +_generate_story_content
backend/app/db/models/reports.py                GameReport +report_type
backend/app/domain/reports/queries.py           get_latest_report +report_type param
backend/app/core/config/groups.py               +report_story_max_findings
backend/.env.example                            +REPORT_STORY_MAX_FINDINGS
backend/app/api/routes/reports.py               +GET /reports/games/{id}/story
backend/alembic/versions/..._report_type_discriminator_on_game_reports.py   new migration
backend/tests/test_reports_game_phases.py       new
backend/tests/test_reports_story_facts.py       new
backend/tests/test_reports_story_prompts.py     new
backend/tests/test_reports_story_fallback.py    new
backend/tests/test_reports_story_service.py     new
backend/tests/test_reports_routes.py            +TestGetGameStory
```

**Frontend**

```
frontend/src/features/reports/api/reports.ts               +fetchGameStory, widened kind enum
frontend/src/features/reports/hooks/useReports.ts           +useGameStory
frontend/src/features/reports/components/StoryView.tsx      new
frontend/src/features/reports/components/StoryView.test.tsx new
frontend/src/features/reports/index.ts                      +StoryView, useGameStory exports
frontend/src/features/workspace/components/StoryTab.tsx     new
frontend/src/features/workspace/components/ContentPanel.tsx +Story tab
frontend/src/features/workspace/components/ContentPanel.test.tsx  updated for 5 tabs
```

**Docs**

```
final_docs/v2/changes/0001-reuse-ledger.md                  +opening/endgame ply heuristic row
final_docs/v2/phase-reports/phase-16b-full-game-story.md    this file
```

## Tests

- Backend: 853 passed (full suite, `uv run pytest -q`) — 826 before this phase, +27 new
  (24 story, 3 PGN-endpoint), no regressions. `ruff check`, `ruff format --check`,
  `mypy` all clean.
- Frontend: 112 passed (full suite) — 107 before this phase, +5 new
  (`StoryView.test.tsx`, the updated `ContentPanel.test.tsx`, and two `Prose` inline-mode
  regression tests from the follow-ups). `npm run build` (`tsc -b` + Vite), `oxlint`,
  `prettier --check` all clean. Same pre-existing >500kB bundle-size warning as Phase
  16a, unrelated and unaddressed here.

## Live verification

Backend-direct against the real dev database and a real `gpt-4o-mini` call (not fixtures
alone) — a real seeded game with a blunder and a landed motif, run through the actual
`ReportService.get_or_generate_story`:

- `source: "llm"`, zero critic violations.
- Correctly named both "White" and "Black" throughout, no "you"/"your".
- Opening section named the real opening and cited real early-game facts.
- Middlegame section covered tactics/blunders for both sides.
- Endgame section correctly grounded against real theme facts for that phase.
- Lesson section tied a concrete takeaway to a real named mistake.

Not repeated this round: a fresh full browser pass (Phase 16a's browser session already
covered the workspace shell; this phase's frontend change — one new tab, one new view
component — is covered by its own component tests plus the backend/LLM verification
above, consistent with the agreed lighter-touch process).

## Follow-ups folded in during the owner's live review (same branch, pre-check-in)

The owner exercised the new tab and the surrounding workspace immediately, which
produced one real bug fix and four small UX changes, all kept on this branch since it
was not yet checked in:

1. **Story tab showed Overview (bug).** `WorkspaceShell.tsx` keeps its own URL-param tab
   whitelist separate from `ContentPanel`'s tab list; "story" was added to one but not
   the other, so the shell silently fell back to Overview. Fixed; the PGN tab below was
   added to both on the first pass as a result.
2. **Findings as bullets, not bordered rows** (`ReportView`) — and fixing that exposed a
   real latent bug: `Prose` always wrapped text in a block-level `<p>`, so bullet text
   broke onto its own line under the marker. Fixed at the source with a `Prose inline`
   mode (dropping the paragraph wrapper), which also fixed the same latent break in the
   Strategy/Recommendations/Next Steps lists and `TrainingPlanView`.
3. **Moves tab re-laid out as a two-column score sheet** — one row per full move,
   White's ply left / Black's right, with a header naming each player and color; the
   repeated `1.` / `1…` numbering of the flat list read as duplication. The raw-UCI
   `best:` column was dropped in the redesign…
4. **…and then reinstated properly**: mistake-tier moves (inaccuracy/mistake/blunder)
   now show `best: <SAN>` in readable notation. That required surfacing the stored
   `best_move_san` (D-036's column) on the moves payload — additive field on
   `MoveEvaluationSummary` + the route + the frontend schema.
5. **New PGN tab**: the raw PGN exactly as imported, read-only textarea with a copy
   button. New `GET /games/{id}/pgn` endpoint serving the stored blob as plain text
   (with a distinct 404 for a row whose blob is missing), a `getText` method on the
   frontend API client, and a `useGamePgn` hook.

## Known gaps

- **Coach/kid have no story tab equivalent** — deliberately out of scope per the owner's
  scope decision.
- **Chat's "review my game" opening message doesn't use this format** — same as D-036,
  intentionally not extended to chat.
- **No fresh browser E2E pass this round** — see "Live verification" above.
- **500-word budget for the story is my own judgment call**, not something the owner
  was asked about directly — flagged here per the lighter-touch agreement.

## Recommendation

Ready for sign-off. Both backend (850) and frontend (110) suites are clean, the feature
was verified against real data and a real LLM call end-to-end (not just fixtures), and
the one design risk this size of feature tends to carry (an unvalidated heuristic) was
addressed by reusing the sibling app's own verified thresholds rather than inventing a
new one, per the research step done before writing any code.
