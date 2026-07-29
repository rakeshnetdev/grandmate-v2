"""LichessGameConnector tests — no real network call, same `httpx.MockTransport`
convention `test_platforms.py` already established."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import IngestionSettings
from app.domain.imports.connectors import ConnectorError
from app.integrations.lichess import LichessGameConnector


def _connector_with_transport(handler, **settings_overrides) -> LichessGameConnector:  # type: ignore[no-untyped-def]
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return LichessGameConnector(IngestionSettings(**settings_overrides), http_client)


class TestFetchRecentGamesPgn:
    async def test_returns_the_response_body_as_pgn_text(self) -> None:
        pgn = '[Event "Test"]\n[White "magnus"]\n\n1. e4 e5 1-0\n'

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/magnus")
            assert request.headers["Accept"] == "application/x-chess-pgn"
            assert request.url.params["max"] == "10"
            return httpx.Response(200, text=pgn)

        connector = _connector_with_transport(handler)

        result = await connector.fetch_recent_games_pgn("magnus", 10)

        assert result == pgn

    async def test_raises_connector_error_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        connector = _connector_with_transport(handler)

        with pytest.raises(ConnectorError):
            await connector.fetch_recent_games_pgn("nobody", 10)

    async def test_raises_connector_error_on_an_unexpected_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        connector = _connector_with_transport(handler, lichess_rate_limit_rps=1000.0)

        with pytest.raises(ConnectorError):
            await connector.fetch_recent_games_pgn("someone", 10)

    async def test_retries_a_429_then_succeeds(self) -> None:
        attempts = {"count": 0}
        pgn = '[Event "Test"]\n\n1. e4 1-0\n'

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            if attempts["count"] < 2:
                return httpx.Response(429)
            return httpx.Response(200, text=pgn)

        connector = _connector_with_transport(handler, lichess_rate_limit_rps=1000.0)

        result = await connector.fetch_recent_games_pgn("magnus", 10)

        assert result == pgn
        assert attempts["count"] == 2

    async def test_raises_connector_error_on_a_transport_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known", request=request)

        connector = _connector_with_transport(handler)

        with pytest.raises(ConnectorError):
            await connector.fetch_recent_games_pgn("magnus", 10)
