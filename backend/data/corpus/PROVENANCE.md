# Provenance — Knowledge Corpus (Phase 7)

Per-document provenance also lives as a small header (`Title`/`Source`/`Source-URL`/
`Licence`/`Retrieved`) at the top of each `.md` file, parsed and enforced by
`domain/knowledge/provenance.py` before ingestion — a document missing any of these
fields is rejected, not silently ingested. This file is the human-readable summary.

| Document | Bucket | Source | Licence | Retrieved |
|----------|--------|--------|---------|-----------|
| `rules/FIDE_Laws_of_Chess.pdf` | `rules` | FIDE (vendored from `grandmate/backend/data/corpus/rules/FIDE - LawsOfChess.pdf`) | **Unclear** — official FIDE rules text, no licence or attribution recorded in the source repository; used here for reference/educational purposes only, per an explicit owner decision to accept this risk rather than invent a licence. Flagged honestly, not silently. | 2026-07-27 |
| `rules/engine_and_evaluation_semantics.md` | `rules` | GrandMate original prose, cross-checked against GrandMate v1's `stockfish.md` | original | 2026-07-27 |
| `openings/opening_families.md` | `openings` | GrandMate original prose, ECO ranges cross-checked against the vendored `lichess-org/chess-openings` dataset (CC0, Phase 6) and GrandMate v1's `openings.tsv` | original | 2026-07-27 |
| `tactics/tactical_motifs.md` | `tactics` | GrandMate original prose, cross-checked against GrandMate v1's `tactics.md` | original | 2026-07-27 |
| `tactics/check_patterns.md` | `tactics` | GrandMate original prose (Phase 13a). Filed under `tactics`, not `strategy`, because named mating patterns are tactical motifs per rag-architecture.md's bucket table. | original | 2026-08-02 |
| `strategy/strategic_principles.md` | `strategy` | GrandMate original prose, informed by general chess strategic theory as commonly described in open-licence references | original (informed by CC BY-SA 4.0 general reference material; no text reproduced) | 2026-07-27 |

## Decisions honoured

- **`rules` bucket / FIDE PDF licence**: the owner explicitly chose to vendor the PDF
  as-is despite the unclear licence, rather than have Claude write an original rules
  summary or source an alternative. Recorded here rather than glossed over, per the
  provenance rule ("a document without provenance does not enter a bucket" — this one
  has provenance, it is simply honest that the licence field is unresolved).
- **`strategy` bucket sourcing**: no source existed anywhere in the reference app: the
  owner chose "source from an open-license reference" over hand-authoring from
  scratch. In practice this meant informing original prose from openly-available
  general chess theory (the kind of material found in, e.g., CC BY-SA encyclopaedic
  overviews) rather than reproducing or closely paraphrasing any single source —
  recorded above with the specific licence caveat.
- **Reuse of GrandMate v1 content** (`tactics.md`, `stockfish.md`, `openings.tsv`): the
  owner's answer was "validate against v1, then write original v2 content" — not a
  verbatim copy-paste reuse. Every document above cross-checked against the
  corresponding v1 file for factual accuracy, then was written independently. See
  `final_docs/v2/changes/phase-07-corpus.md` for the full reuse record per the
  Migration Rule.

## Re-authoring later

Corpus content is expected to grow well beyond this MVP-sized set (rule 12: retrieval
is a first-class capability, not a fixed snapshot). Each bucket's document is a plain
Markdown file with the header format above — adding a new document is: write the file
with a valid header, drop it in the right bucket directory, and re-run
`KnowledgeIngestionService` (idempotent by `content_hash`, so re-running after adding
one new file does not re-embed the unchanged ones).
