"""Chess.com published-data game connector (Phase 14, ADR-0007, D-030/D-031).

Chess.com's Published-Data API has always been public and unauthenticated (ADR-0007);
nothing about Phase 14 changes that. Games are organised by month
(`/pub/player/{username}/games/archives` lists archive URLs oldest-first); each archive's
game objects carry a `pgn` field directly (D-031), so — same as the Lichess connector —
this module's only job is producing PGN text, never a second parser for the structured
JSON shape.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import IngestionSettings
from app.domain.imports.connectors import ConnectorError
from app.integrations.http_retry import get_with_backoff

CHESSCOM_API = "https://api.chess.com/pub"
USER_AGENT = "GrandMate/0.1 (chess analysis; +https://github.com/rakeshnetdev/grandmate-v2)"


class ChessComGameConnector:
    """Structurally satisfies `domain.imports.connectors.PlatformGameConnector`."""

    def __init__(
        self, settings: IngestionSettings, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings
        self._client = client

    async def fetch_recent_games_pgn(self, username: str, max_games: int) -> str:
        archive_urls = await self._fetch_archive_urls(username)
        if not archive_urls:
            return ""

        # Walk archives from most recent to oldest, stopping once enough games are
        # collected — a "last 10 games" request has no business fetching a player's
        # entire multi-year archive history.
        collected: list[str] = []
        for index, archive_url in enumerate(reversed(archive_urls)):
            games = await self._fetch_archive_games(archive_url)
            collected = [g["pgn"] for g in games if g.get("pgn")] + collected
            if len(collected) >= max_games:
                break
            if index + 1 < len(archive_urls):
                # Only sleep between archive fetches, never after the last one needed —
                # same "don't pay for a delay nothing is waiting on" reasoning as the
                # Lichess connector's single-request case.
                await asyncio.sleep(1.0 / self._settings.chesscom_rate_limit_rps)

        return "\n\n".join(collected[-max_games:])

    async def _fetch_archive_urls(self, username: str) -> list[str]:
        url = f"{CHESSCOM_API}/player/{username.lower()}/games/archives"
        response = await self._get(url)
        if response.status_code == 404:
            raise ConnectorError(f"No Chess.com account named {username!r}")
        if response.status_code != 200:
            raise ConnectorError(f"Chess.com returned {response.status_code} listing archives")
        payload: dict[str, Any] = response.json()
        return list(payload.get("archives", []))

    async def _fetch_archive_games(self, archive_url: str) -> list[dict[str, Any]]:
        response = await self._get(archive_url)
        if response.status_code != 200:
            raise ConnectorError(
                f"Chess.com returned {response.status_code} fetching {archive_url}"
            )
        payload: dict[str, Any] = response.json()
        return list(payload.get("games", []))

    async def _get(self, url: str) -> httpx.Response:
        headers = {"User-Agent": USER_AGENT}
        try:
            if self._client is not None:
                return await get_with_backoff(
                    self._client,
                    url,
                    headers=headers,
                    rate_limit_rps=self._settings.chesscom_rate_limit_rps,
                )
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await get_with_backoff(
                    client,
                    url,
                    headers=headers,
                    rate_limit_rps=self._settings.chesscom_rate_limit_rps,
                )
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Could not reach Chess.com: {exc}") from exc


__all__ = ["CHESSCOM_API", "ChessComGameConnector"]
