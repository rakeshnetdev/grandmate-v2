"""Corpus document provenance parsing and validation (Phase 7).

Enforces the ingestion rule from `claude.md`: "a document without provenance does not
enter a bucket." Every curated document (see `data/corpus/PROVENANCE.md`) carries a
small, plain-text header before its body:

```
Title: Tactical Motifs Reference
Source: GrandMate original prose
Source-URL:
Licence: original
Retrieved: 2026-07-27
===
## The Pin
...body...
```

A deliberately simple `Key: Value` format, not YAML or TOML — parsing four required
fields does not need a markup language, and one fewer dependency is one fewer thing to
get wrong. `Source-URL` may be blank (hand-authored notes have none); every other field
is required and non-blank, or the document is rejected before ingestion ever runs.

Non-markdown sources (the vendored FIDE PDF) carry the same header in a sidecar file —
`<filename>.provenance` — next to the source, since the header cannot live inside a PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

_REQUIRED_FIELDS = ("title", "source", "licence", "retrieved")
_HEADER_BODY_SEPARATOR = "==="


class ProvenanceError(ValueError):
    """Raised when a document's provenance header is missing, incomplete, or malformed."""


@dataclass(frozen=True)
class Provenance:
    """A document's recorded source, licence, and review state.

    `reviewed_by` is never parsed from the header — it starts `None` for every document
    ingested here and is only ever set later, directly in the database, once a human
    actually spot-checks the content (see `KnowledgeDocument.reviewed_by`'s docstring).
    A document cannot claim its own review.
    """

    title: str
    source: str
    source_url: str | None
    licence: str
    retrieved_at: date


def _parse_fields(header_text: str, *, context: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in header_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ProvenanceError(
                f"{context}: malformed header line (expected 'Key: Value'): {line!r}"
            )
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()
    return fields


def parse_provenance(header_text: str, *, context: str) -> Provenance:
    """Parse and validate a raw header block.

    `context` is only for error messages (typically the source file's path), so a
    rejected document points straight at the file that needs fixing.
    """
    fields = _parse_fields(header_text, context=context)

    missing = [name for name in _REQUIRED_FIELDS if not fields.get(name)]
    if missing:
        raise ProvenanceError(
            f"{context}: missing required provenance field(s): {', '.join(missing)}. "
            "No provenance, no ingestion — see data/corpus/PROVENANCE.md."
        )

    try:
        retrieved_at = date.fromisoformat(fields["retrieved"])
    except ValueError as exc:
        raise ProvenanceError(
            f"{context}: 'Retrieved' must be an ISO date (YYYY-MM-DD), got {fields['retrieved']!r}"
        ) from exc

    return Provenance(
        title=fields["title"],
        source=fields["source"],
        source_url=fields.get("source-url") or None,
        licence=fields["licence"],
        retrieved_at=retrieved_at,
    )


def load_markdown_document(path: Path) -> tuple[Provenance, str]:
    """Split a corpus `.md` file into its provenance header and body.

    The body is returned raw (un-chunked) — chunking policy is `chunking.py`'s concern,
    not this module's.
    """
    raw = path.read_text(encoding="utf-8")
    if _HEADER_BODY_SEPARATOR not in raw:
        raise ProvenanceError(
            f"{path}: no '{_HEADER_BODY_SEPARATOR}' header/body separator found — "
            "every corpus document needs a provenance header."
        )
    header_text, _, body = raw.partition(_HEADER_BODY_SEPARATOR)
    provenance = parse_provenance(header_text, context=str(path))
    return provenance, body.strip()


def load_sidecar_provenance(source_path: Path) -> Provenance:
    """Load provenance for a non-markdown source (e.g. the vendored FIDE PDF) from its
    `<filename>.provenance` sidecar file."""
    sidecar_path = source_path.with_name(source_path.name + ".provenance")
    if not sidecar_path.is_file():
        raise ProvenanceError(
            f"{source_path}: no sidecar provenance file found at {sidecar_path} — "
            "every corpus document needs a provenance header."
        )
    return parse_provenance(sidecar_path.read_text(encoding="utf-8"), context=str(sidecar_path))


__all__ = [
    "Provenance",
    "ProvenanceError",
    "load_markdown_document",
    "load_sidecar_provenance",
    "parse_provenance",
]
