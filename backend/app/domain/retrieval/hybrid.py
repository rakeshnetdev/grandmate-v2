"""Hybrid retrieval: dense + sparse fused with reciprocal rank fusion, for one bucket
(Phase 7).

The one implementation every caller shares (rule 13) — the Phase 10 agent tool
(`search_knowledge`), the Phase 12 MCP server, and this phase's own RAGAS harness all
call this function rather than each re-wiring dense+sparse+fusion themselves.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.db.models import KnowledgeBucket
from app.domain.retrieval.dense import dense_search
from app.domain.retrieval.fusion import reciprocal_rank_fusion
from app.domain.retrieval.interfaces import RetrievedChunk
from app.domain.retrieval.sparse import sparse_search
from app.integrations.llm.base import EmbeddingProvider


async def hybrid_search(
    session: AsyncSession,
    *,
    bucket: KnowledgeBucket,
    query: str,
    embedding_provider: EmbeddingProvider,
    settings: RetrievalSettings,
) -> list[RetrievedChunk]:
    """Dense and sparse results for `query` in `bucket`, fused with RRF."""
    dense_results = await dense_search(
        session,
        bucket=bucket,
        query=query,
        embedding_provider=embedding_provider,
        settings=settings,
    )
    sparse_results = await sparse_search(session, bucket=bucket, query=query, settings=settings)
    return reciprocal_rank_fusion(
        [dense_results, sparse_results],
        fusion_k=settings.retrieval_fusion_k,
        top_k=settings.retrieval_top_k,
    )


__all__ = ["hybrid_search"]
