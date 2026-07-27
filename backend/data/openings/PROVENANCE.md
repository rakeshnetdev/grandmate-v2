# Provenance — Lichess Openings Dataset

- **Source**: https://github.com/lichess-org/chess-openings
- **Commit**: `51b886249b9e418498d25b6e39b926c3de99c29a`
- **Retrieved**: 2026-07-26
- **Licence**: CC0 1.0 Universal (public domain dedication) — see `COPYING.txt`
- **Retrieved/reviewed by**: GrandMate project owner, via Claude Code (Phase 6)
- **Decision record**: D-011, ADR-0009

## What is vendored

- `source/{a,b,c,d,e}.tsv` — the upstream source files, one per ECO volume, unmodified.
  Three columns: `eco`, `name`, `pgn`.
- `gen.py` — the upstream `bin/gen.py` build script, unmodified. Requires only
  `python-chess`, already a project dependency (`pyproject.toml`).
- `dist/{a,b,c,d,e}.tsv` — generated output, one per ECO volume, matching the upstream
  `Makefile`'s per-file `dist/%.tsv` target. Five columns: `eco`, `name`, `pgn`, `uci`,
  `epd`. Kept for reference/debugging by volume.
- `dist/all.tsv` — **the file `domain/patterns` actually loads.** Matches the upstream
  `Makefile`'s `dist/all.tsv` target: all five source files run through `gen.py` in a
  single invocation. This matters beyond convenience — `gen.py`'s own duplicate-EPD check
  (`by_epd`) is scoped to one invocation, so building the five per-volume files
  separately would *not* catch an opening EPD that happens to collide across two ECO
  volumes. Running all five together in one `gen.py` call is what makes that guarantee
  real, and is why the loader reads this file specifically rather than the five above.

## How `dist/` was generated

The upstream repository does not publish `dist/` at a stable URL — it is produced by the
repository's own `Makefile` from the `source/` files. Reproduced locally with the
project's existing `python-chess` dependency, no upstream `pip install` needed:

```bash
cd backend
for f in a b c d e; do
  uv run python data/openings/gen.py "data/openings/source/$f.tsv" > "data/openings/dist/$f.tsv"
done
uv run python data/openings/gen.py data/openings/source/{a,b,c,d,e}.tsv > data/openings/dist/all.tsv
```

Both runs were clean: no errors, no duplicate-EPD warnings (within or across volumes), no
ordering warnings. `all.tsv` holds 3,807 uniquely-keyed openings.

## Re-vendoring later

Dataset updates are a manual re-vendor (ADR-0009's documented consequence, not an
automated sync): re-fetch `source/*.tsv` + `gen.py` from a newer commit, re-run the
command above, update the commit SHA and retrieval date in this file.
