"""`KnowledgeIngestionService` integration tests: real transactional `db_session`, a
temp corpus directory, and the fake embedding provider (no real network calls) — covers
persistence shape and, especially, idempotent re-ingestion by `content_hash`.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.domain.knowledge.ingestion import KnowledgeIngestionService
from tests.fake_embeddings import FakeEmbeddingProvider

_DOC_HEADER = (
    "Title: Doc\nSource: Test\nSource-URL:\nLicence: original\nRetrieved: 2026-07-27\n===\n"
)


def _write_doc(corpus_dir: Path, body: str) -> None:
    rules_dir = corpus_dir / "rules"
    rules_dir.mkdir(exist_ok=True)
    (rules_dir / "doc.md").write_text(_DOC_HEADER + body, encoding="utf-8")


def _settings(corpus_dir: Path) -> RetrievalSettings:
    return RetrievalSettings(corpus_data_dir=str(corpus_dir))


class TestIngestCorpus:
    async def test_ingests_documents_and_chunks(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _write_doc(tmp_path, "## Heading One\nBody one.\n\n## Heading Two\nBody two.\n")
        service = KnowledgeIngestionService(
            db_session, _settings(tmp_path), FakeEmbeddingProvider()
        )

        results = await service.ingest_corpus()

        assert len(results) == 1
        assert results[0].chunks_written == 2
        assert results[0].skipped_unchanged is False
        docs = (await db_session.execute(select(KnowledgeDocument))).scalars().all()
        assert len(docs) == 1
        assert docs[0].title == "Doc"
        chunks = (await db_session.execute(select(KnowledgeChunk))).scalars().all()
        assert len(chunks) == 2
        assert all(len(chunk.embedding) > 0 for chunk in chunks)

    async def test_reingesting_an_unchanged_corpus_is_a_noop(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _write_doc(tmp_path, "## Heading\nBody.\n")
        service = KnowledgeIngestionService(
            db_session, _settings(tmp_path), FakeEmbeddingProvider()
        )
        await service.ingest_corpus()

        results = await service.ingest_corpus()

        assert results[0].skipped_unchanged is True
        assert results[0].chunks_written == 0
        chunks = (await db_session.execute(select(KnowledgeChunk))).scalars().all()
        assert len(chunks) == 1

    async def test_a_changed_document_replaces_its_chunks_not_duplicates_them(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _write_doc(tmp_path, "## Heading\nOriginal body.\n")
        service = KnowledgeIngestionService(
            db_session, _settings(tmp_path), FakeEmbeddingProvider()
        )
        await service.ingest_corpus()

        _write_doc(tmp_path, "## Heading\nUpdated body.\n\n## Second\nNew section.\n")
        results = await service.ingest_corpus()

        assert results[0].skipped_unchanged is False
        assert results[0].chunks_written == 2
        docs = (await db_session.execute(select(KnowledgeDocument))).scalars().all()
        assert len(docs) == 1  # replaced, not duplicated
        chunks = (await db_session.execute(select(KnowledgeChunk))).scalars().all()
        assert len(chunks) == 2
        assert {chunk.content.splitlines()[0] for chunk in chunks} == {"## Heading", "## Second"}

    async def test_missing_bucket_directory_is_skipped_not_an_error(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        service = KnowledgeIngestionService(
            db_session, _settings(tmp_path), FakeEmbeddingProvider()
        )

        results = await service.ingest_corpus()

        assert results == []
