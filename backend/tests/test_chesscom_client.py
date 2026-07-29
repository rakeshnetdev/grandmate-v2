"""ChessComGameConnector tests — no real network call, same `httpx.MockTransport`
convention `test_platforms.py` established."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import IngestionSettings
from app.domain.imports.connectors import ConnectorError
from app.integrations.chesscom import ChessComGameConnector

_ARCHIVES_URL = "https://api.chess.com/pub/player/hikaru/games/archives"
_JAN_URL = "https://api.chess.com/pub/player/hikaru/games/2024/01"
_FEB_URL = "https://api.chess.com/pub/player/hikaru/games/2024/02"


def _connector_with_transport(handler, **settings_overrides) -> ChessComGameConnector:  # type: ignore[no-untyped-def]
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return ChessComGameConnector(IngestionSettings(**settings_overrides), http_client)


class TestFetchRecentGamesPgn:
    async def test_walks_archives_from_most_recent_and_concatenates_pgns(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url == _ARCHIVES_URL:
                return httpx.Response(200, json={"archives": [_JAN_URL, _FEB_URL]})
            if url == _FEB_URL:
                # The most recent month alone already has enough games (max_games=1) —
                # January must never be fetched.
                return httpx.Response(200, json={"games": [{"pgn": "feb-game"}]})
            raise AssertionError(f"unexpected request to {url}")

        connector = _connector_with_transport(handler)

        result = await connector.fetch_recent_games_pgn("hikaru", 1)

        assert result == "feb-game"

    async def test_keeps_walking_older_archives_until_enough_games_are_collected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url == _ARCHIVES_URL:
                return httpx.Response(200, json={"archives": [_JAN_URL, _FEB_URL]})
            if url == _FEB_URL:
                return httpx.Response(200, json={"games": [{"pgn": "feb-game"}]})
            if url == _JAN_URL:
                return httpx.Response(200, json={"games": [{"pgn": "jan-game"}]})
            raise AssertionError(f"unexpected request to {url}")

        connector = _connector_with_transport(handler, chesscom_rate_limit_rps=1000.0)

        result = await connector.fetch_recent_games_pgn("hikaru", 2)

        # Chronological order preserved: January's game, then February's.
        assert result == "jan-game\n\nfeb-game"

    async def test_no_archives_returns_an_empty_string_without_further_requests(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"archives": []})

        connector = _connector_with_transport(handler)

        result = await connector.fetch_recent_games_pgn("nobody-yet", 10)

        assert result == ""

    async def test_raises_connector_error_when_the_account_does_not_exist(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        connector = _connector_with_transport(handler)

        with pytest.raises(ConnectorError):
            await connector.fetch_recent_games_pgn("nobody", 10)

    async def test_raises_connector_error_on_a_transport_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known", request=request)

        connector = _connector_with_transport(handler)

        with pytest.raises(ConnectorError):
            await connector.fetch_recent_games_pgn("hikaru", 10)
