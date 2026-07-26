"""Current-user resolution from the session cookie.

Every failure mode here — missing cookie, malformed token, expired token, account since
deleted — collapses to the same 401. Distinguishing them in the response would tell a
caller more about *why* a token was rejected than a caller needs, and more than an
attacker probing the endpoint should get.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.settings import SettingsDep
from app.domain.auth import COOKIE_NAME, AuthService, InvalidSessionError, LoginResult, read_session
from app.integrations.platforms import PlatformClient

_UNAUTHORIZED = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def get_current_login(
    settings: SettingsDep,
    session: DbSessionDep,
    session_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> LoginResult:
    """The authenticated user, identity, and self profile — or a 401."""
    if session_token is None:
        raise _UNAUTHORIZED

    try:
        user_id = read_session(session_token, settings.identity)
    except InvalidSessionError as exc:
        raise _UNAUTHORIZED from exc

    auth_service = AuthService(session, PlatformClient(settings.ingestion))
    result = await auth_service.current(user_id)
    if result is None:
        raise _UNAUTHORIZED
    return result


CurrentLoginDep = Annotated[LoginResult, Depends(get_current_login)]

__all__ = ["CurrentLoginDep", "get_current_login"]
