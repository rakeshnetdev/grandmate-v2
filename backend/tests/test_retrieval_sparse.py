"""BM25 sparse retrieval (Phase 7): exact lexical matching, no embeddings involved."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.db.models import KnowledgeBucket, KnowledgeChunk, KnowledgeDocument
from app.domain.retrieval.sparse import sparse_search


async def _make_chunk(session: AsyncSession, bucket: KnowledgeBucket, content: str) -> None:
    document = KnowledgeDocument(
        bucket=bucket,
        title=content[:30],
        source="test",
        source_url=None,
        licence="original",
        retrieved_at=date(2026, 7, 27),
        content_hash=str(uuid.uuid4()),
    )
    session.add(document)
    await session.flush()
    session.add(
        KnowledgeChunk(
            document_id=document.id,
            bucket=bucket,
            chunk_index=0,
            content=content,
            token_count=len(content.split()),
            chunk_metadata={},
            # BM25 never touches this column — a zero vector is fine here.
            embedding=[0.0] * 1536,
        )
    )
    await session.flush()


class TestSparseSearch:
    async def test_exact_keyword_match_ranks_first(self, db_session: AsyncSession) -> None:
        # A third, unrelated filler chunk matters here: classic BM25's IDF is exactly
        # zero for a term appearing in precisely half of a corpus (log(1) == 0), which
        # a bare two-document "one has it, one doesn't" corpus hits exactly. Three
        # documents (one match, two non-matches) keeps the term's document frequency
        # away from that boundary, matching how a real, larger corpus behaves.
        await _make_chunk(db_session, KnowledgeBucket.OPENINGS, "The Sicilian Defence is sharp.")
        await _make_chunk(db_session, KnowledgeBucket.OPENINGS, "The French Defence is solid.")
        await _make_chunk(db_session, KnowledgeBucket.OPENINGS, "The Caro-Kann Defence is calm.")

        results = await sparse_search(
            db_session,
            bucket=KnowledgeBucket.OPENINGS,
            query="Sicilian",
            settings=RetrievalSettings(),
        )

        assert results[0].content.startswith("The Sicilian")
        assert results[0].retrieved_by == "sparse"

    async def test_no_lexical_overlap_returns_nothing(self, db_session: AsyncSession) -> None:
        await _make_chunk(db_session, KnowledgeBucket.OPENINGS, "The Sicilian Defence is sharp.")

        results = await sparse_search(
            db_session,
            bucket=KnowledgeBucket.OPENINGS,
            query="zzznonexistentword",
            settings=RetrievalSettings(),
        )

        assert results == []

    async def test_only_returns_chunks_from_the_requested_bucket(
        self, db_session: AsyncSession
    ) -> None:
        await _make_chunk(db_session, KnowledgeBucket.OPENINGS, "Sicilian in openings bucket.")
        await _make_chunk(db_session, KnowledgeBucket.STRATEGY, "Sicilian in strategy bucket.")
        # Same zero-IDF-at-50%-document-frequency reason as the test above: the
        # STRATEGY bucket needs the matching term at less than half its documents.
        await _make_chunk(db_session, KnowledgeBucket.STRATEGY, "Unrelated filler chunk text.")
        await _make_chunk(db_session, KnowledgeBucket.STRATEGY, "Another unrelated filler chunk.")

        results = await sparse_search(
            db_session,
            bucket=KnowledgeBucket.STRATEGY,
            query="Sicilian",
            settings=RetrievalSettings(),
        )

        assert len(results) == 1
        assert results[0].content == "Sicilian in strategy bucket."

    async def test_empty_bucket_returns_no_results(self, db_session: AsyncSession) -> None:
        results = await sparse_search(
            db_session, bucket=KnowledgeBucket.RULES, query="anything", settings=RetrievalSettings()
        )

        assert results == []
