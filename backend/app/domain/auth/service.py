"""Login and account bootstrap.

**Security note, deliberate and temporary.** Login proves only that a username *exists*
on the platform, not that the person typing it owns the account. Anyone can log in as
anyone. That is an accepted trade-off for MVP — the product currently analyses public
games, so there is nothing private behind the door — but it must be closed before real
users or any private data. See ADR-0014.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models import (
    AuditAction,
    AuditEvent,
    AuthProvider,
    GameSource,
    Profile,
    ProfileKind,
    ProfileSource,
    User,
    UserIdentity,
)
from app.integrations.platforms import PlatformClient, PlatformUser


@dataclass(frozen=True)
class LoginResult:
    user: User
    profile: Profile
    identity: UserIdentity
    created: bool


class AuthService:
    """Resolves a platform username into a logged-in user."""

    def __init__(self, session: AsyncSession, platforms: PlatformClient) -> None:
        self._session = session
        self._platforms = platforms

    async def login(self, provider: AuthProvider, username: str) -> LoginResult:
        """Log in, creating the account on first sight.

        Raises ``UserNotFoundError`` if the platform does not know the username.
        """
        platform_user = await self._platforms.fetch_user(provider, username)

        identity = await self._find_identity(platform_user)
        if identity is not None:
            user = await self._session.get(User, identity.user_id)
            assert user is not None  # FK guarantees this
            # Keep the display name current — people rename themselves upstream.
            identity.provider_username = platform_user.username
            user.last_login_at = utc_now()
            profile = await self._self_profile(user)
            self._audit(AuditAction.USER_LOGIN, user, {"provider": provider.value})
            await self._session.flush()
            return LoginResult(user=user, profile=profile, identity=identity, created=False)

        return await self._create_account(platform_user)

    async def current(self, user_id: uuid.UUID) -> LoginResult | None:
        """Resolve a session's user id back into user, identity, and self profile.

        Returns ``None`` if the account no longer exists — a signed token can outlive its
        account, since a token is stateless and carries no reference to check against.

        Picks the first-linked identity to represent "who this session is". Fine for MVP,
        where signup creates exactly one identity; once a user can link a second provider,
        this needs the session to actually track which identity logged in.
        """
        user = await self._session.get(User, user_id)
        if user is None:
            return None

        identity_result = await self._session.execute(
            select(UserIdentity)
            .where(UserIdentity.user_id == user_id)
            .order_by(UserIdentity.created_at)
            .limit(1)
        )
        identity = identity_result.scalars().first()
        if identity is None:
            return None

        profile = await self._self_profile(user)
        return LoginResult(user=user, profile=profile, identity=identity, created=False)

    async def _find_identity(self, platform_user: PlatformUser) -> UserIdentity | None:
        result = await self._session.execute(
            select(UserIdentity).where(
                UserIdentity.provider == platform_user.provider,
                UserIdentity.provider_user_id == platform_user.provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _create_account(self, platform_user: PlatformUser) -> LoginResult:
        """First login: user, identity, self profile, and a game source, together.

        The profile and source are created here rather than lazily so that every user has
        somewhere for their games to land from the moment they exist.
        """
        user = User(last_login_at=utc_now())
        self._session.add(user)
        await self._session.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider=platform_user.provider,
            provider_user_id=platform_user.provider_user_id,
            provider_username=platform_user.username,
            # False: existence was checked, ownership was not. See the module docstring.
            verified=False,
            verification_method="username_claim",
        )
        profile = Profile(
            owner_user_id=user.id,
            kind=ProfileKind.SELF,
            display_name=platform_user.username,
        )
        self._session.add_all([identity, profile])
        await self._session.flush()

        self._session.add(
            ProfileSource(
                profile_id=profile.id,
                source=GameSource(platform_user.provider.value),
                source_username=platform_user.username,
                verified=False,
            )
        )
        self._audit(
            AuditAction.PROFILE_CREATED,
            user,
            {"provider": platform_user.provider.value, "username": platform_user.username},
        )
        await self._session.flush()

        return LoginResult(user=user, profile=profile, identity=identity, created=True)

    async def _self_profile(self, user: User) -> Profile:
        result = await self._session.execute(
            select(Profile).where(
                Profile.owner_user_id == user.id, Profile.kind == ProfileKind.SELF
            )
        )
        profile = result.scalars().first()
        if profile is not None:
            return profile

        # Defensive: an account without a self profile should be impossible, but a
        # missing profile must not make login fail.
        profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
        self._session.add(profile)
        await self._session.flush()
        return profile

    def _audit(self, action: AuditAction, user: User, metadata: dict[str, str]) -> None:
        self._session.add(
            AuditEvent(
                actor_user_id=user.id,
                action=action,
                subject_type="user",
                subject_id=user.id,
                event_metadata=metadata,
            )
        )


__all__ = ["AuthService", "LoginResult"]
