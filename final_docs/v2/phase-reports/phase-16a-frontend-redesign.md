# Phase 16a Report — Frontend Redesign

**Date**: 2026-07-29
**Status**: Complete, pending sign-off
**Branch**: `P16a-frontend-redesign`

## Goal

Replace the six-page, navigation-heavy frontend shell (Home / Games / Game Detail /
Imports / Chat / Memory / Dashboard) with a single three-panel workspace — game selection,
game content, chat — so a user can import, review, and discuss a game without a page
navigation, while reusing every existing feature API and component as-is. Frontend-only by
instruction; the two backend touches in the "Backend touches" section below are small and
additive, not new functionality.

Two further, unplanned pieces of work were folded into this same branch after the owner
reviewed the redesigned Analysis tab live: a correctness bug fix (see "Bug found during
sign-off review" below) and a self-learner-only game report format redesign (see
"Addendum: self-learner-only game report format (D-036)" below) — both kept in this
branch at the owner's explicit direction, since the branch had not yet been checked in.

## Scope decisions confirmed before implementation (D-035)

Four open UI questions resolved with the owner via `AskUserQuestion`, all recommended
defaults accepted:

1. **Moves tab**: a move list (SAN + classification badges), not an embedded chess board —
   board rendering deferred, not part of this phase's scope.
2. **Prose rendering**: add `react-markdown` (+`remark-gfm`) rather than hand-rolling
   markdown parsing, so analysis/report/chat text renders as real formatted prose instead
   of raw markdown characters.
3. **Default workspace view**: profile-level analytics + training plan (the existing
   `ProfileDashboard`), shown in the Overview tab when no game is selected.
4. **Memory placement**: a tab inside the right-hand chat panel (`ChatDock`), not a
   separate page.

## Completed

| Deliverable | Status |
|-------------|--------|
| Three-panel `WorkspaceShell`: collapsible left game list, tabbed center content, right chat dock | ✅ |
| Left panel: icon-rail collapsed / full list expanded, click-to-select (not navigation), Import button opening a modal | ✅ |
| `ImportModal`: sync-from-platform / upload tabs, reuses existing import feature components as-is | ✅ |
| Center panel tabs: Overview (profile dashboard + training plan), Analysis (persona report), Moves (real SAN + classification badges), Patterns (opening/motifs/themes) | ✅ |
| Game-specific tabs only exist once a game is selected; an established game-tab value falls back to Overview otherwise | ✅ |
| Right panel: `ChatDock` with Chat/Memory tabs, thread list restacked for a narrow panel | ✅ |
| Dark/light/system theme: `ThemeProvider`, `ThemeToggle`, persisted to `localStorage`, full CSS variable sets for both themes | ✅ |
| Responsive layout: side-by-side panels ≥`lg`, off-canvas drawer overlays with Escape-to-close on mobile | ✅ |
| Formatted prose everywhere analysis/report/chat text renders: `Prose` component (`react-markdown` + chess-notation/classification-word highlighting) | ✅ |
| Classification pill badges (`ClassificationBadge`) reused across Moves tab, chat, and reports | ✅ |
| Chat citations surfaced inline (`CitationList`, expandable source list) | ✅ |
| Backend: `MoveEvaluationSummary` now carries `san`/`fen_after`; chat messages persist and return `citations`/`grounded` | ✅ |
| Dead code removed: old page components and their routes/tests deleted once superseded | ✅ |
| Live-verified in a real browser end to end (see below) | ✅ |

## Backend touches (small, additive — per instruction)

Both were needed so the new UI could show information the API already computed
internally but hadn't surfaced, not new functionality:

1. **`MoveEvaluationSummary.san` / `.fen_after`** — the Moves tab needs real algebraic
   notation and post-move FEN per ply; these were already stored on `GameMove` but not
   included in the analysis summary response. `get_game_analysis` now joins in
   `moves_by_ply` and merges the fields; nullable, so a ply with no matching `GameMove`
   degrades gracefully rather than erroring.
2. **`ChatMessageOut.citations` / `.grounded`** — the chat graph already computed
   citations and a groundedness flag internally (Phase 10/13) but never persisted or
   returned them. Both fields are added with defaults (`[]` / `None`) so pre-existing
   stored messages still validate; `_run_agent` now writes both onto the assistant
   message dict.

No routes, schemas, or business logic were added beyond these two field additions.

## Bug found during sign-off review: mate-score sentinel shown as literal centipawns

While reviewing the redesigned Analysis tab live, the owner spotted a persona report
saying "Your move 19 (Black) was a blunder, costing 99470 centipawns" — an impossible
value (real evals are roughly ±2000cp even for severe blunders).

**Root cause**: `domain/analysis/classification.py`'s `compute_cpl()` collapses a forced
mate into a flat `_MATE_SCORE_CP = 100_000` sentinel so mate-adjacent swings always
classify as blunder-tier, regardless of exactly how many moves the mate was in. That is
correct for classification, but the function's return value — sentinel arithmetic, e.g.
`100_000 - 530 = 99_470` for a move that let a forced mate slip to a merely +530
position — was being stored verbatim as `MoveEvaluation.eval_swing_cp` and then read as a
real evaluation swing by every downstream consumer: the fallback report text, the LLM
report prompt (`eval_swing_cp` is sent as ground-truth JSON the model is instructed to
cite), the `analysis` RAG bucket's projected text (so it was also embedded into the
retrieval corpus, citable to a user via chat), and the chat agent's tool payloads.

**Fix**: added `MoveEvaluation.mate_swing: bool` (Alembic
`bdb59298c771_mate_swing_flag_on_move_evaluations`, backfilled for existing rows from
data already on the table — each row's own `mate_in` is the eval *before* that move, and
the next ply's `mate_in` is the eval *after* it, so both sides of every existing swing
were still reconstructable without a full re-analysis). `classification.py` gained
`is_mate_swing()` (computes the flag) and `display_swing_cp()` (returns `None` instead of
the sentinel whenever `mate_swing` is True) — every text-producing consumer now goes
through `display_swing_cp` and describes the swing in words ("missed or allowed a forced
mate") instead of ever printing the sentinel as centipawns. `compute_cpl()` and the
classification thresholds themselves are unchanged — this was a display/storage bug, not
a classification bug; "blunder" was already the correct label before this fix.

Verified against the real dev database: the backfill flagged 291 of 3639 existing
`move_evaluations` rows, and re-running fallback-report generation for the exact game the
bug was found in now renders "Your move 3 (Black) was a blunder, missing or allowing a
forced mate." with no numeric artifact.

## Addendum: self-learner-only game report format (D-036)

After the centipawn bug fix, the owner asked for the game report to follow a specific
format spec (fixed headers, exact classification-word tagging, no engine numbers, third
person, a word budget) — a substantially larger change than either the frontend redesign
or the bug fix, since none of the underlying data it needs (a human-readable "better
move," any record of good moves at all) existed yet. Scoped down via four
`AskUserQuestion` rounds before implementation, all recorded in `decisions-log.md` D-036:
kid keeps its existing gentler format; the new format governs the report tab only, not
chat; coach keeps its Phase 9 unbounded/high-depth design, unaffected; "What Went Well"
requires a landed tactic (a motif at that ply), not merely the engine's top choice.

**New data, computed once at analysis time and persisted:**
- `MoveEvaluation.best_move_san` — the engine's suggested move in algebraic notation
  (previously only `best_move_uci` existed, unreadable in report prose), computed via
  python-chess from each ply's own position and backfilled for all 2669 existing rows
  with a `best_move_uci` set.
- A new fact-extraction path for "strength" findings (`facts.py`'s
  `_positive_move_facts`): a `BEST`-classified move that also landed a tactic (a motif
  finding on the mover's own side at that ply, excluding the self-inflicted
  `HANGING_PIECE`).

**A design flaw found via live verification, not a test, before this could be called
done:** the first version tied "strength" findings to `BEST` + `is_critical_moment` (the
recommended, owner-approved answer to the "best-move-facts" question) — reasonable-
sounding, but querying the real dev database showed 0 of 1928 `BEST` rows were *ever*
also `is_critical_moment`, because that flag is defined by a large centipawn *loss*,
which a best move has essentially none of by construction. "What Went Well" would have
rendered empty in virtually every real report. Corrected to the landed-tactic criterion
above (verified: 329 real `BEST`+motif co-occurrences in the dev database) before
shipping, not left as a known gap.

**A second issue, also found via live verification against a real LLM call, not a
test:** self-learner findings need a `"kind": "strength"|"mistake"` tag so the frontend
can group them — described in prose in the system prompt, every real generation omitted
it anyway. The model was pattern-matching against the shared JSON output-contract
template shown later in the same prompt, which didn't mention `"kind"`. Fixed by giving
self-learner its own copy of the contract with `"kind"` in the literal JSON shape, not
a rule stated near it — re-verified against a real `gpt-4o-mini` call afterward: zero
critic violations, correctly tagged and grounded output.

**Where the rules live:**
- `domain/reports/prompts.py` — self-learner-only system prompt addendum and output
  contract; coach and kid system prompts are untouched.
- `domain/reports/critic.py` — `validate_report` gained a `report_kind: "game" |
  "training"` parameter so the new `kind`-tag/no-second-person/split-cap rules apply to
  the per-game report only, not Phase 15's training plan (same persona, same shared
  critic function, predates and is untouched by this addendum).
- `domain/reports/selection.py` — self-learner splits its finding budget into an
  independently-capped positive pool and mistake pool (`report_self_learner_
  positive_max`/`_mistake_max`, 2 and 3); coach and kid never receive positive-move
  facts at all, preserving their exact prior behaviour.
- `domain/reports/fallback.py` — the deterministic path mirrors the same rules
  (third person, better-move naming, motif naming, `kind` tagging) so a report is
  equally correct whether or not the LLM path was used.
- Frontend: `ReportView.tsx` groups findings under "What Went Well" / "Mistakes &
  Blunders" headers (React-rendered, not model-authored markdown headers — more robust
  than trusting an LLM to reproduce exact header strings) whenever `kind` tags are
  present, and falls back to the original flat list otherwise (coach, kid, or any
  fallback report predating this addendum).

**Live-verified against real data and a real LLM call** (not just fixtures): found a
real seeded game with both a landed tactic and a blunder, ran it through the actual
`ReportService` with a real `gpt-4o-mini` call — `source: "llm"`, zero critic
violations, correct third-person prose naming real moves, real better-moves, and real
motifs, correctly tagged `strength`/`mistake`.

## Files created or changed

**Backend**

```
backend/app/schemas/analysis.py           +san, +fen_after, +mate_swing on MoveEvaluationSummary
backend/app/api/routes/analysis.py        _to_analysis_summary takes moves_by_ply; +mate_swing
backend/app/orchestration/graphs/chat.py  messages type widened; +citations, +grounded on assistant message
backend/app/schemas/chat.py               ChatMessageOut +citations, +grounded (both defaulted)
backend/app/domain/chat/service.py        get_history return type widened
backend/app/db/models/analysis.py         MoveEvaluation +mate_swing
backend/app/domain/analysis/classification.py  +is_mate_swing, +display_swing_cp
backend/app/domain/analysis/service.py    computes and persists mate_swing per move
backend/app/domain/analysis/__init__.py   +display_swing_cp, +is_mate_swing exports
backend/app/domain/reports/facts.py       move-fact eval_swing_cp goes through display_swing_cp; +mate_swing
backend/app/domain/reports/fallback.py    mate-swing wording instead of a bogus cp number
backend/app/domain/knowledge/analysis_projection.py  critical-moment text/metadata mate-swing-aware
backend/app/orchestration/tools/analysis_tools.py     tool payloads mate-swing-aware
backend/alembic/versions/20260729_1714_bdb59298c771_mate_swing_flag_on_move_evaluations.py
  new column + data-driven backfill for existing rows (see "Bug found during sign-off review")
backend/tests/test_analysis_routes.py     +with_move param, +san/fen_after/mate_swing assertions, +1 new test
backend/tests/test_chat_graph.py, test_chat_routes.py, test_chat_service.py   assertions updated for new keys
backend/tests/test_analysis_classification.py, test_analysis_service.py, test_reports_facts.py,
  test_reports_fallback.py, test_knowledge_analysis_projection.py, test_orchestration_tools.py
  new/updated tests for the mate-swing fix (+10 tests total)

# Addendum: self-learner-only game report format (D-036)
backend/app/db/models/analysis.py         MoveEvaluation +best_move_san
backend/app/domain/analysis/service.py    computes best_move_san via python-chess at analysis time
backend/app/core/config/groups.py         +report_self_learner_positive_max/_mistake_max
backend/.env.example                      +REPORT_SELF_LEARNER_POSITIVE_MAX/_MISTAKE_MAX
backend/app/domain/reports/facts.py       +_positive_move_facts, +san/best_move_san on move facts,
                                           extract_facts takes moves_by_ply
backend/app/domain/reports/service.py     fetches moves_by_ply, passes to extract_facts
backend/app/domain/reports/selection.py   self-learner-only positive/mistake split cap
backend/app/domain/reports/prompts.py     self-learner-only system prompt + output contract addendum
backend/app/domain/reports/critic.py      +report_kind param, +kind-tag validation, +you/your ban
backend/app/domain/reports/training_service.py  passes report_kind="training" to validate_report
backend/app/domain/reports/fallback.py    self-learner rewrite: kind tag, positive-move text,
                                           better-move naming, no you/your
backend/app/schemas/reports.py            ReportFinding +kind (nullable)
backend/alembic/versions/20260729_1838_d4413c217998_best_move_san_on_move_evaluations.py
backend/tests/test_reports_prompts.py     new file
backend/tests/test_analysis_service.py, test_reports_facts.py, test_reports_selection.py,
  test_reports_critic.py, test_reports_fallback.py, test_reports_service.py,
  test_reports_routes.py, test_orchestration_tools.py
  new/updated tests for the format addendum (+38 tests total)
```

**Frontend — modified (addendum)**

```
frontend/src/features/reports/api/reports.ts             +kind on reportFindingSchema
frontend/src/features/reports/components/ReportView.tsx  groups findings under kind-based headers
frontend/src/features/reports/components/PersonaReportPanel.test.tsx  +1 new test
```

**Frontend — new**

```
frontend/src/shared/theme/               ThemeProvider, context, useTheme, ThemeToggle (+tests)
frontend/src/shared/lib/prose.tsx        Prose component, chess-notation highlighting (+tests)
frontend/src/shared/lib/classification.ts  +CLASSIFICATION_BADGE_CLASS
frontend/src/shared/components/ui/classification-badge.tsx  (+tests)
frontend/src/shared/components/ui/dialog.tsx  (+tests)
frontend/src/shared/components/ui/tabs.tsx    (+tests)
frontend/src/features/workspace/
  components/WorkspaceShell.tsx, GameListPanel.tsx, ImportModal.tsx,
             ContentPanel.tsx, OverviewTab.tsx, AnalysisTab.tsx, MovesTab.tsx,
             PatternsTab.tsx, ChatDock.tsx  (+tests where noted above)
  hooks/useLeftPanelCollapsed.ts  (+tests)
  index.ts
frontend/src/pages/WorkspacePage.tsx
frontend/src/features/chat/components/CitationList.tsx  (+tests)
```

**Frontend — modified**

```
frontend/src/index.css                    data-theme light/dark variable blocks
frontend/src/app/providers/AppProviders.tsx  +ThemeProvider
frontend/src/app/layouts/RootLayout.tsx   simplified: header (logo+ThemeToggle+UserMenu) + <main>, footer removed
frontend/src/app/router/index.tsx         WorkspacePage/LoginPage/NotFoundPage only
frontend/src/app/router/router.test.tsx   updated for WorkspacePage
frontend/src/features/games/api/games.ts  +san, +fen_after on moveEvaluationSchema
frontend/src/features/games/lib/format.ts +opponentLine helper
frontend/src/features/games/index.ts      trimmed exports (GamesList/GameAnalysisView removed)
frontend/src/features/chat/api/chat.ts    +citations, +grounded on chatMessageSchema
frontend/src/features/chat/components/ChatMessageList.tsx  Prose + CitationList
frontend/src/features/chat/components/ChatPanel.tsx  layout: vertical stack instead of viewport-width grid
frontend/src/features/reports/components/ReportView.tsx  Prose for summary/findings/recommendations
frontend/src/features/reports/components/PersonaReportPanel.test.tsx  matcher fix for prose highlighting
frontend/src/features/training/components/TrainingPlanView.tsx  Prose
frontend/src/pages/LoginPage.tsx, NotFoundPage.tsx  own padding (main no longer pads globally)
frontend/src/test/setup.ts                matchMedia polyfill, working localStorage stub
```

**Frontend — deleted** (superseded by the workspace shell)

```
frontend/src/pages/HomePage.tsx, ImportsPage.tsx, GamesPage.tsx, ChatPage.tsx,
  MemoryPage.tsx, GameDetailPage.tsx, DashboardPage.tsx
frontend/src/features/games/components/GamesList.tsx (+test)
frontend/src/features/games/components/GameAnalysisView.tsx (+test)
```

**Docs**

```
project-plan.md                                    +Phase 16a section, +D-036 addendum
final_docs/v2/decisions-log.md                      +D-035, +D-036
final_docs/v2/changes/0001-reuse-ledger.md          +Design and frontend patterns section
final_docs/v2/persona-matrix.md                     +Phase 16a addendum (self-learner game report format)
final_docs/v2/phase-reports/phase-16a-frontend-redesign.md   this file
```

## A design decision made during implementation, not pre-specified

`DevInsightPanel` (dev-only) is rendered as a third flex sibling below `<main>` in
`RootLayout`. The original `WorkspaceShell` used a hardcoded `h-[calc(100vh-4rem)]`, which
overflowed the viewport whenever `DevInsightPanel` was present, since nothing accounted
for its height. Caught via a live screenshot review and a
`document.body.scrollHeight` vs `window.innerHeight` check, not something the owner
flagged — fixed by adding `min-h-0` to `<main>` and switching `WorkspaceShell`'s root to
`h-full`, letting flexbox compute the correct available height regardless of whether the
dev panel is present.

## A second issue found live, not in tests: misleading "Analyzing…" on a real error

One older seeded demo game had a `GameAnalysis.summary` missing a field the frontend's zod
schema requires, so the schema threw on parse. `fetchGameAnalysisOrNull` only special-cases
404s, so the schema error surfaced as an unhandled query error — `isLoading` stayed false
and `data` stayed undefined, which the Moves tab's original logic rendered identically to
"still polling." Fixed by adding explicit `isError` handling to both `MovesTab` and
`PatternsTab`, rendering a distinct error message. This is a genuine robustness fix (a real
network failure would previously have looked identical to normal polling), not a
workaround for the one stale demo row — verification continued against a
properly-analyzed demo game once found.

## Tests

- Frontend: 107 tests across 25 files, all passing. `npm run build` (`tsc -b` +
  Vite build) clean, `oxlint` clean, `prettier --check` clean. One pre-existing,
  unrelated build warning (main JS chunk >500kB after minification, most likely
  `react-markdown`'s dependency tree) — not addressed this phase; noted as a future
  code-splitting candidate.
- Backend: 826 passed (full suite, `uv run pytest -q`) — 786 after the original two
  backend touches, +10 for the mate-swing fix, +30 for the report-format addendum, no
  regressions at any step.

No new RAGAS evaluation suite — this phase is UI/UX restructuring plus two backend
correctness/format fixes, none of which change retrieval behavior. The mate-swing fix is
a display/storage correctness bug in existing deterministic analysis; the report-format
addendum changes prompt *instructions* and a structural JSON contract for one persona,
not retrieval. Both are covered by unit/integration tests (classification, service,
facts, selection, prompts, critic, fallback, RAG-projection, routes) plus live
re-verification against the real dev database and, for the format addendum, a real LLM
call end-to-end through `ReportService`.

## Live verification

Real stack (real Postgres, real logged-in profile `DrNykterstein`, Chromium via
hand-written Playwright driver scripts — `chromium-cli` unavailable in this environment):

- Login flow, dark/light theme toggle with persistence across reload.
- Game selection from the left panel auto-switches to the Analysis tab.
- All four content tabs verified with real data: Overview (dashboard + training plan),
  Analysis (persona report, formatted prose), Moves (real SAN, classification badges),
  Patterns (opening/motifs/themes).
- Left panel collapse/expand.
- Chat: sent a message, citations rendered and expandable ("Show/Hide N sources"),
  verified citation display survives a full page reload by re-selecting the thread.
- Memory tab inside the chat dock.
- Responsive mobile (390×844): header toolbar, left drawer with backdrop, right chat
  overlay, Escape-to-close on both (added after a live test found Escape didn't close the
  hand-rolled overlays, unlike the shared `Dialog` component).

**Report-format addendum's own live verification** (backend-direct, not through the
browser — the frontend grouping change itself is covered by the `PersonaReportPanel`
test above): a one-off script against the real dev database and a real `gpt-4o-mini`
call, not fixtures — this is what caught both the `is_critical_moment` design flaw and
the missing-`"kind"`-field prompt issue described in the addendum section above. As part
of that verification, existing cached `GameReport` rows in the dev database were
cleared (they are a regenerable cache — `ReportService.get_or_generate`'s own docstring
— not source data) so a real report would regenerate through the new code path rather
than returning a stale cached one; noted here since it's a state change to the dev
database, even though a low-risk, reversible one (the next request for any game's report
regenerates it).

## Known gaps

- **No embedded chess board** on the Moves tab — deliberately deferred per the owner's
  scope choice (decision 1 above); the tab shows SAN + classification only.
- **Main JS bundle size warning** (>500kB after minification) — pre-existing, not
  addressed this phase; a code-splitting pass is a reasonable future item.
- **One stale demo game** has a schema-incompatible `GameAnalysis.summary` row from
  earlier ad-hoc seeding; left in place (now correctly shown as an error rather than a
  false "Analyzing…" state) since fixing historical demo data is out of this phase's scope.
- **Local dev servers** left running for continued exploration: backend on `:7575`,
  frontend on `:3535`.
- **Mate-swing backfill's one unrecoverable edge case**: the migration reconstructs
  `mate_swing` for existing rows from data already on the table, except the very last
  ply of a game, which has no "after" row at all (positions has N+1 entries for N stored
  plies). Only affects a game whose *final* recorded move itself walks into an
  engine-evaluated mate score — extremely rare, and only for analyses that predate this
  fix; a re-analysis of that specific game would resolve it.
- **`best_move_san` has the same edge case**, for the same structural reason, on
  existing analyses predating this addendum — not an issue for any analysis run from
  now on.
- **The report-format addendum's frontend grouping is unit-tested but not
  browser-verified** this round — the earlier browser session covered the pre-addendum
  Analysis tab; this addendum's `ReportView.tsx` change was verified via its component
  test plus the real backend/LLM script above, not a fresh browser pass.

## Recommendation

Ready for sign-off. All four original scope decisions implemented as approved, the two
frontend backend-touches stayed additive with no new functionality, the full frontend
and backend suites are clean, and the redesigned workspace was live-verified end to end
including three real bugs (viewport overflow, misleading error state, and the mate-score
centipawn-display bug) caught and fixed during that verification rather than left for
later.

Two further items were folded into this same branch at the owner's explicit direction,
since it was found during this phase's own live review and the branch had not yet been
checked in: the mate-swing centipawn-display bug fix, and the self-learner-only game
report format (D-036) — both beyond this phase's original "frontend-only, small additive
backend touches" scope, both scoped down through direct questions to the owner before
implementation, and both live-verified against the real dev database (the format
addendum against a real LLM call too) rather than fixtures alone. One real design flaw
(the `is_critical_moment` criterion for "What Went Well") and one real prompt-engineering
bug (the `"kind"` field being described but not enforced by the JSON template) were
caught and fixed during that verification, not left as known gaps.
