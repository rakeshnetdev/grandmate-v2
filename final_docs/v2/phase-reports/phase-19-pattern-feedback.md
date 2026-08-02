# Phase 19 Report — Pattern Feedback

**Date**: 2026-08-01
**Status**: Complete, pending sign-off
**Branch**: `P19-pattern-feedback`

## Goal

A new "Pattern feedback" tab answering the three questions a player actually asks after
finishing a game, none of which the existing surfaces answered:

- What did I do **again** in this game?
- What did I **stop** doing?
- **How good** was this game, for me?

The existing Analysis and Story tabs describe one game in isolation; the analytics
dashboard describes profile-level trends over a window. Neither compares *this* game to
the history behind it, which is where the owner's own product priority — cross-game
self-patterns over opponent comparison — actually lands.

## Scope decisions (taken with the owner before implementation)

1. **A workspace tab**, not a browser tab. A standalone route would have cut against
   Phase 16a/D-035, which deliberately collapsed six pages into the one workspace shell.
2. **Baseline = the last N analyzed games, unfiltered** (N configurable, default 20).
   Same-colour and same-time-control slices are the obvious follow-up and are deliberately
   out of scope here — they sharpen the signal but halve or fragment the sample.
3. Two calls made by Claude and stated up front rather than asked: a minimum-history gate,
   and a streak requirement before any absence is called an improvement.

## Design

### The three claims, and what stops each from being a lie

- **Repeated** (`comparison.py`) — a weakness that counts against the player in this game
  *and* recurs across at least `GAME_FEEDBACK_REPEAT_MIN_OCCURRENCE_RATE` of the baseline.
  Recurrence is the whole point: a one-off is already covered by the per-game report, and
  calling it a pattern would misdescribe the player's history.
- **Improved** — a recurring weakness *absent* from this game. This is the claim most
  easily overstated, so absence alone is never called a fix. A single clean game carries
  `clear_streak: 1, sustained: false` and is rendered "not in this game"; only a run of
  `GAME_FEEDBACK_IMPROVEMENT_MIN_STREAK` earns "clear for N games running". The streak
  resets at the most recent relapse rather than averaging it away.
- **Verdict** — the player's own move quality as distance from their own recent mean. The
  panel never shows a bare number: every metric appears beside the player's own average and
  a band ("78.4% · vs 71.2% · Well above your usual"), because "78.4%" alone tells a player
  nothing. The prose beside it quotes no figures at all — see below.

### The prose explains; it does not restate

Raised by the owner on review of the first live output, which read: *"Your move accuracy
was 81.2%, significantly above your baseline mean of 62.7%. Additionally, your blunder rate
was 6.2%…"* — every figure in that sentence was already on screen in the table directly
above it, and the paragraph beneath it re-listed all eight repeats with their move numbers,
also already on screen.

The prompt now states plainly that the reader is looking at those numbers, forbids quoting
any figure (percentages, counts, move numbers), and caps the write-up at one verdict and
two repeats — "one well-explained habit beats five named". The deterministic fallback was
rewritten the same way and no longer emits a per-metric finding at all; its verdict cites
the metric facts without reproducing them. `test_game_feedback_fallback.py` asserts the
whole fallback payload contains no digit at all, which is a crude check but exactly the
right one.

Division of labour after the change: the deterministic panel carries every number, and the
generated prose carries only what a table cannot say.

### Regenerating

`?regenerate=true` on the route, and a "Regenerate" button in the tab header — the same
contract and the same mutation-not-refetch shape `/reports/profile/training` already uses,
so a press always spends an LLM call and a refocus or remount never can. The flag skips the
staleness check but **not** the minimum-baseline gate: a profile with too little history has
nothing to regenerate from, and the button must not be a way to talk the system into a
verdict it has already declined to make (tested).

`scripts/clear_reports.py` gained `--feedback` for the prompt-iteration workflow, which is
the case a user-facing "clear" would otherwise serve; a cleared report simply regenerates
on next view, so there is no separate clear action in the UI.

### Player-only metrics

`GameAnalysis.summary["accuracy"]` covers *both* sides' moves — correct for a neutral game
summary, wrong for "how did I do". The same published formula (share of best-or-good moves)
is re-applied to the player's own moves only, for the target and every baseline game
identically. These numbers therefore differ from the dashboard's by design.

### Zero-variance baselines

Found while writing tests, and worth recording because the first implementation got it
wrong. When every baseline game scores identically (common for a whole-number metric like
critical moments), a z-score is undefined — but the *direction* of a difference is still
certain. Reporting "in line" would hide a real difference; inventing a z-score would claim
a magnitude nothing supports. The band is reported at the minimum tier and `z_score` stays
`null`, so a reader inspecting the payload is never shown a statistic that was not
computed.

### Reuse, not duplication

- `analytics/loading.py` — `ProfileAnalyticsService._load_analyzed_games` was extracted so
  the analytics window and the feedback baseline share one definition of "analyzed", one
  retry-wins rule, and one recency ordering. Two loaders would have been two chances for a
  game to sit in the dashboard's window while being invisible to its own baseline.
- `metrics.player_weaknesses_in_game` — the "this was the player's own problem in this
  game" rule (polarity, the self-inflicted-motif mistake-or-worse check, per-game
  deduplication) extracted from `recurring_weaknesses` and now shared by both.
- `reports/critic.py` — one critic, a fourth `report_kind`. Per rule 13, not a second
  implementation.
- `GameReport(report_type="pattern_feedback")` — the existing column already used by the
  story report; no migration needed.

### The critic rule that matters

Pattern feedback's findings are cross-checked against the *kind* of fact they cite: a
finding tagged `improved` must cite an `improvement` fact, `repeated` must cite a `repeat`
fact. This structurally blocks the one hallucination that would genuinely harm a reader —
a model reading "this recurred again" and writing "you have fixed this".

### Cache staleness

A stored report is superseded by a new analysis version *or* by a change in baseline size.
A per-game report depends only on its own game; this one depends on the history behind it,
and importing older games backfills that history. "3 of your last 12" when the answer is
now "3 of your last 20" is stale in a way `analysis_version` cannot see.

## Files

**Backend (new)**: `domain/game_feedback/{__init__,baseline,comparison,facts,prompts,fallback,service}.py`,
`domain/analytics/loading.py`
**Backend (changed)**: `core/config/{groups,settings,__init__}.py`, `.env.example`,
`domain/analytics/{metrics,service}.py`, `domain/reports/{critic,facts}.py`,
`api/routes/reports.py`, `schemas/reports.py`, `scripts/clear_reports.py`
**Frontend (new)**: `features/game-feedback/` (api, hooks, lib, components),
`features/workspace/components/PatternFeedbackTab.tsx`
**Frontend (changed)**: `features/workspace/components/{ContentPanel,WorkspaceShell}.tsx`,
`features/reports/{index.ts,api/reports.ts}`
**Tooling**: `.claude/skills/run-grandmate/driver.mjs`
**Docs**: `configuration.md`, `decisions-log.md` (D-037), this report

## Route

`GET /api/v1/reports/games/{game_id}/pattern-feedback` — self-learner only, profile-scoped
via `ScopedProfileIdDep`. A thin baseline is **not** an error: it returns 200 with
`sufficient_baseline: false` and a null report. Only an unanalyzed game 404s, with the same
detail string the sibling routes use so the frontend's existing pending-vs-error
distinction applies unchanged.

## Tests

| Suite | Count | Covers |
|-------|-------|--------|
| `test_game_feedback_comparison.py` | 14 | Thin/unattributable baselines, repeat vs. one-off, polarity inheritance, streak logic incl. relapse reset, metric direction, zero-variance handling |
| `test_game_feedback_routes.py` | 6 | Thin baseline as a normal response, repeat reported once supported, pending-not-broken 404, cross-profile isolation, regenerate replaces the stored write-up, regenerate cannot bypass the baseline gate |
| `test_game_feedback_fallback.py` | 6 | Improvement wording (both tiers), no-figures-anywhere, repeat still reads as a habit, one verdict not one per metric, grounding by construction |
| `test_reports_critic.py` (extended) | +3 | Pattern-feedback kind vocabulary, and the improvement-from-a-repeat-fact rejection |
| `PatternFeedbackView.test.tsx` | 8 | Absence vs. sustained wording, sample size always shown, per-unit metric formatting, regenerate control absent without a handler and disabled in flight |
| `patternFeedback.test.ts` | 2 | Schema accepts a real backend response and the thin-baseline shape |

**Results**: backend `ruff`, `mypy` (221 files), and all affected suites (176) pass.
Frontend `tsc --noEmit`, `oxlint`, and the full vitest suite (32 files, 154 tests) pass.

## Live verification (against the real dev database and a real LLM call)

Run against `Arjun1820`'s profile — 59 analyzed games, so a full 20-game baseline. The
endpoint returned `source: "llm"`, `grounded: true`, zero critic violations. Three things
that only showed up here, not in any test:

1. **"Your blunder rate was 0.3704."** The metric fact carried the raw ratio, and the model
   quoted it verbatim. Metric facts now carry pre-formatted strings (`format_metric`) and
   the prompt is told to quote them exactly; the fallback reads the same strings, so the
   two paths cannot drift into different units. Re-verified: "37.0%".
2. **A repeat naming ten move numbers in one sentence.** Honest but unreadable. The fact
   now names at most three plus an `occurrences_in_game` count; the API response keeps the
   full list, and the UI lays it out as "move 3, 9, 10, 11 +6 more".
3. **The tab showed "could not load" against a backend answering 200.** The embedded report
   reuses the shared `gameReportSchema`, whose finding-`kind` enum did not list
   `repeated`/`improved`/`verdict` — zod rejected the entire response. Component tests
   could not catch this because they build objects directly rather than parsing, so
   `patternFeedback.test.ts` now parses a real captured response.

Also fixed: `.claude/skills/run-grandmate/driver.mjs`'s loading-state regex did not know
this tab's wait text, so the driver screenshotted a spinner and reported success. Not a
product bug, but it would have hidden finding 3 indefinitely.

Screenshot of the working tab is in the PR.

**Pre-existing failures, not from this phase**: the full backend suite shows flaky,
order-dependent failures in `test_devinsight_api.py` and
`test_import_analysis_dispatch_integration.py`. Verified by stashing this branch's changes
and re-running on clean `main`, which fails in the same modules (with a different subset
each run). Not investigated here.

## Known gaps

1. **No same-colour or same-time-control slicing.** A blitz game is compared against a
   baseline that may be mostly rapid. Deliberate scope decision (above); the obvious next
   increment.
2. **Baseline ignores how far back it reaches.** Twenty games could be a week or a year;
   there is no recency decay and no staleness cutoff.
3. **Theme weaknesses are included but untested end-to-end.** The comparison treats motifs
   and themes identically and the code path is shared, but every test fixture uses a
   motif.
4. **No RAGAS evaluation.** This report is grounded by the deterministic critic rather than
   by retrieval, so the existing retrieval harness does not apply to it directly. If the
   owner wants generated-prose quality scored here, that is its own increment.
5. **`overall_band` averages three measures equally.** Defensible and documented, but not
   validated against what players would themselves call a good game.

## Recommendation

Ready for sign-off. The deterministic layer is tested where it makes claims about a
person, the generated layer cannot outrun those claims structurally, and the honest
"not enough history yet" state is a first-class response rather than an error path.
