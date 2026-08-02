"""Grounding guardrail (Phase 10, `rag-architecture.md` §6).

Chess truth is never asserted by an LLM alone (`claude.md`'s RAG and Agent Rules). The
agent's final turn must answer in a structured shape — `{"answer": ..., "citations":
[...]}` — rather than free text, precisely so this module has something machine-checkable
to verify: every citation is checked against the same profile-scoped tables the tools
themselves read from (never trusting the model's own restatement of a tool result), and
variation citations reuse `validate_line` rather than re-implementing legality checking.

On failure the caller (the chat graph) regenerates once with the violations fed back, then
degrades to a deterministic factual summary — never delivers an answer that failed this
check.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select

from app.db.models import (
    GameAnalysis,
    GameMove,
    KnowledgeChunk,
    KnowledgeDocument,
    MoveEvaluation,
    OpeningMatch,
)
from app.domain.analysis import get_latest_analysis, get_moves
from app.domain.patterns.queries import get_opening_match
from app.orchestration.tools.context import ToolContext
from app.orchestration.tools.validation_tools import validate_line


def retrieved_chunk_ids(tool_results: list[dict[str, Any]]) -> set[str]:
    """Every chunk id a retrieval tool returned this turn, read off the recorded tool
    results (Phase 20).

    Lives here rather than in either graph because it is the input contract for
    `validate_answer`'s `retrieved_chunk_ids` argument, and both the single-agent loop
    (`graphs/chat.py`'s `turn_context`) and the multi-agent graph (`_combined_context`)
    record tool results in the same shape. One implementation, per rule 13.

    Reads the recorded *result* of each call — server-side truth about what the tool
    returned, never the model's account of it.
    """
    chunk_ids: set[str] = set()
    for entry in tool_results:
        result = entry.get("result", {})
        if not isinstance(result, dict):
            continue
        for chunk in result.get("results", []):
            chunk_id = chunk.get("chunk_id") if isinstance(chunk, dict) else None
            if isinstance(chunk_id, str):
                chunk_ids.add(chunk_id)
    return chunk_ids


async def validate_answer(
    ctx: ToolContext,
    raw_content: str,
    *,
    retrieved_chunk_ids: set[str] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse the model's final answer and check every citation.

    Returns `(parsed, violations)`. `parsed` is `None` only when the response is not
    even shaped like an answer — a caller should treat that as an unconditional retry
    trigger rather than inspecting citations that were never produced.

    `retrieved_chunk_ids` (Phase 20) is every chunk a retrieval tool actually returned
    during this turn, and it is what a `knowledge` citation is checked against. Verifying
    that the chunk merely exists in the corpus would be a much weaker claim — it would let
    the model cite any real document for any assertion — whereas this proves the answer
    cites something the agent genuinely saw. Defaulted to `None` (meaning "no retrieval
    happened") so callers that never retrieve stay unchanged; a `knowledge` citation is
    then always a violation, which is correct.
    """
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return None, ["response was not valid JSON"]
    if not isinstance(parsed, dict) or not isinstance(parsed.get("answer"), str):
        return None, ["response missing a string 'answer' field"]

    citations = parsed.get("citations", [])
    if not isinstance(citations, list):
        return parsed, ["'citations' must be a list"]

    violations: list[str] = []
    moves_cache: dict[uuid.UUID, dict[int, GameMove] | None] = {}
    analysis_cache: dict[uuid.UUID, GameAnalysis | None] = {}
    opening_cache: dict[uuid.UUID, OpeningMatch | None] = {}

    for index, citation in enumerate(citations):
        if not isinstance(citation, dict):
            violations.append(f"citation {index} is not an object")
            continue
        kind = citation.get("kind")
        if kind == "move":
            violations.extend(await _check_move(ctx, citation, moves_cache, index))
        elif kind == "evaluation":
            violations.extend(await _check_evaluation(ctx, citation, analysis_cache, index))
        elif kind == "variation":
            violations.extend(_check_variation(citation, index))
        elif kind == "opening":
            violations.extend(await _check_opening(ctx, citation, opening_cache, index))
        elif kind == "knowledge":
            violations.extend(
                await _check_knowledge(ctx, citation, retrieved_chunk_ids or set(), index)
            )
        else:
            violations.append(f"citation {index} has unknown kind {kind!r}")

    return parsed, violations


async def _moves_for_game(
    ctx: ToolContext, game_id: str, cache: dict[uuid.UUID, dict[int, GameMove] | None]
) -> dict[int, GameMove] | None:
    try:
        parsed_id = uuid.UUID(game_id)
    except (ValueError, TypeError):
        return None
    if parsed_id not in cache:
        moves = await get_moves(ctx.session, parsed_id, ctx.profile_id)
        cache[parsed_id] = {m.ply: m for m in moves} if moves else None
    return cache[parsed_id]


async def _analysis_for_game(
    ctx: ToolContext, game_id: str, cache: dict[uuid.UUID, GameAnalysis | None]
) -> GameAnalysis | None:
    try:
        parsed_id = uuid.UUID(game_id)
    except (ValueError, TypeError):
        return None
    if parsed_id not in cache:
        cache[parsed_id] = await get_latest_analysis(ctx.session, parsed_id, ctx.profile_id)
    return cache[parsed_id]


async def _check_move(
    ctx: ToolContext,
    citation: dict[str, Any],
    cache: dict[uuid.UUID, dict[int, GameMove] | None],
    index: int,
) -> list[str]:
    game_id, ply, san = citation.get("game_id"), citation.get("ply"), citation.get("san")
    if not isinstance(game_id, str) or not isinstance(ply, int) or not isinstance(san, str):
        return [f"citation {index}: 'move' citation needs game_id, ply, and san"]

    moves = await _moves_for_game(ctx, game_id, cache)
    if moves is None:
        return [f"citation {index}: game {game_id} not found"]
    move = moves.get(ply)
    if move is None:
        return [f"citation {index}: no move at ply {ply} in game {game_id}"]
    if move.san != san:
        return [f"citation {index}: ply {ply} was {move.san!r}, not {san!r}"]
    return []


async def _check_evaluation(
    ctx: ToolContext,
    citation: dict[str, Any],
    cache: dict[uuid.UUID, GameAnalysis | None],
    index: int,
) -> list[str]:
    game_id, ply = citation.get("game_id"), citation.get("ply")
    if not isinstance(game_id, str) or not isinstance(ply, int):
        return [f"citation {index}: 'evaluation' citation needs game_id and ply"]

    analysis = await _analysis_for_game(ctx, game_id, cache)
    if analysis is None:
        return [f"citation {index}: no analysis found for game {game_id}"]
    evaluation: MoveEvaluation | None = next(
        (e for e in analysis.evaluations if e.ply == ply), None
    )
    if evaluation is None:
        return [f"citation {index}: no evaluation at ply {ply} in game {game_id}"]

    eval_cp, mate_in = citation.get("eval_cp"), citation.get("mate_in")
    if eval_cp is not None and eval_cp != evaluation.eval_cp:
        return [f"citation {index}: ply {ply} eval_cp was {evaluation.eval_cp}, not {eval_cp}"]
    if mate_in is not None and mate_in != evaluation.mate_in:
        return [f"citation {index}: ply {ply} mate_in was {evaluation.mate_in}, not {mate_in}"]
    return []


async def _check_opening(
    ctx: ToolContext,
    citation: dict[str, Any],
    cache: dict[uuid.UUID, OpeningMatch | None],
    index: int,
) -> list[str]:
    game_id, eco, name = citation.get("game_id"), citation.get("eco"), citation.get("opening_name")
    if not isinstance(game_id, str) or not isinstance(eco, str) or not isinstance(name, str):
        return [f"citation {index}: 'opening' citation needs game_id, eco, and opening_name"]

    try:
        parsed_id = uuid.UUID(game_id)
    except (ValueError, TypeError):
        return [f"citation {index}: {game_id!r} is not a valid game id"]
    if parsed_id not in cache:
        cache[parsed_id] = await get_opening_match(ctx.session, parsed_id, ctx.profile_id)
    opening = cache[parsed_id]

    if opening is None:
        return [f"citation {index}: no opening match found for game {game_id}"]
    if opening.eco != eco or opening.opening_name != name:
        return [
            f"citation {index}: game {game_id}'s opening was "
            f"{opening.eco} {opening.opening_name!r}, not {eco} {name!r}"
        ]
    return []


async def _check_knowledge(
    ctx: ToolContext,
    citation: dict[str, Any],
    retrieved_chunk_ids: set[str],
    index: int,
) -> list[str]:
    """A fact taken from the knowledge corpus rather than from one of the user's games.

    The model supplies only `chunk_id`; every human-readable field is filled in here from
    the database. That is deliberately stricter than the other kinds, which accept a
    model-written SAN or ECO and then check it matches — here there is nothing to check,
    because the model never gets to write the label at all.

    The title lookup is best-effort by design: `search_analysis` returns chunks from
    `analysis_knowledge_chunks`, which has no parent document, so a verified analysis
    chunk simply carries no title. Absence of a title is not a grounding failure —
    membership in this turn's retrieved set is what makes the citation true.
    """
    chunk_id = citation.get("chunk_id")
    if not isinstance(chunk_id, str):
        return [f"citation {index}: 'knowledge' citation needs chunk_id"]
    if chunk_id not in retrieved_chunk_ids:
        return [
            f"citation {index}: chunk {chunk_id} was not returned by a retrieval tool this turn"
        ]

    try:
        parsed_id = uuid.UUID(chunk_id)
    except (ValueError, TypeError):
        return [f"citation {index}: {chunk_id!r} is not a valid chunk id"]

    document = await _document_for_chunk(ctx, parsed_id)
    if document is not None:
        citation["title"] = document.title
        citation["source"] = document.source
    return []


async def _document_for_chunk(ctx: ToolContext, chunk_id: uuid.UUID) -> KnowledgeDocument | None:
    result = await ctx.session.execute(
        select(KnowledgeDocument)
        .join(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeChunk.id == chunk_id)
    )
    return result.scalar_one_or_none()


def _check_variation(citation: dict[str, Any], index: int) -> list[str]:
    fen, moves = citation.get("fen"), citation.get("moves")
    if not isinstance(fen, str) or not isinstance(moves, list):
        return [f"citation {index}: 'variation' citation needs fen and moves"]
    result = validate_line(fen=fen, moves=moves)
    if not result["legal"]:
        return [f"citation {index}: illegal variation ({result['reason']})"]
    return []


__all__ = ["retrieved_chunk_ids", "validate_answer"]
