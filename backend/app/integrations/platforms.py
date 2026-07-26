"""Chess platform lookups.

Both platforms expose a public, unauthenticated endpoint for "does this user exist and
what is their canonical name". That is all login needs, so it is all this module does.

Looking the username up rather than trusting it costs one cheap request and buys two
things: typos are rejected at login instead of producing an empty profile, and we store
the platform's canonical casing rather than whatever the user typed.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import IngestionSettings
from app.db.models import AuthProvider

LICHESS_API = "https://lichess.org/api"
CHESSCOM_API = "https://api.chess.com/pub"

# Chess.com blocks requests without a descriptive User-Agent.
USER_AGENT = "GrandMate/0.1 (chess analysis; +https://github.com/rakeshnetdev/grandmate-v2)"


class PlatformError(RuntimeError):
    """The platform could not be reached or returned something unusable."""


class UserNotFoundError(PlatformError):
    """No such user on that platform."""


@dataclass(frozen=True)
class PlatformUser:
    """The minimum a login needs to identify someone."""

    provider: AuthProvider
    # Stable identifier. Lichess exposes a lowercase `id` distinct from the display name;
    # Chess.com has no separate id, so the lowercased username stands in.
    provider_user_id: str
    username: str


class PlatformClient:
    """Looks up users on Lichess and Chess.com."""

    def __init__(
        self, settings: IngestionSettings, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings
        self._client = client

    async def _get(self, url: str) -> httpx.Response:
        headers = {"User-Agent": USER_AGENT}
        if self._client is not None:
            return await self._client.get(url, headers=headers)
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.get(url, headers=headers)

    async def fetch_user(self, provider: AuthProvider, username: str) -> PlatformUser:
        """Look a user up, or raise :class:`UserNotFoundError`."""
        cleaned = username.strip()
        if not cleaned:
            raise UserNotFoundError("Username is empty")

        if provider is AuthProvider.LICHESS:
            return await self._fetch_lichess(cleaned)
        return await self._fetch_chesscom(cleaned)

    async def _fetch_lichess(self, username: str) -> PlatformUser:
        response = await self._get(f"{LICHESS_API}/user/{username}")

        if response.status_code == 404:
            raise UserNotFoundError(f"No Lichess account named {username!r}")
        if response.status_code != 200:
            raise PlatformError(f"Lichess returned {response.status_code}")

        payload = response.json()
        # Closed accounts still resolve; treating them as found would create a profile
        # whose games can never be imported.
        if payload.get("disabled"):
            raise UserNotFoundError(f"Lichess account {username!r} is closed")

        return PlatformUser(
            provider=AuthProvider.LICHESS,
            provider_user_id=str(payload["id"]),
            username=str(payload.get("username", username)),
        )

    async def _fetch_chesscom(self, username: str) -> PlatformUser:
        response = await self._get(f"{CHESSCOM_API}/player/{username.lower()}")

        if response.status_code == 404:
            raise UserNotFoundError(f"No Chess.com account named {username!r}")
        if response.status_code != 200:
            raise PlatformError(f"Chess.com returned {response.status_code}")

        payload = response.json()
        # Chess.com has no id separate from the username, so the lowercased handle is the
        # stable key. Usernames there are not reassigned, so this is safe.
        canonical = str(payload.get("username", username))
        return PlatformUser(
            provider=AuthProvider.CHESSCOM,
            provider_user_id=canonical.lower(),
            username=canonical,
        )


__all__ = [
    "CHESSCOM_API",
    "LICHESS_API",
    "PlatformClient",
    "PlatformError",
    "PlatformUser",
    "UserNotFoundError",
]
