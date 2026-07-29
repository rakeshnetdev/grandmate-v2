"""Lichess game-export connector (Phase 14, ADR-0007, D-030/D-031).

Fetches PGN directly from Lichess's public games-export endpoint. No OAuth token is
involved (D-030): `GET /api/games/user/{username}` is public for a user's public games,
the same trust level `integrations/platforms.py`'s login lookup already relies on — real
Lichess OAuth2 PKCE (ADR-0007) stays deferred until a feature actually needs private data
or write access, which reading a public game history is not.

Requesting `Accept: application/x-chess-pgn` rather than the default NDJSON is D-031:
the connector's only job is producing PGN text for `ImportService`'s existing pipeline,
not a second parser for Lichess's structured game JSON.
"""

from __future__ import annotations

import httpx

from app.core.config import IngestionSettings
from app.domain.imports.connectors import ConnectorError
from app.integrations.http_retry import get_with_backoff

LICHESS_GAMES_API = "https://lichess.org/api/games/user"
USER_AGENT = "GrandMate/0.1 (chess analysis; +https://github.com/rakeshnetdev/grandmate-v2)"


class LichessGameConnector:
    """Structurally satisfies `domain.imports.connectors.PlatformGameConnector`."""

    def __init__(
        self, settings: IngestionSettings, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings
        self._client = client

    async def fetch_recent_games_pgn(self, username: str, max_games: int) -> str:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/x-chess-pgn"}
        # Lichess's own `max` truncates server-side to the most recent N games, so this
        # is one request regardless of window size — no pagination to rate-limit here,
        # unlike Chess.com's month-by-month archives.
        params = {"max": max_games}
        url = f"{LICHESS_GAMES_API}/{username}"

        try:
            if self._client is not None:
                response = await get_with_backoff(
                    self._client,
                    url,
                    headers=headers,
                    params=params,
                    rate_limit_rps=self._settings.lichess_rate_limit_rps,
                )
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await get_with_backoff(
                        client,
                        url,
                        headers=headers,
                        params=params,
                        rate_limit_rps=self._settings.lichess_rate_limit_rps,
                    )
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Could not reach Lichess for {username!r}: {exc}") from exc

        if response.status_code == 404:
            raise ConnectorError(f"No Lichess account named {username!r}")
        if response.status_code != 200:
            raise ConnectorError(
                f"Lichess returned {response.status_code} fetching games for {username!r}"
            )
        return response.text


__all__ = ["LICHESS_GAMES_API", "LichessGameConnector"]
