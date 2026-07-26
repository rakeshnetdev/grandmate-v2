"""Canonicalization orchestration: fetch, replay, persist, resolve focus (Phase 4).

Runs synchronously, called by `ImportService` right after each game is stored — same
philosophy as Phase 3's D-018 (in-process, no new infra, MVP scale). A canonicalization
failure does not undo the import: the `Game` row, its dedup guarantee, and its raw PGN
all stand regardless. Only `canonicalized_at`/`parse_error` and the presence of
`GameMove` rows reflect whether this step succeeded.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models import Game, GameMove, ProfileSource
from app.domain.games.normalization import resolve_focus
from app.domain.games.parsing import CanonicalizationError, canonicalize_pgn
from app.integrations.storage import StorageBackend


class GameParsingService:
    """Turns a stored `Game` row into canonical `GameMove` records."""

    def __init__(self, session: AsyncSession, storage: StorageBackend) -> None:
        self._session = session
        self._storage = storage

    async def canonicalize(self, game: Game) -> None:
        """Replay `game`'s stored PGN and persist the result onto `game` in place.

        Never raises for a canonicalization failure — that is recorded on the game via
        `parse_error`, not propagated, so one bad game cannot fail the request it arrived
        in. Storage/transport failures are the one thing that does propagate: unlike a
        malformed game, there is no partial result to record for "couldn't read the file
        at all," and retrying is the correct response, not silently marking it failed.
        """
        pgn_text = (await self._storage.get(game.raw_pgn_path)).decode("utf-8")

        try:
            canonical = canonicalize_pgn(pgn_text)
        except CanonicalizationError as exc:
            game.parse_error = {"reason": exc.reason.value, "detail": exc.detail}
            game.canonicalized_at = None
            return

        # Bulk delete + add_all, not `game.moves = [...]`: assigning to the relationship
        # collection makes SQLAlchemy lazy-load the existing collection first to reconcile
        # delete-orphan cascade, which is a synchronous load this async session can't
        # satisfy implicitly. Targeting the FK directly sidesteps that entirely, and
        # handles re-canonicalization (stale rows from a previous run) the same way.
        await self._session.execute(delete(GameMove).where(GameMove.game_id == game.id))
        self._session.add_all(
            [
                GameMove(
                    game_id=game.id,
                    ply=move.ply,
                    san=move.san,
                    uci=move.uci,
                    fen_before=move.fen_before,
                    fen_after=move.fen_after,
                    epd_after=move.epd_after,
                    clock_ms=move.clock_ms,
                )
                for move in canonical.moves
            ]
        )

        await self._resolve_focus(game)

        game.parse_error = None
        game.canonicalized_at = utc_now()

    async def _resolve_focus(self, game: Game) -> None:
        white = game.headers.get("White")
        black = game.headers.get("Black")
        if not white or not black:
            return

        result = await self._session.execute(
            select(ProfileSource.source_username).where(ProfileSource.profile_id == game.profile_id)
        )
        linked_usernames = list(result.scalars().all())
        if not linked_usernames:
            return

        resolution = resolve_focus(white=white, black=black, linked_usernames=linked_usernames)
        game.focus_color = resolution.focus_color
        game.opponent_name = resolution.opponent_name


__all__ = ["GameParsingService"]
