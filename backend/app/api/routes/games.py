"""Game listing and single-game lookup.

Thin per the "routes delegate" rule: lookups live in `domain/games/queries.py`. Separate
resource from `/imports` on purpose, same reasoning as `/analysis` vs `/patterns` — an
import `Job` and the `Game` rows it produced are different resources with different
lifecycles, even though one import request creates both. This closes the "no games-list
route" gap noted since Phase 4: a caller previously had no way to discover a `game_id`
without already knowing it, which meant `/analysis/games/{id}` and `/patterns/games/{id}`
were unreachable from a fresh session.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.profile_scope import ScopedProfileIdDep
from app.api.dependencies.storage import StorageDep
from app.db.models import Game
from app.domain.games import get_game, list_games
from app.integrations.storage import ObjectNotFoundError
from app.schemas.games import GameSummary

router = APIRouter(prefix="/games", tags=["games"])


def _to_summary(game: Game) -> GameSummary:
    return GameSummary(
        id=game.id,
        source=game.source.value,
        headers=game.headers,
        played_at=game.played_at,
        canonicalized_at=game.canonicalized_at,
        created_at=game.created_at,
    )


@router.get("", response_model=list[GameSummary])
async def list_my_games(profile_id: ScopedProfileIdDep, session: DbSessionDep) -> list[GameSummary]:
    """Games in the requested profile (defaults to the caller's own SELF profile — see
    `profile_id`'s Phase 8b dependency), most recent first."""
    games = await list_games(session, profile_id)
    return [_to_summary(game) for game in games]


@router.get("/{game_id}", response_model=GameSummary)
async def get_my_game(
    game_id: uuid.UUID, profile_id: ScopedProfileIdDep, session: DbSessionDep
) -> GameSummary:
    """A single game in the requested profile."""
    game = await get_game(session, game_id, profile_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return _to_summary(game)


@router.get("/{game_id}/pgn", response_class=PlainTextResponse)
async def get_my_game_pgn(
    game_id: uuid.UUID,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    storage: StorageDep,
) -> str:
    """The game's raw PGN as plain text (Phase 16b follow-up) — exactly the bytes that
    were imported, fetched from storage by the game's own `raw_pgn_path`."""
    game = await get_game(session, game_id, profile_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    try:
        data = await storage.get(game.raw_pgn_path)
    except ObjectNotFoundError:
        # The row exists but its blob is gone (e.g. a wiped local storage dir) — a
        # data-state gap, still a 404 from the caller's perspective, with a distinct
        # detail so the two cases are tellable apart in logs.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stored PGN not found"
        ) from None
    return data.decode("utf-8", errors="replace")


__all__ = ["router"]
