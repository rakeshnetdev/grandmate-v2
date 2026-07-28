"""Profile listing (Phase 8b, D-021, ADR-0016).

Thin per the "routes delegate" rule: lookups live in `domain/profiles/queries.py`. Lets
the frontend build the "My games" / "Study games" toggle without hardcoding profile ids.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies.auth import CurrentLoginDep
from app.api.dependencies.db import DbSessionDep
from app.db.models import Profile
from app.domain.profiles import list_profiles
from app.schemas.profiles import ProfileSummary

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _to_summary(profile: Profile) -> ProfileSummary:
    return ProfileSummary(id=profile.id, kind=profile.kind.value, display_name=profile.display_name)


@router.get("", response_model=list[ProfileSummary])
async def list_my_profiles(current: CurrentLoginDep, session: DbSessionDep) -> list[ProfileSummary]:
    """Every profile the caller owns, self first."""
    profiles = await list_profiles(session, current.user.id)
    return [_to_summary(profile) for profile in profiles]


__all__ = ["router"]
