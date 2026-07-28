"""Resolves which profile a request should be scoped to (Phase 8b, D-021, ADR-0016).

Every route that reads per-profile data (`games`, `analysis`, `patterns`, `analytics`)
accepts an optional `profile_id` query param so a caller can view either their own SELF
profile (the default) or their study profile — never anyone else's. Ownership is enforced
here, once, rather than duplicated per route.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import CurrentLoginDep
from app.api.dependencies.db import DbSessionDep
from app.domain.profiles import get_owned_profile


async def get_scoped_profile_id(
    current: CurrentLoginDep,
    session: DbSessionDep,
    profile_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """The profile id a request should read against: ``profile_id`` if given and owned
    by the caller, otherwise the caller's own SELF profile. A ``profile_id`` that exists
    but belongs to someone else 404s the same as one that doesn't exist at all — see
    `domain.profiles.get_owned_profile`.
    """
    if profile_id is None:
        return current.profile.id

    profile = await get_owned_profile(session, current.user.id, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile.id


ScopedProfileIdDep = Annotated[uuid.UUID, Depends(get_scoped_profile_id)]

__all__ = ["ScopedProfileIdDep", "get_scoped_profile_id"]
