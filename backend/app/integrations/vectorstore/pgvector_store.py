"""pgvector similarity search adapter (Phase 7).

Encapsulates the cosine-distance query pattern behind a small function-based interface,
rather than inlining raw pgvector comparator syntax into `domain/retrieval` — the same
"adapters behind interfaces" rule the engine (`app/integrations/engine`) and storage
(`app/integrations/storage`) adapters already follow. `domain/retrieval/dense.py` is the
only caller; persistence (insert/replace) stays in
`domain/knowledge/ingestion.py`, which already has the session open for the write it is
doing anyway — this module is read-only, similarity search only.

`search_analysis_chunks` takes `profile_id` as a required keyword argument, not an
optional filter, so that the isolation rule (`rag-architecture.md` section 5) is
enforced at the lowest layer that touches the table, not only by the caller's discipline.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalysisKnowledgeChunk, KnowledgeBucket, KnowledgeChunk


async def search_knowledge_chunks(
    session: AsyncSession,
    *,
    bucket: KnowledgeBucket,
    query_embedding: list[float],
    top_k: int,
) -> list[tuple[KnowledgeChunk, float]]:
    """The `top_k` chunks in `bucket` nearest `query_embedding`.

    Returns `(chunk, distance)` pairs — pgvector's `<=>` cosine *distance*, where lower
    means closer, not a 0-1 similarity score. Callers that want a similarity-style score
    (e.g. for `RETRIEVAL_MIN_SCORE` filtering) convert it themselves (`1 - distance`),
    since which convention a given caller wants varies (fusion needs rank, not score).
    """
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(KnowledgeChunk, distance.label("distance"))
        .where(KnowledgeChunk.bucket == bucket)
        .order_by(distance)
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return [(row.KnowledgeChunk, row.distance) for row in result]


async def search_analysis_chunks(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int,
) -> list[tuple[AnalysisKnowledgeChunk, float]]:
    """The `top_k` `analysis`-bucket chunks belonging to `profile_id`, nearest
    `query_embedding`. `profile_id` is not optional — see the module docstring."""
    distance = AnalysisKnowledgeChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(AnalysisKnowledgeChunk, distance.label("distance"))
        .where(AnalysisKnowledgeChunk.profile_id == profile_id)
        .order_by(distance)
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return [(row.AnalysisKnowledgeChunk, row.distance) for row in result]


__all__ = ["search_analysis_chunks", "search_knowledge_chunks"]
