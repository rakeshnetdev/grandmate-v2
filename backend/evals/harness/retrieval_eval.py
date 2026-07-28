"""RAGAS retrieval evaluation harness (Phase 7, `evaluation-strategy.md`).

Runs the golden retrieval dataset against dense-only, sparse-only, and hybrid
retrieval, scores each with RAGAS's non-LLM context precision/recall, and records the
comparison. Per `rag-architecture.md` section 3: **hybrid must beat both baselines on
the recorded numbers, or the simpler retriever ships.**

Also reports Hit Rate and Mean Reciprocal Rank (MRR) by query type
(`lexical`/`semantic`), plus a false-positive rate over the negative (out-of-corpus)
queries — a methodology adapted from `grandmate/evals/compare_retrievers.py` (see
`final_docs/v2/changes/0001-reuse-ledger.md`): deriving positive/negative query types
from the corpus itself rather than judging relevance by substring matching, and
reporting MRR because it is rank-sensitive where a boolean hit-rate is not — rebuilt
here against pgvector/rank-bm25/RAGAS instead of Chroma/BM25Okapi.

**Needs a real `OPENAI_API_KEY`** (dense retrieval embeds every query for real) and an
already-ingested corpus (`KnowledgeIngestionService.ingest_corpus()` must have run
first) — this is why it lives outside `app/` and outside the hermetic `tests/` suite,
run on demand rather than as part of `uv run pytest`.

Usage (from `backend/`):
    uv run python -m evals.harness.retrieval_eval
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings, get_settings
from app.db.models import KnowledgeBucket, KnowledgeChunk
from app.db.session import create_engine, create_session_factory, session_scope
from app.domain.retrieval.dense import dense_search
from app.domain.retrieval.hybrid import hybrid_search
from app.domain.retrieval.interfaces import RetrievedChunk
from app.domain.retrieval.sparse import sparse_search
from app.integrations.llm.openai_provider import OpenAIEmbeddingProvider
from evals.harness.dataset import GoldenQuery, load_golden_queries
from evals.harness.ragas_compat import ensure_ragas_importable

# A function call, not an import statement — immune to isort reordering itself back
# below the `ragas` imports it must precede. See ragas_compat.py's own docstring: an
# earlier version of this file used a bare `import ragas_compat` for its side effect,
# and a ruff --fix pass silently reordered it below the ragas imports it existed to
# protect, reintroducing the exact ImportError it was written to avoid.
ensure_ragas_importable()

from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.metrics import NonLLMContextPrecisionWithReference, NonLLMContextRecall  # noqa: E402

_HARNESS_DIR = Path(__file__).resolve().parent
DATASET_PATH = _HARNESS_DIR.parent / "datasets" / "golden" / "retrieval.jsonl"
RUNS_DIR = _HARNESS_DIR.parent / "runs"
DATASET_VERSION = "v1-2026-07-27"
RETRIEVER_VERSION = "phase-7-v1"


async def _resolve_reference_contents(session: AsyncSession, query: GoldenQuery) -> list[str]:
    """The actual chunk text a positive golden query's headings/substring resolve to —
    RAGAS's non-LLM metrics compare content, not ids (see dataset.py's docstring)."""
    if query.bucket is None:
        return []
    bucket = KnowledgeBucket(query.bucket)
    result = await session.execute(select(KnowledgeChunk).where(KnowledgeChunk.bucket == bucket))
    chunks = result.scalars().all()

    if query.expected_headings:
        return [
            chunk.content
            for chunk in chunks
            if chunk.chunk_metadata.get("heading") in query.expected_headings
        ]
    if query.expected_content_contains:
        needle = query.expected_content_contains.lower()
        return [chunk.content for chunk in chunks if needle in chunk.content.lower()]
    return []


async def _search(
    session: AsyncSession,
    strategy: str,
    bucket: KnowledgeBucket,
    query_text: str,
    embedding_provider: OpenAIEmbeddingProvider,
    settings: RetrievalSettings,
) -> list[RetrievedChunk]:
    if strategy == "dense":
        return await dense_search(
            session,
            bucket=bucket,
            query=query_text,
            embedding_provider=embedding_provider,
            settings=settings,
        )
    if strategy == "sparse":
        return await sparse_search(session, bucket=bucket, query=query_text, settings=settings)
    if strategy == "hybrid":
        return await hybrid_search(
            session,
            bucket=bucket,
            query=query_text,
            embedding_provider=embedding_provider,
            settings=settings,
        )
    raise ValueError(f"Unknown retrieval strategy: {strategy!r}")


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


async def _run_strategy(
    session: AsyncSession,
    strategy: str,
    queries: list[GoldenQuery],
    embedding_provider: OpenAIEmbeddingProvider,
    settings: RetrievalSettings,
) -> dict[str, object]:
    precision_metric = NonLLMContextPrecisionWithReference()
    recall_metric = NonLLMContextRecall()

    precision_scores: list[float] = []
    recall_scores: list[float] = []
    by_qtype: dict[str, list[bool]] = {}
    reciprocal_ranks: list[float] = []
    reciprocal_ranks_by_qtype: dict[str, list[float]] = {}
    negative_false_positives = 0
    negative_total = 0

    for query in queries:
        if query.is_negative:
            negative_total += 1
            # Negative queries carry no bucket -- check every bucket, mirroring what a
            # real caller with no router match would do (router.py's own documented
            # "search everything" fallback).
            found_anything = False
            for bucket in KnowledgeBucket:
                retrieved = await _search(
                    session, strategy, bucket, query.query, embedding_provider, settings
                )
                if retrieved:
                    found_anything = True
                    break
            if found_anything:
                negative_false_positives += 1
            continue

        bucket = KnowledgeBucket(query.bucket)
        retrieved = await _search(
            session, strategy, bucket, query.query, embedding_provider, settings
        )
        reference_contents = await _resolve_reference_contents(session, query)
        if not reference_contents:
            # A golden-set authoring problem (the heading/substring didn't resolve to
            # any chunk -- e.g. the corpus hasn't been ingested), not a retriever defect.
            # Surfaced in the run record's `unresolved_queries`, not silently dropped.
            continue

        retrieved_contents = [chunk.content for chunk in retrieved]
        sample = SingleTurnSample(
            user_input=query.query,
            retrieved_contexts=retrieved_contents or [""],
            reference_contexts=reference_contents,
        )
        precision_scores.append(await precision_metric.single_turn_ascore(sample))
        recall_scores.append(await recall_metric.single_turn_ascore(sample))

        hit = any(content in retrieved_contents for content in reference_contents)
        by_qtype.setdefault(query.qtype, []).append(hit)

        # Mean Reciprocal Rank: 1 / (rank of the first retrieved chunk that is actually
        # relevant), 0 if none is. Unlike the boolean hit-rate above, MRR is sensitive
        # to *where* in the ranked list a relevant chunk lands, not just whether it's
        # present at all — the property that actually distinguishes a good ranking
        # from a lucky one. Adapted from grandmate/evals/compare_retrievers.py's own
        # Hit-Rate/MRR reporting (see final_docs/v2/changes/0001-reuse-ledger.md).
        reciprocal_rank = 0.0
        for rank, content in enumerate(retrieved_contents, start=1):
            if content in reference_contents:
                reciprocal_rank = 1.0 / rank
                break
        reciprocal_ranks.append(reciprocal_rank)
        reciprocal_ranks_by_qtype.setdefault(query.qtype, []).append(reciprocal_rank)

    return {
        "strategy": strategy,
        "context_precision": _avg(precision_scores),
        "context_recall": _avg(recall_scores),
        "mrr": _avg(reciprocal_ranks),
        "mrr_by_qtype": {
            qtype: _avg(ranks) for qtype, ranks in sorted(reciprocal_ranks_by_qtype.items())
        },
        "hit_rate_by_qtype": {
            qtype: sum(hits) / len(hits) for qtype, hits in sorted(by_qtype.items())
        },
        "negative_false_positive_rate": (
            negative_false_positives / negative_total if negative_total else None
        ),
        "n_scored": len(precision_scores),
    }


async def run() -> dict[str, object]:
    settings = get_settings()
    queries = load_golden_queries(DATASET_PATH)

    reviewed_count = sum(1 for query in queries if query.reviewed_by)
    if reviewed_count == 0:
        print(
            "WARNING: no golden query has `reviewed_by` set yet. Per "
            "evaluation-strategy.md's golden-vs-synthetic rule, these scores are "
            "informative only and must not gate anything until a human spot-checks "
            "the set and it is marked reviewed.",
        )

    embedding_provider = OpenAIEmbeddingProvider(settings.llm, settings.retrieval)
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    results: dict[str, dict[str, object]] = {}
    try:
        async with session_scope(session_factory) as session:
            for strategy in ("dense", "sparse", "hybrid"):
                results[strategy] = await _run_strategy(
                    session, strategy, queries, embedding_provider, settings.retrieval
                )
    finally:
        await engine.dispose()
        await embedding_provider.aclose()

    dense_precision = results["dense"]["context_precision"] or 0.0
    sparse_precision = results["sparse"]["context_precision"] or 0.0
    hybrid_precision = results["hybrid"]["context_precision"] or 0.0
    dense_recall = results["dense"]["context_recall"] or 0.0
    sparse_recall = results["sparse"]["context_recall"] or 0.0
    hybrid_recall = results["hybrid"]["context_recall"] or 0.0
    hybrid_beats_both = hybrid_precision >= max(
        dense_precision, sparse_precision
    ) and hybrid_recall >= max(dense_recall, sparse_recall)

    record = {
        "dataset_path": str(DATASET_PATH),
        "dataset_version": DATASET_VERSION,
        "retriever_version": RETRIEVER_VERSION,
        "embed_model": settings.retrieval.embed_model,
        "reviewed_query_count": reviewed_count,
        "total_query_count": len(queries),
        "timestamp": datetime.now(UTC).isoformat(),
        "thresholds": {
            "context_precision": settings.evaluation.ragas_context_precision_threshold,
            "context_recall": settings.evaluation.ragas_context_recall_threshold,
        },
        "results": results,
        "hybrid_beats_both_baselines": hybrid_beats_both,
        "recommendation": (
            "ship hybrid"
            if hybrid_beats_both
            else "ship the simpler retriever (see rag-architecture.md section 3)"
        ),
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_retrieval.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Run recorded: {run_path}")
    return record


def main() -> None:
    record = asyncio.run(run())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()


__all__ = ["run"]
