"""Golden retrieval dataset loading (Phase 7, `evaluation-strategy.md`).

Schema per line: `query`, `bucket` (`null` for a negative/out-of-corpus query),
`expected_headings` (a list of `KnowledgeChunk.chunk_metadata["heading"]` values — how a
positive case names its relevant chunk(s)), `expected_content_contains` (a substring
fallback for chunks with no heading metadata, e.g. the PDF-derived `rules` chunks),
`qtype` (`lexical` | `semantic` | `negative`), and `reviewed_by` (`null` until a human
spot-checks it — see the module docstring in `provenance.py` for the same
has-provenance-vs-is-reviewed distinction).

**Why headings/substrings, not chunk ids.** `KnowledgeChunk.id` is a UUID assigned at
ingestion time — regenerated every time the corpus is re-ingested from scratch. A golden
query that hardcoded ids would silently stop meaning anything the moment the corpus is
rebuilt. Headings and distinctive substrings are stable across re-ingestion as long as
the underlying corpus document itself doesn't change, which is the property a golden set
actually needs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GoldenQuery:
    query: str
    bucket: str | None
    expected_headings: list[str]
    expected_content_contains: str | None
    qtype: str
    reviewed_by: str | None

    @property
    def is_negative(self) -> bool:
        return self.qtype == "negative"


def load_golden_queries(path: Path) -> list[GoldenQuery]:
    queries = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            queries.append(
                GoldenQuery(
                    query=row["query"],
                    bucket=row.get("bucket"),
                    expected_headings=row.get("expected_headings", []),
                    expected_content_contains=row.get("expected_content_contains"),
                    qtype=row["qtype"],
                    reviewed_by=row.get("reviewed_by"),
                )
            )
    return queries


__all__ = ["GoldenQuery", "load_golden_queries"]
