"""Bucket router: which global corpus bucket(s) a query most likely belongs to
(Phase 7, project-plan.md's "retrieval router that selects buckets from query intent").

Deliberately a plain heuristic classifier, not a learned or LLM-based one — the actual
*agentic* bucket selection is Phase 10's job: `rag-architecture.md`'s `search_knowledge
(bucket, query)` tool signature takes the bucket as an explicit argument the agent
supplies itself, so an agent caller does not need this router at all. This module exists
for two narrower purposes instead: giving any non-agentic caller a sane default bucket
set when none is specified, and auto-routing the RAGAS harness's unlabelled queries.

Only covers the four static buckets — `analysis` is never a router target: it is
profile-scoped and only ever reached through `AnalysisRetriever`, which requires an
explicit `profile_id` a bare text query has no way to supply.
"""

from __future__ import annotations

from app.db.models import KnowledgeBucket

_BUCKET_KEYWORDS: dict[KnowledgeBucket, tuple[str, ...]] = {
    KnowledgeBucket.RULES: (
        "rule",
        "legal",
        "illegal",
        "touch-move",
        "touch move",
        "draw",
        "repetition",
        "fifty-move",
        "fifty move",
        "castl",
        "en passant",
        "promot",
        "stalemate",
        "fide",
        "law of chess",
        "laws of chess",
        "uci",
        "centipawn",
        "engine eval",
        "principal variation",
    ),
    KnowledgeBucket.OPENINGS: (
        "opening",
        "eco ",
        "defence",
        "defense",
        "gambit",
        "sicilian",
        "french defence",
        "french defense",
        "caro-kann",
        "ruy lopez",
        "italian game",
        "queen's gambit",
        "king's indian",
        "nimzo-indian",
        "english opening",
        "catalan",
        "grunfeld",
        "grünfeld",
        "reti",
        "réti",
        "london system",
    ),
    KnowledgeBucket.TACTICS: (
        "fork",
        "pin",
        "skewer",
        "discovered attack",
        "double check",
        "back-rank",
        "back rank",
        "smothered",
        "hanging piece",
        "removing the defender",
        "x-ray",
        "deflection",
        "decoy",
        "overload",
        "interference",
        "zwischenzug",
        "windmill",
        "tactic",
        "motif",
        "combination",
    ),
    KnowledgeBucket.STRATEGY: (
        "pawn structure",
        "isolated pawn",
        "isolated queen",
        "passed pawn",
        "bad bishop",
        "open file",
        "centre control",
        "center control",
        "space advantage",
        "development",
        "king safety",
        "endgame",
        "opposition",
        "minority attack",
        "strategic",
        "strategy",
        "plan",
        "structure",
    ),
}


def select_buckets(query: str) -> list[KnowledgeBucket]:
    """Every bucket whose keyword set matches `query`, or every bucket if none match.

    Falling back to "search everything" rather than "search nothing" matters: a query
    the heuristic fails to classify is exactly the case where the caller most needs
    retrieval to still attempt something, not silently return an empty result.
    """
    normalized = query.lower()
    matched = [
        bucket
        for bucket, keywords in _BUCKET_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return matched or list(KnowledgeBucket)


__all__ = ["select_buckets"]
