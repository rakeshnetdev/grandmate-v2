"""Profile listing, ownership checks, and the study-profile fallback (Phase 8b, D-021,
ADR-0016).

`SELF` and the study profile are both created eagerly at account creation
(`AuthService._create_account`) — `get_or_create_study_profile`'s create path exists only
as a defensive fallback for accounts created before Phase 8b shipped, same reasoning as
`AuthService._self_profile`'s own fallback for `SELF`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile, ProfileKind, ProfileSource


async def list_profiles(session: AsyncSession, user_id: uuid.UUID) -> list[Profile]:
    """Every profile the user owns, self first."""
    result = await session.execute(select(Profile).where(Profile.owner_user_id == user_id))
    profiles = list(result.scalars().all())
    profiles.sort(key=lambda p: p.kind != ProfileKind.SELF)
    return profiles


async def get_owned_profile(
    session: AsyncSession, user_id: uuid.UUID, profile_id: uuid.UUID
) -> Profile | None:
    """A specific profile, only if the caller owns it. `None` for someone else's profile
    or a nonexistent id — callers map both to the same 404, never distinguishing "not
    found" from "not yours"."""
    profile = await session.get(Profile, profile_id)
    if profile is None or profile.owner_user_id != user_id:
        return None
    return profile


async def get_or_create_study_profile(session: AsyncSession, user_id: uuid.UUID) -> Profile:
    result = await session.execute(
        select(Profile).where(
            Profile.owner_user_id == user_id, Profile.kind == ProfileKind.OPPONENT
        )
    )
    profile = result.scalars().first()
    if profile is not None:
        return profile

    profile = Profile(owner_user_id=user_id, kind=ProfileKind.OPPONENT, display_name="Study games")
    session.add(profile)
    await session.flush()
    return profile


async def get_linked_usernames(session: AsyncSession, profile_id: uuid.UUID) -> list[str]:
    result = await session.execute(
        select(ProfileSource.source_username).where(ProfileSource.profile_id == profile_id)
    )
    return list(result.scalars().all())


__all__ = [
    "get_linked_usernames",
    "get_or_create_study_profile",
    "get_owned_profile",
    "list_profiles",
]
