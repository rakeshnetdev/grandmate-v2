"""Developer insight routes.

Registered **only** when developer insight is active, which
``Settings.dev_insight_active`` forces off in production. These endpoints expose request
internals and are unauthenticated until Phase 2 adds an auth layer, so they must not be
reachable on a deployed environment.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.settings import SettingsDep
from app.core.devinsight import Trace, TraceStore, TraceSummary
from app.db.models import KnowledgeBucket
from app.domain.retrieval import RetrievedChunk, dense_search, hybrid_search, sparse_search
from app.integrations.llm import OpenAIEmbeddingProvider

router = APIRouter(prefix="/dev", tags=["developer-insight"])

_STRATEGIES = {"dense", "sparse", "hybrid"}


class RetrievedChunkOut(BaseModel):
    """Manual-testing view of a retrieval result (Phase 7). Not a stable API contract —
    the real, versioned surface for this arrives at Phase 10 as an agent tool."""

    chunk_id: str
    content: str
    score: float
    metadata: dict[str, object]
    retrieved_by: str

    @classmethod
    def from_domain(cls, chunk: RetrievedChunk) -> RetrievedChunkOut:
        return cls(
            chunk_id=str(chunk.chunk_id),
            content=chunk.content,
            score=chunk.score,
            metadata=chunk.metadata,
            retrieved_by=chunk.retrieved_by,
        )


def _store(request: Request) -> TraceStore:
    """The store built in ``create_app``, reachable from app state."""
    store: TraceStore = request.app.state.trace_store
    return store


@router.get("/traces", response_model=list[TraceSummary])
async def list_traces(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TraceSummary]:
    """Recent traces, newest first.

    Returns summaries rather than full traces so opening the panel does not serialise
    every span of every retained request.
    """
    return _store(request).list(limit=limit)


@router.get("/traces/{trace_id}", response_model=Trace)
async def get_trace(request: Request, trace_id: str) -> Trace:
    """One full trace, including every span."""
    trace = _store(request).get(trace_id)
    if trace is None:
        # Traces live in a bounded ring buffer, so "not found" usually means "aged out"
        # rather than "never existed". Say so, since the distinction matters to whoever
        # is debugging.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found. It may have been evicted from the buffer.",
        )
    return trace


@router.delete("/traces", status_code=status.HTTP_204_NO_CONTENT)
async def clear_traces(request: Request) -> None:
    """Empty the buffer. Useful before reproducing a specific problem."""
    _store(request).clear()


@router.get("/search", response_model=list[RetrievedChunkOut])
async def search_knowledge_dev(
    session: DbSessionDep,
    settings: SettingsDep,
    bucket: str = Query(..., description="rules | openings | tactics | strategy"),
    query: str = Query(..., min_length=1),
    strategy: str = Query(default="hybrid", description="dense | sparse | hybrid"),
) -> list[RetrievedChunkOut]:
    """Manual retrieval testing for Phase 7, ahead of Phase 10's real agent tool.

    Deliberately excludes the `analysis` bucket: that bucket is profile-scoped
    (`AnalysisRetriever` requires `profile_id`), and this route has no auth — adding it
    here would mean building a second, weaker isolation path instead of the one that
    already exists. Real chat access to `analysis` arrives properly in Phase 10/11,
    through the authenticated path.

    Costs a real embedding API call for `dense`/`hybrid` — dev-gated for that reason too,
    same as every other route in this module.
    """
    if strategy not in _STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"strategy must be one of {sorted(_STRATEGIES)}, got {strategy!r}",
        )
    try:
        parsed_bucket = KnowledgeBucket(bucket)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"bucket must be one of {[b.value for b in KnowledgeBucket]}, got {bucket!r}",
        ) from exc

    if strategy == "sparse":
        results = await sparse_search(
            session, bucket=parsed_bucket, query=query, settings=settings.retrieval
        )
    else:
        embedding_provider = OpenAIEmbeddingProvider(settings.llm, settings.retrieval)
        try:
            search_fn = dense_search if strategy == "dense" else hybrid_search
            results = await search_fn(
                session,
                bucket=parsed_bucket,
                query=query,
                embedding_provider=embedding_provider,
                settings=settings.retrieval,
            )
        finally:
            await embedding_provider.aclose()

    return [RetrievedChunkOut.from_domain(chunk) for chunk in results]


__all__ = ["router"]
