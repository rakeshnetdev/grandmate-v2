"""Hybrid retrieval (Phase 7): dense + sparse fused with RRF, the one implementation
every future caller (agent tool, MCP server, RAGAS harness) shares."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.db.models import KnowledgeBucket, KnowledgeChunk, KnowledgeDocument
from app.domain.retrieval.hybrid import hybrid_search
from tests.fake_embeddings import FakeEmbeddingProvider


async def _make_chunk(
    session: AsyncSession, bucket: KnowledgeBucket, content: str, embedder: FakeEmbeddingProvider
) -> None:
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
    (embedding,) = await embedder.embed([content])
    session.add(
        KnowledgeChunk(
            document_id=document.id,
            bucket=bucket,
            chunk_index=0,
            content=content,
            token_count=len(content.split()),
            chunk_metadata={},
            embedding=embedding,
        )
    )
    await session.flush()


class TestHybridSearch:
    async def test_a_chunk_found_by_both_dense_and_sparse_ranks_first(
        self, db_session: AsyncSession
    ) -> None:
        embedder = FakeEmbeddingProvider()
        # This chunk shares vocabulary with the query (helps dense) and contains the
        # exact query term (helps sparse) -- it should win both retrievers and rank
        # first after fusion.
        await _make_chunk(
            db_session,
            KnowledgeBucket.TACTICS,
            "A fork attacks two enemy pieces at once.",
            embedder,
        )
        await _make_chunk(
            db_session, KnowledgeBucket.TACTICS, "A pin immobilises a single enemy piece.", embedder
        )
        await _make_chunk(
            db_session, KnowledgeBucket.TACTICS, "A skewer forces a piece to move away.", embedder
        )

        results = await hybrid_search(
            db_session,
            bucket=KnowledgeBucket.TACTICS,
            query="what does a fork attack",
            embedding_provider=embedder,
            settings=RetrievalSettings(),
        )

        assert results[0].content.startswith("A fork")
        assert results[0].retrieved_by == "fused"

    async def test_empty_bucket_returns_no_results(self, db_session: AsyncSession) -> None:
        embedder = FakeEmbeddingProvider()

        results = await hybrid_search(
            db_session,
            bucket=KnowledgeBucket.RULES,
            query="anything",
            embedding_provider=embedder,
            settings=RetrievalSettings(),
        )

        assert results == []
