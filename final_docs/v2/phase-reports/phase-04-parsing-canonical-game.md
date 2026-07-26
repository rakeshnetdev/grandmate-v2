# Phase 4 Report — Parsing and Canonical Game Object

**Date**: 2026-07-26
**Status**: Complete, pending sign-off

## Scope note

One implementation decision was proposed and confirmed with the owner before coding, and
one already-locked decision (D-009) was amended mid-phase at the owner's request:

- **Canonicalization trigger**: runs automatically, synchronously, in the same request as
  Phase 3's import — not as a separate `jobs` row. Same philosophy as Phase 3's D-018: no
  new infrastructure for MVP scale. A game is fully parsed (move list, FEN/EPD, focus
  side) by the time `POST /imports` returns.
- **D-009 amended**: the corpus was originally the full `grandmate/` collections (7,818 +
  2,775 = 10,594 games, 7.5MB). After seeing that committed, the owner asked for a smaller
  MVP fixture footprint. Trimmed to the first 75 games of each collection (150 total) plus
  the 8 curated edge cases — see `decisions-log.md` and the Corpus reduction section below
  for what was verified against the full set *before* trimming.

## Completed

| Deliverable | Status |
|-------------|--------|
| `game_moves` table: one row per ply, written only on successful canonicalization | ✅ |
| `games.canonicalized_at` / `games.parse_error`: Phase 3/4 boundary tracked explicitly | ✅ |
| Alembic migration, reversible (upgrade/downgrade/repeat tested) | ✅ |
| Full `python-chess` move replay: SAN, UCI, FEN before/after, EPD after, clock, per ply | ✅ |
| Structured canonicalization failure taxonomy (`UNPARSEABLE`, `REPLAY_ERROR`) | ✅ |
| Header-normalisation policy: `focus_color`/`opponent_name` resolved against linked platform usernames, never guessed | ✅ |
| Canonicalization wired into `ImportService`, same request as Phase 3 | ✅ |
| PGN corpus fixtures ported and trimmed (150 real games + 8 curated edge cases) | ✅ |
| Property tests: independent replay path cross-checked against the canonical one | ✅ |
| Two Phase 3 bugs found and fixed during this phase (see below) | ✅ |

## Files created or changed

**Backend**

```
backend/
  alembic/versions/..._canonical_game_moves.py   game_moves table, games columns
  app/
    db/models/
      games.py                    Game, GameColor, GameMove (Game moved from imports.py)
      imports.py                  trimmed to Job/JobKind/JobStatus only
    domain/games/
      parsing.py                  canonicalize_pgn: full replay, FEN/EPD, failure taxonomy
      normalization.py            resolve_focus: header-name matching policy
      service.py                  GameParsingService: fetch, replay, persist, resolve
    domain/imports/
      parsing.py                  +pgn_text on ParsedGame (bug fix, see below)
      service.py                  wires GameParsingService in after each game is stored
  tests/
    fixtures/pgn/                 Carlsen.pgn, Praggnanandhaa.pgn (75 each), edge_cases.pgn
    test_game_parsing.py          14 tests — replay, FEN/EPD, failure taxonomy
    test_game_normalization.py    6 tests — focus resolution policy
    test_game_replay_properties.py 3 property tests (100 examples each) — replay consistency
    test_corpus_canonicalization.py 3 tests — edge cases + 150-game corpus accuracy/timing
    test_game_service.py          6 tests — DB+storage integration, focus resolution end to end
    test_import_parsing.py        +2 tests — per-game pgn_text scoping (bug fix regression)
    test_import_service.py        +1 test — stored PGN content scoping (bug fix regression)
    test_migrations.py            +game_moves to EXPECTED_TABLES
  pyproject.toml                  +hypothesis (dev)
```

**Docs**: `data-model.md` (`games`/`game_moves` updated for Phase 4 columns),
`decisions-log.md` (D-009 amendment), `changes/0001-reuse-ledger.md` (corpus trim noted),
this report.

## Test results

```
218 passed (39 new: 32 Phase 4 dedicated + 4 layer-boundary + 3 Phase 3 bug-fix regressions)
  ruff check    All checks passed!
  ruff format   clean
  mypy (strict) Success: no issues found in 70 source files
```

`tests/test_layer_boundaries.py`'s parametrised check was empty and auto-skipped through
Phases 1–3 (no deterministic-core modules existed yet). It now runs for real against
`domain/games/*.py` — 4 cases, all passing: the core correctly imports nothing
LLM-related or from `orchestration`.

## Two bugs found and fixed during this phase

**1. `raw_pgn_path` stored the whole source file, not the game.** Phase 3's
`ImportService` wrote `source.text` (the entire uploaded file or paste, which may contain
several games) to storage under a key scoped to *one* game's content hash. A 3-game file
left all 3 `Game` rows pointing at storage blobs containing all 3 games, with no way to
tell which game was which — this would have silently broken canonicalization for any
multi-game upload. Found while designing this phase's storage-fetch step, before any code
ran against it. Fixed by adding `ParsedGame.pgn_text` (`str(game)`, python-chess's own
serializer, verified to round-trip) and storing that instead — each game's storage blob
now contains exactly that game. `tests/test_import_parsing.py` and
`tests/test_import_service.py` gained regression tests asserting no cross-contamination
between games in the same batch.

**2. `MissingGreenlet` when wiring canonicalization into the async import flow.**
Assigning `game.moves = [...]` to persist the replayed moves triggered SQLAlchemy to
lazy-load the relationship's existing collection first (to reconcile `delete-orphan`
cascade accounting) — a synchronous load the async session can't satisfy implicitly,
raising `MissingGreenlet`. Fixed by deleting stale rows and adding new ones directly via
the `game_id` foreign key (`delete(GameMove).where(...)` + `session.add_all(...)`),
sidestepping the relationship-collection write path entirely. This also made
re-canonicalization idempotent (covered by
`test_re_canonicalizing_replaces_stale_moves_without_a_conflict`).

## Corpus reduction (D-009 amendment)

Before trimming, the full 10,594-game corpus (`grandmate/`'s Carlsen + Praggnanandhaa
collections) was run once against `canonicalize_pgn` to establish real evaluation numbers:

```
Total games:        10,594
Failed:              1
Accuracy:            99.991%
Elapsed:              353.8s
Time per game:        ~33.4ms
```

The one failure (`Praggnanandhaa.pgn`, "Gibraltar Masters 2020", game index 558) is a
zero-move forfeit record — `Result "0-1"`, no moves. Phase 3's ingestion validation
(`NO_MOVES` rejection) would already reject this game before it ever reached
canonicalization, so in the real pipeline this corpus canonicalizes at **100%** of what
Phase 3 actually lets through.

After the owner asked for a smaller MVP footprint, the fixtures were trimmed to the first
75 games of each collection (150 total, ~106KB vs. 7.5MB) plus the 8 curated edge cases.
The full-corpus numbers above are recorded here rather than re-verified on every test run;
the 150-game set now canonicalizes at 100% in the default suite (`test_corpus_canonicalization.py`).

## Evaluation

| Criterion | Result |
|-----------|--------|
| Parsing accuracy rate against the corpus | 99.991% on the full 10,594-game corpus (pre-trim); 100% on the 150-game MVP set and the 8 curated edge cases |
| Failure taxonomy coverage | Both `UNPARSEABLE` and `REPLAY_ERROR` have dedicated tests. `REPLAY_ERROR` is genuinely defensive — unreachable through real PGN input, since python-chess validates every move before our replay loop ever sees it — verified reachable via a targeted monkeypatch (`test_replay_error_path_is_reachable`) rather than left as an unverified `except` clause |
| Time per game | ~33ms/game average (full corpus, pre-trim); performance-budget test asserts <150ms/game on the 150-game set to catch regressions |
| Replay consistency | 3 property tests (100 sampled examples each) cross-check `canonicalize_pgn`'s SAN-based replay against an independently driven UCI-based replay — FEN chains, gap-freedom, and EPD-is-a-FEN-prefix all verified to hold across every sampled real game |

Known limitation: accuracy is measured against *real, previously-played* games. It does
not (and cannot, from this corpus alone) characterize behaviour on adversarially malformed
input beyond what the 8 hand-authored edge cases cover — Phase 3's ingestion layer is the
actual first line of defense there, and this phase's failure taxonomy is the second.

## Decisions honoured

| Decision | How |
|----------|-----|
| D-009 (amended this phase) | Corpus reused and trimmed per the owner's explicit request; full-corpus numbers preserved here rather than discarded |
| Rule 8 (deterministic core separate from LLM layer) | `domain/games` now has real, passing layer-boundary checks for the first time |
| D-008 no hardcoded values | No new `.env` keys needed this phase; test-only constants (e.g. the 150ms/game budget) are assertion thresholds, not runtime behaviour |
| Rule 13 (one implementation per capability) | `GameParsingService` is the only canonicalization path — called from `ImportService`, not duplicated |

## Deviations from plan

1. **Canonicalization folds into the import request** rather than a separate `jobs` row —
   proposed and confirmed with the owner before coding (see Scope note).
2. **Corpus trimmed from 10,594 to 150 games** — the owner's explicit request mid-phase,
   amending D-009. Full-corpus evaluation numbers preserved in this report.

## Known gaps

| Gap | Resolution |
|-----|-----------|
| No route/UI to view a canonicalized game's moves yet | Out of Phase 4's scope per `project-plan.md`'s own module split (`imports` vs `games` as separate frontend features) — the owner raised this during Phase 3 sign-off and it was confirmed as expected, not a gap to close now |
| Header-normalisation matching is exact (case-insensitive), not fuzzy | Deliberate for MVP — see `normalization.py`'s docstring. A near-miss (e.g. a display-name variant) leaves the game unresolved rather than mismatched, which is the safer failure mode |
| `REPLAY_ERROR` has no real-world trigger found in the corpus | Expected, not a gap — python-chess's own parsing already guarantees move legality before our replay loop runs. Verified reachable via monkeypatch instead of treating it as untested dead code |
| Re-canonicalization is available (idempotent) but nothing currently calls it | No caller needed yet — every game is canonicalized once, at import time. Will matter once a future phase changes the canonicalization policy and needs to re-run it against existing games |

## Risks

| Risk | Status |
|------|--------|
| Synchronous full replay slowing large imports | Bounded the same way as Phase 3: `MAX_GAMES_PER_IMPORT` (default 60) caps a single request; ~33ms/game means a full 60-game batch adds under 2 seconds |
| Corpus trim hiding a rare failure mode the full set would catch | Mitigated: the full-corpus run happened before trimming and its one finding is documented; the 150-game sample plus 8 targeted edge cases still exercise the same code paths |
| R-12 schema/architecture tangle | Continues to be mitigated: `domain/games` has no import of `api/routes`; `domain/imports` importing `domain/games` is a deliberate, documented, one-directional dependency (imports needs games' capability, not the reverse) |

## Structure review

Largest new file is `app/db/models/games.py` at 125 lines (`Game`, `GameColor`,
`GameMove` — three related models sharing one migration boundary, matching the existing
`db/models/identity.py` pattern). `app/domain/imports/service.py` grew to 176 lines
wiring in canonicalization; still one cohesive responsibility (ingest one submission end
to end). No file is taking on multiple concerns; no refactor needed before sign-off.

## How to test this phase

**Full replay via the existing import endpoint** — same request as Phase 3, now returns a
fully canonicalized game:

```bash
curl -c cookies.txt -X POST localhost:7575/api/v1/auth/login \
  -d '{"provider":"lichess","username":"DrNykterstein"}' -H 'Content-Type: application/json'

curl -b cookies.txt -X POST localhost:7575/api/v1/imports \
  -F 'pgn_text=[Event "Test"]
[White "DrNykterstein"]
[Black "Hikaru"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0'
# -> 201, progress.imported == 1
```

Then inspect the game directly (no route exposes this yet — psql, matching the "no games
list view" known gap above):

```bash
docker compose exec postgres psql -U grandmate -d grandmate -c \
  "SELECT focus_color, opponent_name, canonicalized_at FROM games ORDER BY created_at DESC LIMIT 1;"
# -> focus_color=white, opponent_name=Hikaru, canonicalized_at set (matches DrNykterstein login above)

docker compose exec postgres psql -U grandmate -d grandmate -c \
  "SELECT ply, san, fen_after FROM game_moves WHERE game_id = (SELECT id FROM games ORDER BY created_at DESC LIMIT 1) ORDER BY ply;"
# -> 5 rows: e4, e5, Nf3, Nc6, Bb5, each with its FEN
```

**Corpus and property tests:**

```bash
cd backend
uv run pytest tests/test_game_parsing.py tests/test_game_normalization.py \
  tests/test_game_replay_properties.py tests/test_corpus_canonicalization.py \
  tests/test_game_service.py -v
# -> 32 passed
```

**Migration reversibility:**

```bash
uv run alembic upgrade head      # -> creates game_moves, adds games columns
uv run alembic downgrade -1      # -> drops cleanly
uv run alembic upgrade head      # -> re-creates with no "already exists" error
```

## Recommendation

**Ready for sign-off.** Canonical game objects are stable against both a curated
edge-case set and real played games, cross-verified via an independent replay path, with
two real Phase 3 bugs caught and fixed along the way. The corpus footprint now matches
the owner's MVP-scale preference while preserving the full-corpus evaluation numbers that
justify trusting the smaller set.

**Phase 5 preview** — engine analysis core: Stockfish UCI adapter, tiered analysis policy,
move classification. Reads the `game_moves` this phase produces; the `jobs` table's
generic design means Phase 5's analysis jobs reuse the same tracking shape without a new
table.
