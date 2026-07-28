"""Profile-scoped retrieval over the `analysis` bucket (Phase 7, rag-architecture.md
section 5).

`profile_id` is a required keyword argument on `search`, not an optional filter — the
whole isolation guarantee rests on there being no code path that can call this without
one. There is deliberately no way to search across every profile's analysis chunks at
once; a retrieval that crosses a profile boundary without an explicit permission grant
is a defect, not a feature (`claude.md` rule 14).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.domain.retrieval.interfaces import RetrievedChunk
from app.integrations.llm.base import EmbeddingProvider
from app.integrations.vectorstore import search_analysis_chunks


class AnalysisRetriever:
    """The only reader of `analysis_knowledge_chunks`."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        settings: RetrievalSettings,
    ) -> None:
        self._session = session
        self._embedding_provider = embedding_provider
        self._settings = settings

    async def search(self, query: str, *, profile_id: uuid.UUID) -> list[RetrievedChunk]:
        """The `settings.retrieval_top_k` of `profile_id`'s own analysis chunks nearest
        `query`, by embedding. Never returns another profile's chunks — `profile_id`
        filters at the query itself (`search_analysis_chunks`), not after the fact."""
        (query_embedding,) = await self._embedding_provider.embed([query])
        rows = await search_analysis_chunks(
            self._session,
            profile_id=profile_id,
            query_embedding=query_embedding,
            top_k=self._settings.retrieval_top_k,
        )
        results = []
        for chunk, distance in rows:
            score = 1.0 - distance
            if score < self._settings.retrieval_min_score:
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


__all__ = ["AnalysisRetriever"]
