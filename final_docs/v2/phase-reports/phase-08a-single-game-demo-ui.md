# Phase 8a Report — Single-Game Demo UI

**Date**: 2026-07-27
**Status**: Complete, pending sign-off
**Branch**: `P8a-single-game-demo-ui` (from `main`, which already includes Phase 7)

## Why this checkpoint exists

Requested ahead of Phase 8 (Multi-Game Aggregation and Profile Analytics): before building
aggregate/trend views across many games, the owner wanted to actually see the pipeline
built in Phases 3–6 end to end in a browser — upload a PGN, watch it get analyzed, see the
result — and wanted a direct answer on whether Phase 7's RAG infrastructure plays any part
in that. It doesn't yet (see below). This checkpoint adds only the minimum needed to make
already-working backend data visible: a games-list route and a games/analysis feature on
the frontend. No new analysis logic, no LLM, no RAG wiring — those are explicitly out of
scope here and remain scheduled where the plan already puts them (Phase 9/10 for LLM
narrative, Phase 12/13 for MCP/agents consuming retrieval).

## Completed

| Deliverable | Status |
|-------------|--------|
| `GET /api/v1/games` — list the caller's own games, most recent first | ✅ |
| `GET /api/v1/games/{id}` — single game lookup, profile-scoped | ✅ |
| `domain/games/queries.py` — read-side lookups, same split as `domain/analysis/queries.py` | ✅ |
| `GameSummary` schema moved from `schemas/imports.py` to its own `schemas/games.py`, `canonicalized_at` added | ✅ |
| Frontend `games` feature: API client, hooks (list/detail/analysis-poll/patterns), `GamesList`, `GameAnalysisView` | ✅ |
| `/games` and `/games/:gameId` pages and routes, nav links from the header and home page | ✅ |
| Verified live end to end in a real browser: login → paste PGN → import → background Stockfish analysis → opening/motif/theme detection → rendered in the UI | ✅ |
| Found and fixed a real bug during that live check: move numbering was off by one ply (see Known gaps / fixes) | ✅ |

## Answer to the RAG question

Confirmed by direct code inspection before writing any code (see conversation): the
analysis shown in this UI is 100% deterministic — Stockfish evaluation, move
classification, opening name/ECO, tactical/strategic motif tags. Phase 7 built real RAG
infrastructure (5-bucket corpus, hybrid dense+sparse retrieval, RAGAS eval), but nothing
consumes it yet — no LLM completion provider exists (only embeddings), no LangGraph node
or MCP tool calls retrieval, and the profile-scoped `analysis` bucket isn't even
auto-populated after analysis runs. This checkpoint does not change any of that; it only
makes already-computed deterministic data visible.

## Files created or changed

**Backend**

```
backend/app/
  api/routes/games.py            new — GET /games, GET /games/{id}
  api/routes/__init__.py         +games router registered
  domain/games/queries.py        new — list_games, get_game
  domain/games/__init__.py       +exports
  schemas/games.py               new — GameSummary (moved from schemas/imports.py, +canonicalized_at)
  schemas/imports.py             -GameSummary (moved out)
backend/tests/
  test_games_routes.py           new — 7 tests: list (empty/scoped/ordering), get (found/404/cross-profile/unparsed)
```

**Frontend**

```
frontend/src/
  features/games/
    api/games.ts                  new — zod schemas + fetch functions for games/analysis/patterns
    hooks/useGames.ts              new — useGames, useGame, useGameAnalysis (polls until ready), useGamePatterns
    components/GamesList.tsx       new
    components/GamesList.test.tsx  new — 2 tests
    components/GameAnalysisView.tsx      new
    components/GameAnalysisView.test.tsx new — 3 tests: pending/ready/unparsed states
    index.ts                       new — public feature surface
  pages/GamesPage.tsx              new
  pages/GameDetailPage.tsx         new
  app/router/index.tsx             +/games, +/games/:gameId
  app/layouts/RootLayout.tsx       +Import/Games nav links
  pages/HomePage.tsx               +"Your games" card
```

## Tests

- Backend: `uv run pytest` — 474 passed (467 existing + 7 new), `mypy app` clean, `ruff check` clean.
- Frontend: `vitest run` — 42 passed (37 existing + 5 new), `tsc -b --noEmit` clean, `oxlint` clean, `prettier --check` clean.

## Live verification

Ran the real stack (existing dev Postgres via `docker compose`, real Stockfish binary,
backend on :7575, Vite dev server on :3535) and drove it with a headless Playwright
script: logged in as a real Lichess username, pasted a PGN on `/imports`, confirmed the
import job reached `Done`, opened `/games`, opened the new game's detail page, and
watched the UI go from "Analyzing…" to a full rendered result — 97.4% accuracy, 39 moves,
opening name (Ruy Lopez, C99), 7 tactical motifs, 6 strategic themes, and a full
move-by-move evaluation table with classification badges. Console had only the expected
transient 401 (pre-login "am I logged in" probe) and 404s (analysis polling before the
background job finished) — no unhandled errors.

That live check caught a real bug before sign-off: `moveLabel` assumed `ply` was
1-indexed with odd=White; `domain/games/parsing.py`'s `enumerate(game.mainline())` is
0-indexed with even=White, so every move was mislabeled by one ply and White/Black were
swapped. Fixed in `GameAnalysisView.tsx`, re-verified live and via the unit suite.

## Known gaps

- **No SAN move text.** The analysis endpoint returns ply, eval, classification, and
  best-move-in-UCI — not SAN (`Nf3`). Phase 4 deliberately left a canonical-moves route
  out of scope, and adding one wasn't part of this checkpoint's approved scope. Moves are
  labelled by move number + side (`12.` / `12…`) and best-move suggestions are shown in
  UCI (`e2e4`). Worth a small follow-up route if move notation matters before Phase 8.
- **Patterns endpoint has one indistinguishable state.** `GET /patterns/games/{id}`
  returns an empty-findings shape both when nothing has been detected yet and when
  detection genuinely found nothing — this view only fetches it once analysis is ready,
  so in practice it's always the latter for this checkpoint's flow, but the ambiguity is
  inherited from Phase 6, not introduced here.
- **No LLM narrative, no RAG.** By design — see "Answer to the RAG question" above.

## Recommendation

Ready for sign-off. Small, additive, fully tested, and live-verified against the real
stack rather than mocks — which is what surfaced the ply-indexing bug. On approval, real
Phase 8 (multi-game aggregation) proceeds on its own branch from `main`.
