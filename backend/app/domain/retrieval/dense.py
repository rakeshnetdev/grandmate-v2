"""Dense (pgvector cosine) retrieval over a static corpus bucket (Phase 7)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.db.models import KnowledgeBucket
from app.domain.retrieval.interfaces import RetrievedChunk
from app.integrations.llm.base import EmbeddingProvider
from app.integrations.vectorstore import search_knowledge_chunks


async def dense_search(
    session: AsyncSession,
    *,
    bucket: KnowledgeBucket,
    query: str,
    embedding_provider: EmbeddingProvider,
    settings: RetrievalSettings,
) -> list[RetrievedChunk]:
    """The `settings.retrieval_top_k` chunks in `bucket` nearest `query`, by embedding."""
    (query_embedding,) = await embedding_provider.embed([query])
    rows = await search_knowledge_chunks(
        session, bucket=bucket, query_embedding=query_embedding, top_k=settings.retrieval_top_k
    )
    results = []
    for chunk, distance in rows:
        # pgvector's `<=>` is cosine *distance* (0 = identical); converting to a
        # similarity score here is what makes RETRIEVAL_MIN_SCORE's threshold and the
        # RRF fusion step's rank-based combination both work over a consistent
        # "higher is better" convention across dense and sparse results alike.
        score = 1.0 - distance
        if score < settings.retrieval_min_score:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                content=chunk.content,
                score=score,
                metadata=chunk.chunk_metadata,
                retrieved_by="dense",
            )
        )
    return results


__all__ = ["dense_search"]
