"""Hybrid multi-bucket retrieval (Phase 7, rag-architecture.md).

`hybrid_search` is the shared entry point for the four static buckets; `AnalysisRetriever`
is the sole, profile-scoped entry point for the `analysis` bucket. `select_buckets` gives
non-agentic callers (and this phase's own evaluation harness) a default bucket set.
"""

from app.domain.retrieval.analysis_retriever import AnalysisRetriever
from app.domain.retrieval.dense import dense_search
from app.domain.retrieval.fusion import reciprocal_rank_fusion
from app.domain.retrieval.hybrid import hybrid_search
from app.domain.retrieval.interfaces import RetrievedChunk
from app.domain.retrieval.router import select_buckets
from app.domain.retrieval.sparse import sparse_search

__all__ = [
    "AnalysisRetriever",
    "RetrievedChunk",
    "dense_search",
    "hybrid_search",
    "reciprocal_rank_fusion",
    "select_buckets",
    "sparse_search",
]
