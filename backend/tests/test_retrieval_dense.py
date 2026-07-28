"""Dense retrieval (Phase 7): pgvector cosine similarity over one bucket, using the
deterministic fake embedding provider so results are meaningful without a real API call.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.db.models import KnowledgeBucket, KnowledgeChunk, KnowledgeDocument
from app.domain.retrieval.dense import dense_search
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


class TestDenseSearch:
    async def test_returns_the_most_similar_chunk_first(self, db_session: AsyncSession) -> None:
        embedder = FakeEmbeddingProvider()
        await _make_chunk(
            db_session, KnowledgeBucket.TACTICS, "A pin immobilises an enemy piece.", embedder
        )
        await _make_chunk(
            db_session, KnowledgeBucket.TACTICS, "A fork attacks two pieces at once.", embedder
        )

        results = await dense_search(
            db_session,
            bucket=KnowledgeBucket.TACTICS,
            query="what is a pin in chess",
            embedding_provider=embedder,
            settings=RetrievalSettings(),
        )

        assert results[0].content.startswith("A pin")
        assert results[0].retrieved_by == "dense"

    async def test_only_returns_chunks_from_the_requested_bucket(
        self, db_session: AsyncSession
    ) -> None:
        embedder = FakeEmbeddingProvider()
        await _make_chunk(db_session, KnowledgeBucket.TACTICS, "A pin is a tactic.", embedder)
        await _make_chunk(db_session, KnowledgeBucket.STRATEGY, "A pin is a tactic too.", embedder)

        results = await dense_search(
            db_session,
            bucket=KnowledgeBucket.STRATEGY,
            query="pin",
            embedding_provider=embedder,
            settings=RetrievalSettings(),
        )

        assert len(results) == 1
        assert results[0].content == "A pin is a tactic too."

    async def test_retrieval_min_score_filters_out_dissimilar_chunks(
        self, db_session: AsyncSession
    ) -> None:
        embedder = FakeEmbeddingProvider()
        await _make_chunk(
            db_session, KnowledgeBucket.TACTICS, "identical matching query words here", embedder
        )
        await _make_chunk(
            db_session,
            KnowledgeBucket.TACTICS,
            "totally unrelated vocabulary about something else entirely",
            embedder,
        )

        results = await dense_search(
            db_session,
            bucket=KnowledgeBucket.TACTICS,
            query="identical matching query words here",
            embedding_provider=embedder,
            settings=RetrievalSettings(retrieval_min_score=0.5),
        )

        assert len(results) == 1
        assert results[0].content == "identical matching query words here"

    async def test_empty_bucket_returns_no_results(self, db_session: AsyncSession) -> None:
        embedder = FakeEmbeddingProvider()

        results = await dense_search(
            db_session,
            bucket=KnowledgeBucket.RULES,
            query="anything",
            embedding_provider=embedder,
            settings=RetrievalSettings(),
        )

        assert results == []
