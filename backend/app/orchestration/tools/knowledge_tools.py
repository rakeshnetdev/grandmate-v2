"""Retrieval tools: the global corpus and the profile-scoped analysis bucket
(Phase 10, ADR-0008 §"the tool set").

Both wrap the exact retrieval functions Phase 7 already built and evaluated
(`hybrid_search`, `AnalysisRetriever`) — no retrieval logic lives here, only the
JSON-schema/dispatch boundary the agent loop needs (`claude.md` rule 13: one
implementation per capability, shared by agents and, from Phase 12, the MCP server).
"""

from __future__ import annotations

from typing import Any

from app.db.models import KnowledgeBucket
from app.domain.retrieval import AnalysisRetriever, RetrievedChunk, hybrid_search
from app.integrations.llm.base import ToolSpec
from app.orchestration.tools.context import ToolContext

SEARCH_KNOWLEDGE = ToolSpec(
    name="search_knowledge",
    description=(
        "Search the curated chess knowledge corpus for rules, opening theory, tactics, "
        "or strategy explanations. Use this for general chess questions not specific to "
        "one of the user's own games."
    ),
    parameters={
        "type": "object",
        "properties": {
            "bucket": {
                "type": "string",
                "enum": [b.value for b in KnowledgeBucket],
                "description": "Which corpus section to search.",
            },
            "query": {"type": "string", "description": "The search query."},
        },
        "required": ["bucket", "query"],
    },
)

SEARCH_ANALYSIS = ToolSpec(
    name="search_analysis",
    description=(
        "Search the user's own previously analysed games for relevant positions, "
        "findings, or commentary. Use this for questions about the user's own play "
        "across games, not a single already-loaded game (use get_game_analysis for that)."
    ),
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The search query."}},
        "required": ["query"],
    },
)


def _chunk_payload(chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "content": chunk.content,
        "score": round(chunk.score, 4),
        "retrieved_by": chunk.retrieved_by,
        "metadata": chunk.metadata,
    }


async def search_knowledge(ctx: ToolContext, *, bucket: str, query: str) -> dict[str, Any]:
    try:
        parsed_bucket = KnowledgeBucket(bucket)
    except ValueError:
        allowed = [b.value for b in KnowledgeBucket]
        return {"error": f"unknown bucket {bucket!r}, expected one of {allowed}"}

    results = await hybrid_search(
        ctx.session,
        bucket=parsed_bucket,
        query=query,
        embedding_provider=ctx.embedding_provider,
        settings=ctx.settings.retrieval,
    )
    return {"results": [_chunk_payload(chunk) for chunk in results]}


async def search_analysis(ctx: ToolContext, *, query: str) -> dict[str, Any]:
    retriever = AnalysisRetriever(ctx.session, ctx.embedding_provider, ctx.settings.retrieval)
    results = await retriever.search(query, profile_id=ctx.profile_id)
    return {"results": [_chunk_payload(chunk) for chunk in results]}


__all__ = ["SEARCH_ANALYSIS", "SEARCH_KNOWLEDGE", "search_analysis", "search_knowledge"]
