"""Corpus chunking policy (Phase 7, rag-architecture.md section 2).

Two chunkers, not a token-size knob per bucket:

- `chunk_markdown_by_heading` splits on `##` headings. Every authored markdown document
  in this corpus is already written at the granularity rag-architecture.md's bucket
  table calls for — one motif per heading in `tactics`, one family per heading in
  `openings`, one theme per heading in `strategy`, one topic per heading in the rules
  bucket's original notes — so heading boundaries *are* the bucket-appropriate chunk
  boundaries. A separately-configured token target per bucket would not improve on
  content that is already sized correctly at the source.
- `chunk_by_tokens` is the fallback for genuinely unstructured text — only the vendored
  FIDE PDF uses it, since raw PDF-extracted text has no heading markers left to exploit
  once pypdf has flattened it to plain text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken

# cl100k_base is the encoding OpenAI's embedding models (including the configured
# text-embedding-3-small default) use — token counts here match what the embedding API
# itself will see, not an approximation.
_ENCODING = tiktoken.get_encoding("cl100k_base")

_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    """One chunk ready for embedding and persistence."""

    content: str
    token_count: int
    metadata: dict[str, object] = field(default_factory=dict)


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def chunk_markdown_by_heading(body: str) -> list[Chunk]:
    """Split a document body into one chunk per `##` heading section.

    Raises `ValueError` if no heading is found — every authored corpus document is
    expected to use them; a document with none is a content-authoring bug, not a case
    to silently fall back on.
    """
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        raise ValueError(
            "No '##' headings found — every markdown corpus document must use them as "
            "chunk boundaries (see data/corpus/PROVENANCE.md)."
        )

    chunks: list[Chunk] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section = body[start:end].strip()
        chunks.append(
            Chunk(
                content=section,
                token_count=count_tokens(section),
                metadata={"heading": match.group(1).strip()},
            )
        )
    return chunks


def chunk_by_tokens(text: str, *, chunk_size_tokens: int, chunk_overlap_tokens: int) -> list[Chunk]:
    """Sliding-window token chunking for unstructured text (the vendored FIDE PDF).

    `chunk_size_tokens`/`chunk_overlap_tokens` come from `RetrievalSettings` — the one
    place in this corpus where the global chunk-size configuration actually applies,
    since there is no heading structure to chunk by instead.
    """
    if chunk_overlap_tokens >= chunk_size_tokens:
        raise ValueError("chunk_overlap_tokens must be smaller than chunk_size_tokens")

    tokens = _ENCODING.encode(text)
    if not tokens:
        return []

    stride = chunk_size_tokens - chunk_overlap_tokens
    chunks: list[Chunk] = []
    start = 0
    while start < len(tokens):
        window = tokens[start : start + chunk_size_tokens]
        content = _ENCODING.decode(window).strip()
        if content:
            chunks.append(Chunk(content=content, token_count=len(window), metadata={}))
        start += stride
    return chunks


__all__ = ["Chunk", "chunk_by_tokens", "chunk_markdown_by_heading", "count_tokens"]
