"""Session tokens.

A signed JWT carrying the user id and nothing else. Everything about the user is looked
up from the database on each request, so a token cannot go stale or carry a permission
that has since been revoked.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import IdentitySettings

ALGORITHM = "HS256"
COOKIE_NAME = "grandmate_session"


class InvalidSessionError(Exception):
    """The token is missing, malformed, expired, or not signed by us."""


@dataclass(frozen=True)
class SessionToken:
    value: str
    expires_at: datetime


def issue_session(user_id: uuid.UUID, settings: IdentitySettings) -> SessionToken:
    """Mint a session token for a user."""
    secret = settings.session_jwt_secret.get_secret_value()
    if not secret:
        # Signing with an empty key would produce tokens anyone could forge. Fail loudly.
        raise InvalidSessionError("SESSION_JWT_SECRET is not configured")

    expires_at = datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)
    payload = {"sub": str(user_id), "exp": expires_at, "iat": datetime.now(UTC)}
    return SessionToken(
        value=jwt.encode(payload, secret, algorithm=ALGORITHM), expires_at=expires_at
    )


def read_session(token: str, settings: IdentitySettings) -> uuid.UUID:
    """Return the user id in a token, or raise :class:`InvalidSessionError`.

    Every failure mode collapses to one exception type on purpose: telling a caller
    *why* a token was rejected helps an attacker more than it helps a user.
    """
    secret = settings.session_jwt_secret.get_secret_value()
    if not secret:
        raise InvalidSessionError("SESSION_JWT_SECRET is not configured")

    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidSessionError("Invalid session") from exc


__all__ = [
    "ALGORITHM",
    "COOKIE_NAME",
    "InvalidSessionError",
    "SessionToken",
    "issue_session",
    "read_session",
]
