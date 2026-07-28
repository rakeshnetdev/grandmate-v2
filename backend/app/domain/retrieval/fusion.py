"""Reciprocal rank fusion (Phase 7, rag-architecture.md section 3).

score(d) = sum over each retriever r of 1 / (RETRIEVAL_FUSION_K + rank_r(d))

Chosen over score normalisation because dense (cosine similarity) and sparse (BM25)
scores are not on comparable scales, and normalising them requires calibration that
drifts as the corpus grows. Rank-based fusion sidesteps that entirely — only each
retriever's *ordering* matters, not its score's magnitude.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from app.domain.retrieval.interfaces import RetrievedChunk


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievedChunk]],
    *,
    fusion_k: int,
    top_k: int,
) -> list[RetrievedChunk]:
    """Fuse several ranked result lists (e.g. dense and sparse) into one.

    A chunk that appears in more than one list accumulates a score contribution from
    each — the whole point of fusion is that a chunk both retrievers agree on outranks
    one only a single retriever found, without either retriever's raw score ever
    entering the calculation.
    """
    fused_scores: dict[uuid.UUID, float] = {}
    first_seen: dict[uuid.UUID, RetrievedChunk] = {}

    for results in result_lists:
        for rank, chunk in enumerate(results, start=1):
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + 1.0 / (
                fusion_k + rank
            )
            first_seen.setdefault(chunk.chunk_id, chunk)

    ranked_ids = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
    return [
        replace(first_seen[chunk_id], score=fused_score, retrieved_by="fused")
        for chunk_id, fused_score in ranked_ids[:top_k]
    ]


__all__ = ["reciprocal_rank_fusion"]
