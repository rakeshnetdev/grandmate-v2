"""Provenance parsing and validation (Phase 7): the ingestion rule from `claude.md` —
"a document without provenance does not enter a bucket" — enforced here, before any
chunking or embedding ever runs.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.domain.knowledge.provenance import (
    ProvenanceError,
    load_markdown_document,
    load_sidecar_provenance,
    parse_provenance,
)

_VALID_HEADER = """
Title: Test Document
Source: GrandMate original
Source-URL: https://example.com/source
Licence: original
Retrieved: 2026-07-27
"""


class TestParseProvenance:
    def test_parses_a_complete_header(self) -> None:
        provenance = parse_provenance(_VALID_HEADER, context="test")

        assert provenance.title == "Test Document"
        assert provenance.source == "GrandMate original"
        assert provenance.source_url == "https://example.com/source"
        assert provenance.licence == "original"
        assert provenance.retrieved_at == date(2026, 7, 27)

    def test_blank_source_url_is_allowed(self) -> None:
        header = _VALID_HEADER.replace("Source-URL: https://example.com/source", "Source-URL:")

        provenance = parse_provenance(header, context="test")

        assert provenance.source_url is None

    @pytest.mark.parametrize("missing_field", ["Title", "Source", "Licence", "Retrieved"])
    def test_missing_required_field_is_rejected(self, missing_field: str) -> None:
        lines = [line for line in _VALID_HEADER.splitlines() if not line.startswith(missing_field)]
        header = "\n".join(lines)

        with pytest.raises(ProvenanceError, match="missing required provenance field"):
            parse_provenance(header, context="test")

    def test_blank_required_field_is_rejected(self) -> None:
        header = _VALID_HEADER.replace("Licence: original", "Licence:")

        with pytest.raises(ProvenanceError, match="missing required provenance field"):
            parse_provenance(header, context="test")

    def test_malformed_date_is_rejected(self) -> None:
        header = _VALID_HEADER.replace("Retrieved: 2026-07-27", "Retrieved: not-a-date")

        with pytest.raises(ProvenanceError, match="ISO date"):
            parse_provenance(header, context="test")

    def test_malformed_line_is_rejected(self) -> None:
        header = _VALID_HEADER + "\nthis line has no colon"

        with pytest.raises(ProvenanceError, match="malformed header line"):
            parse_provenance(header, context="test")


class TestLoadMarkdownDocument:
    def test_splits_header_and_body(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        path.write_text(_VALID_HEADER + "===\n## Heading\nBody text.\n", encoding="utf-8")

        provenance, body = load_markdown_document(path)

        assert provenance.title == "Test Document"
        assert body == "## Heading\nBody text."

    def test_missing_separator_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        path.write_text(_VALID_HEADER + "\n## Heading\nBody text.\n", encoding="utf-8")

        with pytest.raises(ProvenanceError, match="separator"):
            load_markdown_document(path)


class TestLoadSidecarProvenance:
    def test_loads_a_sidecar_file(self, tmp_path: Path) -> None:
        source = tmp_path / "document.pdf"
        source.write_bytes(b"%PDF-fake")
        sidecar = tmp_path / "document.pdf.provenance"
        sidecar.write_text(_VALID_HEADER, encoding="utf-8")

        provenance = load_sidecar_provenance(source)

        assert provenance.title == "Test Document"

    def test_missing_sidecar_is_rejected(self, tmp_path: Path) -> None:
        source = tmp_path / "document.pdf"
        source.write_bytes(b"%PDF-fake")

        with pytest.raises(ProvenanceError, match="sidecar"):
            load_sidecar_provenance(source)
