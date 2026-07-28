"""Corpus ingestion pipeline (Phase 7).

Loads curated documents from `RetrievalSettings.corpus_data_dir`, chunks them per
`chunking.py`'s policy, embeds every chunk, and persists `KnowledgeDocument`/
`KnowledgeChunk` rows.

Idempotent by `content_hash`: an unchanged document is a no-op on re-ingestion, and a
changed one replaces its previous chunks rather than accumulating stale ones alongside
fresh ones — same non-versioned "replace" philosophy `PatternDetectionService` uses for
`OpeningMatch`, not `GameAnalysis`'s append-only versioning. Corpus documents are pure
functions of their source file; there is no reason to keep old chunks around once the
source changes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.core.config.groups import BACKEND_ROOT
from app.db.models import KnowledgeBucket, KnowledgeChunk, KnowledgeDocument
from app.domain.knowledge.chunking import chunk_by_tokens, chunk_markdown_by_heading
from app.domain.knowledge.provenance import load_markdown_document, load_sidecar_provenance
from app.integrations.llm.base import EmbeddingProvider

# Sidecar/system files that live alongside real corpus sources but are never
# themselves ingested (see provenance.py's module docstring and data/corpus/PROVENANCE.md).
_SKIP_SUFFIXES = (".provenance",)


@dataclass(frozen=True)
class IngestedDocument:
    """One document's ingestion outcome, for the caller to summarise/log."""

    bucket: KnowledgeBucket
    title: str
    chunks_written: int
    skipped_unchanged: bool


class KnowledgeIngestionService:
    """Load -> chunk -> embed -> persist, per bucket directory."""

    def __init__(
        self,
        session: AsyncSession,
        settings: RetrievalSettings,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._session = session
        self._settings = settings
        self._embedding_provider = embedding_provider

    async def ingest_corpus(self) -> list[IngestedDocument]:
        """Ingest every recognised source file under every bucket directory.

        A bucket directory that does not exist yet is skipped rather than erroring —
        the corpus grows bucket by bucket, and an empty bucket is a legitimate,
        temporary state, not a configuration mistake.
        """
        corpus_dir = Path(self._settings.corpus_data_dir)
        if not corpus_dir.is_absolute():
            corpus_dir = BACKEND_ROOT / corpus_dir

        results: list[IngestedDocument] = []
        for bucket in KnowledgeBucket:
            bucket_dir = corpus_dir / bucket.value
            if not bucket_dir.is_dir():
                continue
            for source_path in sorted(bucket_dir.iterdir()):
                if not source_path.is_file() or source_path.suffix in _SKIP_SUFFIXES:
                    continue
                result = await self._ingest_one(bucket, source_path)
                if result is not None:
                    results.append(result)
        return results

    async def _ingest_one(
        self, bucket: KnowledgeBucket, source_path: Path
    ) -> IngestedDocument | None:
        suffix = source_path.suffix.lower()
        if suffix == ".md":
            provenance, body = load_markdown_document(source_path)
            content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            chunks = chunk_markdown_by_heading(body)
        elif suffix == ".pdf":
            provenance = load_sidecar_provenance(source_path)
            content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            chunks = chunk_by_tokens(
                _extract_pdf_text(source_path),
                chunk_size_tokens=self._settings.chunk_size_tokens,
                chunk_overlap_tokens=self._settings.chunk_overlap_tokens,
            )
        else:
            # Not a recognised corpus source type (e.g. a stray file) — nothing to do,
            # and not an error worth failing the whole ingestion run over.
            return None

        existing = await self._session.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.content_hash == content_hash)
        )
        if existing.scalar_one_or_none() is not None:
            return IngestedDocument(
                bucket=bucket, title=provenance.title, chunks_written=0, skipped_unchanged=True
            )

        # A prior version of this same logical document (same bucket + title, different
        # content) is replaced rather than left to accumulate stale chunks alongside it.
        stale = await self._session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.bucket == bucket, KnowledgeDocument.title == provenance.title
            )
        )
        stale_row = stale.scalar_one_or_none()
        if stale_row is not None:
            await self._session.delete(stale_row)
            await self._session.flush()

        document = KnowledgeDocument(
            bucket=bucket,
            title=provenance.title,
            source=provenance.source,
            source_url=provenance.source_url,
            licence=provenance.licence,
            retrieved_at=provenance.retrieved_at,
            content_hash=content_hash,
        )
        self._session.add(document)
        await self._session.flush()

        embeddings = await self._embedding_provider.embed([chunk.content for chunk in chunks])
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            self._session.add(
                KnowledgeChunk(
                    document_id=document.id,
                    bucket=bucket,
                    chunk_index=index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    chunk_metadata=chunk.metadata,
                    embedding=embedding,
                )
            )
        await self._session.flush()

        return IngestedDocument(
            bucket=bucket,
            title=provenance.title,
            chunks_written=len(chunks),
            skipped_unchanged=False,
        )


def _extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


__all__ = ["IngestedDocument", "KnowledgeIngestionService"]
