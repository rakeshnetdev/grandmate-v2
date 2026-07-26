# ADR-0009 — Lichess Openings Dataset, Matched on EPD

- **Status**: Accepted
- **Date**: 2026-07-25
- **Phase**: 0, implemented in Phase 6
- **Deciders**: Project owner

## Context

Opening identification needs an authoritative dataset and a matching strategy.

The reference application shipped `backend/data/corpus/strategies/openings.tsv`: 65 rows,
hand-written, with columns `name`, `pgn`, `description`, `moves`. The owner's assessment
was that this data is not accurate enough, and asked for material curated from Lichess. The
owner also asked directly whether FEN or PGN is the right representation.

## Decision

**Source**: `lichess-org/chess-openings`, the generated `dist/` TSV files (`a.tsv` through
`e.tsv`, by ECO volume). Columns are `eco`, `name`, `pgn`, `uci`, and `epd`. Released under
a CC0 public domain dedication.

**Matching key**: **EPD**, not PGN and not full FEN.

Detection walks the played positions, looks each position's EPD up in an index built from
the dataset, and keeps the **deepest** match. The matched ply is stored alongside the ECO
code and opening name.

**The old descriptions are not discarded.** The prose from the reference TSV is genuinely
useful explanatory text, so it is folded into the `openings` corpus bucket as retrievable
knowledge — just not as identification data.

**Vendoring**: the dataset is vendored into the repository with its licence file and a
recorded retrieval date, rather than fetched at runtime.

## Rationale

On the source: 65 openings is not a usable dataset. The Lichess set is roughly two orders
of magnitude larger, community-maintained, ECO-coded, and CC0, which removes any licensing
question.

On the matching key, which is the more interesting part of the decision. EPD is a FEN
without the halfmove clock and fullmove number. That difference is exactly what opening
identification needs, because the same opening position can be reached by different move
orders and at different move numbers.

- **PGN prefix matching** fails on transpositions. A game that reaches the Nimzo-Indian by
  an unusual move order does not match the canonical PGN string, so the opening is missed.
- **Full FEN matching** fails too, because the move counters differ between a position
  reached on move 6 and the same position reached on move 8. The positions are identical;
  the FENs are not.
- **EPD matching** handles both. Position identity is position identity, regardless of the
  path taken to reach it.

Keeping the deepest match matters because openings nest: a position may match both a broad
family and a specific variation, and the specific one is more informative.

There is a practical benefit too — EPD lookup is a hash lookup per ply, which is far
cheaper than prefix-matching move text and correct in more cases.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Reference app's 65-row TSV | Far too small; not authoritative; owner rejected it |
| PGN prefix matching | Misses transpositions, the case that matters most |
| Full FEN as key | Move counters break equality for identical positions |
| Runtime fetch from the Lichess repo | Network dependency in analysis; breaks hermetic tests |
| A commercial opening database | Licensing cost and restrictions for no functional gain over CC0 data |

## Consequences

### Positive
- Comprehensive ECO coverage
- Transpositions handled correctly
- CC0 removes licensing risk
- Fast hash-based lookup
- Old prose descriptions still earn their keep in the corpus

### Negative
- The `dist/` files must be built from the repo or downloaded from a workflow artifact, so the vendoring step needs documenting
- The EPD index is a memory-resident structure that needs sizing
- Dataset updates are a manual re-vendor

### Follow-up required
- Phase 6: vendor `dist/` TSVs with licence and retrieval date; build the EPD index; test transposition handling explicitly
- Phase 7: fold the reference prose descriptions into the `openings` bucket with provenance

## References
- [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings) — CC0
- Decision D-011
