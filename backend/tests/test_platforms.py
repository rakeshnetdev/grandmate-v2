"""PlatformClient tests.

No existing coverage exercised this module directly — auth tests monkeypatch
`fetch_user` wholesale instead. These add direct coverage, including the regression this
phase fixed: a transport-level failure (DNS, connection refused, timeout) must surface as
`PlatformError`, not propagate as a raw `httpx` exception that becomes an unhandled 500.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import IngestionSettings
from app.db.models import AuthProvider
from app.integrations.platforms import PlatformClient, PlatformError, UserNotFoundError


def _client_with_transport(handler) -> PlatformClient:  # type: ignore[no-untyped-def]
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return PlatformClient(IngestionSettings(), http_client)


class TestFetchUser:
    async def test_finds_a_real_lichess_style_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "magnus", "username": "DrNykterstein"})

        client = _client_with_transport(handler)

        user = await client.fetch_user(AuthProvider.LICHESS, "DrNykterstein")

        assert user.provider_user_id == "magnus"
        assert user.username == "DrNykterstein"

    async def test_raises_not_found_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        client = _client_with_transport(handler)

        with pytest.raises(UserNotFoundError):
            await client.fetch_user(AuthProvider.LICHESS, "nobody")

    async def test_treats_a_closed_lichess_account_as_not_found(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "x", "username": "x", "disabled": True})

        client = _client_with_transport(handler)

        with pytest.raises(UserNotFoundError):
            await client.fetch_user(AuthProvider.LICHESS, "x")

    async def test_raises_platform_error_on_an_unexpected_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        client = _client_with_transport(handler)

        with pytest.raises(PlatformError):
            await client.fetch_user(AuthProvider.LICHESS, "someone")

    async def test_raises_platform_error_on_a_transport_failure(self) -> None:
        """The regression this phase fixed: a connection failure must become
        `PlatformError`, not an unhandled `httpx` exception."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known", request=request)

        client = _client_with_transport(handler)

        with pytest.raises(PlatformError):
            await client.fetch_user(AuthProvider.LICHESS, "someone")

    async def test_rejects_a_blank_username_without_a_network_call(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("should not reach the network for a blank username")

        client = _client_with_transport(handler)

        with pytest.raises(UserNotFoundError):
            await client.fetch_user(AuthProvider.LICHESS, "   ")

    async def test_chesscom_lookup_uses_the_lowercased_username_as_the_stable_id(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/hikaru")
            return httpx.Response(200, json={"username": "Hikaru"})

        client = _client_with_transport(handler)

        user = await client.fetch_user(AuthProvider.CHESSCOM, "Hikaru")

        assert user.provider_user_id == "hikaru"
        assert user.username == "Hikaru"
