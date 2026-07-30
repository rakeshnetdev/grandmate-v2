"""Analysis-lookup tools: canonical per-game facts, critical moments, profile
aggregates, and opening identification (Phase 10, ADR-0008 §"the tool set").

Every tool here reuses an existing profile-scoped query/service rather than writing a
new one — `get_latest_analysis`/`get_moves` (Phase 5), `ProfileAnalyticsService` (Phase
8), `OpeningIndex` (Phase 6). The tool layer's own job is strictly the JSON-schema and
dispatch boundary; a tool that re-implemented its own fetch would be exactly the
duplicated capability `claude.md` rule 13 forbids.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.domain.analysis import display_swing_cp, get_latest_analysis, get_moves
from app.domain.analytics import ProfileAnalyticsService
from app.domain.patterns.queries import get_opening_match
from app.integrations.llm.base import ToolSpec
from app.orchestration.tools.context import ToolContext

GET_GAME_ANALYSIS = ToolSpec(
    name="get_game_analysis",
    description=(
        "Fetch the canonical engine analysis for one of the user's own games: every "
        "move played, its classification (best/good/inaccuracy/mistake/blunder), the "
        "engine's evaluation at each ply, and the opening that was reached, if known."
    ),
    parameters={
        "type": "object",
        "properties": {"game_id": {"type": "string", "description": "The game's id."}},
        "required": ["game_id"],
    },
)

LIST_CRITICAL_MOMENTS = ToolSpec(
    name="list_critical_moments",
    description=(
        "The pivotal plies in one of the user's own games — the moves with the largest "
        "evaluation swings, where the game's outcome was most contested."
    ),
    parameters={
        "type": "object",
        "properties": {"game_id": {"type": "string", "description": "The game's id."}},
        "required": ["game_id"],
    },
)

GET_PROFILE_AGGREGATE = ToolSpec(
    name="get_profile_aggregate",
    description=(
        "Cross-game statistics for the user's own recent games: accuracy trend, move "
        "classification rates, opening performance, and recurring weaknesses over a "
        "window of games."
    ),
    parameters={
        "type": "object",
        "properties": {
            "window": {
                "type": "integer",
                "description": "How many recent games to aggregate over.",
            }
        },
        "required": [],
    },
)

LOOKUP_OPENING = ToolSpec(
    name="lookup_opening",
    description="Identify the ECO code and opening name for a board position, given its EPD.",
    parameters={
        "type": "object",
        "properties": {
            "epd": {
                "type": "string",
                "description": "The position's EPD (FEN without move counters).",
            }
        },
        "required": ["epd"],
    },
)


def _parse_game_id(game_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(game_id)
    except ValueError:
        return None


async def get_game_analysis(ctx: ToolContext, *, game_id: str) -> dict[str, Any]:
    parsed_id = _parse_game_id(game_id)
    if parsed_id is None:
        return {"error": f"{game_id!r} is not a valid game id"}

    analysis = await get_latest_analysis(ctx.session, parsed_id, ctx.profile_id)
    if analysis is None:
        return {"error": "no analysis found for that game"}

    moves_by_ply = {m.ply: m for m in await get_moves(ctx.session, parsed_id, ctx.profile_id)}
    opening = await get_opening_match(ctx.session, parsed_id, ctx.profile_id)
    return {
        "analysis_version": analysis.analysis_version,
        "summary": analysis.summary,
        "opening": (
            {"eco": opening.eco, "opening_name": opening.opening_name}
            if opening is not None
            else None
        ),
        "moves": [
            {
                "ply": ev.ply,
                "san": moves_by_ply[ev.ply].san if ev.ply in moves_by_ply else None,
                "classification": ev.classification.value,
                "eval_cp": ev.eval_cp,
                "mate_in": ev.mate_in,
                "eval_swing_cp": display_swing_cp(ev.eval_swing_cp, ev.mate_swing),
                "mate_swing": ev.mate_swing,
                "best_move_uci": ev.best_move_uci,
            }
            for ev in analysis.evaluations
        ],
    }


async def list_critical_moments(ctx: ToolContext, *, game_id: str) -> dict[str, Any]:
    parsed_id = _parse_game_id(game_id)
    if parsed_id is None:
        return {"error": f"{game_id!r} is not a valid game id"}

    analysis = await get_latest_analysis(ctx.session, parsed_id, ctx.profile_id)
    if analysis is None:
        return {"error": "no analysis found for that game"}

    moves_by_ply = {m.ply: m for m in await get_moves(ctx.session, parsed_id, ctx.profile_id)}
    return {
        "critical_moments": [
            {
                "ply": ev.ply,
                "san": moves_by_ply[ev.ply].san if ev.ply in moves_by_ply else None,
                "classification": ev.classification.value,
                "eval_swing_cp": display_swing_cp(ev.eval_swing_cp, ev.mate_swing),
                "mate_swing": ev.mate_swing,
            }
            for ev in analysis.evaluations
            if ev.is_critical_moment
        ]
    }


async def get_profile_aggregate(ctx: ToolContext, *, window: int | None = None) -> dict[str, Any]:
    settings = ctx.settings.analytics
    window_size = window if window is not None else settings.analytics_default_window
    if window_size not in settings.window_sizes_list:
        return {"error": f"window must be one of {settings.window_sizes_list}"}

    service = ProfileAnalyticsService(ctx.session, settings)
    snapshot = await service.compute_snapshot(ctx.profile_id, window_size)
    return {
        "window_size": snapshot.window_size,
        "games_included": snapshot.games_included,
        "sufficient_sample": snapshot.sufficient_sample,
        **snapshot.metrics,
    }


async def lookup_opening(ctx: ToolContext, *, epd: str) -> dict[str, Any]:
    match = ctx.opening_index.match([epd])
    if match is None:
        return {"result": None}
    return {"result": {"eco": match.eco, "opening_name": match.opening_name, "epd": match.epd}}


__all__ = [
    "GET_GAME_ANALYSIS",
    "GET_PROFILE_AGGREGATE",
    "LIST_CRITICAL_MOMENTS",
    "LOOKUP_OPENING",
    "get_game_analysis",
    "get_profile_aggregate",
    "list_critical_moments",
    "lookup_opening",
]
