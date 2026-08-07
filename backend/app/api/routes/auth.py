"""Login, current user, logout.

Thin per the "routes delegate, they do not decide" rule: platform lookup lives in
``PlatformClient``, account bootstrap in ``AuthService``, token shape in
``app.domain.auth.session``. This module only translates between HTTP and those calls.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies.auth import CurrentLoginDep
from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.settings import SettingsDep
from app.domain.auth import COOKIE_NAME, AuthService, LoginResult, issue_session
from app.integrations.platforms import PlatformClient, PlatformError, UserNotFoundError
from app.schemas.auth import CurrentUser, LoginRequest, ProfileSummary

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_current_user(result: LoginResult) -> CurrentUser:
    return CurrentUser(
        id=result.user.id,
        provider=result.identity.provider,
        username=result.identity.provider_username,
        verified=result.identity.verified,
        profile=ProfileSummary(
            id=result.profile.id,
            display_name=result.profile.display_name,
            kind=result.profile.kind.value,
            default_persona=result.profile.default_persona.value,
        ),
    )


@dataclass(frozen=True)
class _SessionCookieAttrs:
    """The cookie attributes that must be identical when setting and when clearing.

    A browser only replaces a cookie when the attributes it is given match the ones it
    stored. A deletion that omits `Secure` or sends a different `SameSite` is ignored
    silently — no error, no warning, the user simply stays logged in. This type exists so
    the two call sites cannot drift: that drift is a real defect that shipped, where
    `delete_cookie` took Starlette's defaults (`SameSite=lax`, `secure=False`) while login
    issued `SameSite=none; Secure` in production, so cross-site logout never cleared
    anything.
    """

    secure: bool
    samesite: Literal["lax", "strict", "none"]
    path: str = "/"
    httponly: bool = True


def _session_cookie_attrs(settings: SettingsDep) -> _SessionCookieAttrs:
    samesite = settings.identity.session_cookie_samesite
    return _SessionCookieAttrs(
        # Secure requires HTTPS, which local development does not have. Production sets
        # APP_ENV=production and gets the real protection.
        #
        # `SameSite=None` is the one case where that is not a free choice: every browser
        # rejects such a cookie outright unless it is also Secure, so a cross-site
        # deployment that forgot HTTPS would drop the cookie silently rather than warn.
        # Forcing it here makes the pair impossible to get half-right.
        secure=settings.app.is_production or samesite == "none",
        samesite=samesite,
    )


def _set_session_cookie(response: Response, settings: SettingsDep, user_id: uuid.UUID) -> None:
    token = issue_session(user_id, settings.identity)
    attrs = _session_cookie_attrs(settings)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token.value,
        expires=token.expires_at,
        httponly=attrs.httponly,
        secure=attrs.secure,
        samesite=attrs.samesite,
        path=attrs.path,
    )


@router.post("/login", response_model=CurrentUser)
async def login(
    payload: LoginRequest,
    response: Response,
    session: DbSessionDep,
    settings: SettingsDep,
) -> CurrentUser:
    """Log in with a Lichess or Chess.com username.

    MVP trust level only: this proves the username exists on the platform, not that the
    caller owns it. See ADR-0014.
    """
    auth_service = AuthService(session, PlatformClient(settings.ingestion))
    try:
        result = await auth_service.login(payload.provider, payload.username)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PlatformError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    _set_session_cookie(response, settings, result.user.id)
    return _to_current_user(result)


@router.get("/me", response_model=CurrentUser)
async def me(current: CurrentLoginDep) -> CurrentUser:
    """The signed-in user, resolved from the session cookie."""
    return _to_current_user(current)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, settings: SettingsDep) -> None:
    """Clear the session cookie. Stateless tokens mean there is nothing to revoke server-side.

    Clears with the *same* attributes login set, via `_session_cookie_attrs` — a mismatch
    here is not an error the browser reports, it just leaves the session in place.
    """
    attrs = _session_cookie_attrs(settings)
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=attrs.httponly,
        secure=attrs.secure,
        samesite=attrs.samesite,
        path=attrs.path,
    )


__all__ = ["router"]
