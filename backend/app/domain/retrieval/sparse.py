"""BM25 (Okapi) sparse retrieval over a static corpus bucket (Phase 7).

An in-memory index built fresh per query from persisted chunks — the simplest option
that is fully testable at MVP corpus scale, per `RetrievalSettings`' own documented
rationale. Swappable for a cached index or Postgres full-text search later if the
corpus outgrows rebuilding it on every call; Phase 7's own evaluation records whether
that trade is worth making yet (it isn't, at this corpus size).
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.db.models import KnowledgeBucket, KnowledgeChunk
from app.domain.retrieval.interfaces import RetrievedChunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


async def sparse_search(
    session: AsyncSession,
    *,
    bucket: KnowledgeBucket,
    query: str,
    settings: RetrievalSettings,
) -> list[RetrievedChunk]:
    """The `settings.retrieval_top_k` chunks in `bucket` with the highest BM25 score."""
    result = await session.execute(select(KnowledgeChunk).where(KnowledgeChunk.bucket == bucket))
    chunks = list(result.scalars().all())
    if not chunks:
        return []

    corpus = [_tokenize(chunk.content) for chunk in chunks]
    bm25 = BM25Okapi(corpus, k1=settings.retrieval_bm25_k1, b=settings.retrieval_bm25_b)
    scores = bm25.get_scores(_tokenize(query))

    ranked = sorted(zip(chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            content=chunk.content,
            score=float(score),
            metadata=chunk.chunk_metadata,
            retrieved_by="sparse",
        )
        for chunk, score in ranked[: settings.retrieval_top_k]
        # A zero score means no lexical overlap at all — not "weakly relevant", not
        # worth returning. BM25's scale is corpus-relative and unbounded, unlike cosine
        # similarity, so RETRIEVAL_MIN_SCORE (tuned for the dense 0-1 scale) does not
        # apply here.
        if score > 0.0
    ]


__all__ = ["sparse_search"]
