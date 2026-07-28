"""Chunking policy (Phase 7): heading-based for authored markdown, token-window for
unstructured text (the vendored FIDE PDF). See `chunking.py`'s module docstring for why
these are the only two chunkers this corpus needs.
"""

from __future__ import annotations

import pytest

from app.domain.knowledge.chunking import chunk_by_tokens, chunk_markdown_by_heading, count_tokens

_BODY = """## The Pin
A pin immobilises an enemy piece.

## The Fork
A fork attacks two pieces at once.

## The Skewer
A skewer forces a valuable piece to move.
"""


class TestChunkMarkdownByHeading:
    def test_splits_one_chunk_per_heading(self) -> None:
        chunks = chunk_markdown_by_heading(_BODY)

        assert [chunk.metadata["heading"] for chunk in chunks] == [
            "The Pin",
            "The Fork",
            "The Skewer",
        ]

    def test_each_chunk_contains_its_own_heading_and_body_only(self) -> None:
        chunks = chunk_markdown_by_heading(_BODY)

        assert chunks[0].content == "## The Pin\nA pin immobilises an enemy piece."
        assert "Fork" not in chunks[0].content

    def test_token_count_is_populated(self) -> None:
        chunks = chunk_markdown_by_heading(_BODY)

        assert all(chunk.token_count > 0 for chunk in chunks)
        assert chunks[0].token_count == count_tokens(chunks[0].content)

    def test_no_heading_raises(self) -> None:
        with pytest.raises(ValueError, match="No '##' headings"):
            chunk_markdown_by_heading("Just a paragraph with no heading at all.")


class TestChunkByTokens:
    def test_short_text_is_a_single_chunk(self) -> None:
        chunks = chunk_by_tokens("a short sentence", chunk_size_tokens=100, chunk_overlap_tokens=10)

        assert len(chunks) == 1
        assert chunks[0].content == "a short sentence"

    def test_long_text_is_split_into_overlapping_windows(self) -> None:
        text = " ".join(f"word{i}" for i in range(50))

        chunks = chunk_by_tokens(text, chunk_size_tokens=20, chunk_overlap_tokens=5)

        assert len(chunks) > 1
        # Every chunk holds exactly chunk_size_tokens (the last one may be shorter, if
        # the text runs out) and the full text is covered end to end.
        assert all(chunk.token_count == 20 for chunk in chunks[:-1])
        assert "word0" in chunks[0].content
        assert "word49" in chunks[-1].content
        # Consecutive windows overlap: content near the end of one chunk reappears near
        # the start of the next — token windows don't land on word boundaries, so this
        # checks for the shared word itself rather than an exact string prefix/suffix.
        assert "word9" in chunks[0].content
        assert "word9" in chunks[1].content

    def test_empty_text_produces_no_chunks(self) -> None:
        assert chunk_by_tokens("", chunk_size_tokens=100, chunk_overlap_tokens=10) == []

    def test_overlap_must_be_smaller_than_chunk_size(self) -> None:
        with pytest.raises(ValueError, match="overlap"):
            chunk_by_tokens("text", chunk_size_tokens=10, chunk_overlap_tokens=10)
