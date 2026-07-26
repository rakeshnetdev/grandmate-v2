"""AuthService unit tests.

The platform lookup is faked rather than hitting Lichess or Chess.com, so these tests are
hermetic and exercise only the account-bootstrap logic that belongs to this service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditAction,
    AuditEvent,
    AuthProvider,
    GameSource,
    ProfileKind,
    ProfileSource,
)
from app.domain.auth import AuthService
from app.integrations.platforms import PlatformUser, UserNotFoundError


@dataclass
class _FakePlatformClient:
    """Stands in for ``PlatformClient``: returns a fixed user, or raises not-found."""

    known: dict[tuple[AuthProvider, str], PlatformUser]

    async def fetch_user(self, provider: AuthProvider, username: str) -> PlatformUser:
        key = (provider, username.strip().lower())
        if key not in self.known:
            raise UserNotFoundError(f"No such user: {username!r}")
        return self.known[key]


def _client(*users: PlatformUser) -> _FakePlatformClient:
    return _FakePlatformClient({(u.provider, u.username.lower()): u for u in users})


class TestLoginCreatesAccount:
    async def test_first_login_creates_user_identity_profile_and_source(
        self, db_session: AsyncSession
    ) -> None:
        platform_user = PlatformUser(
            provider=AuthProvider.LICHESS, provider_user_id="42", username="Magnus"
        )
        service = AuthService(db_session, _client(platform_user))

        result = await service.login(AuthProvider.LICHESS, "magnus")

        assert result.created is True
        assert result.identity.provider_user_id == "42"
        assert result.identity.provider_username == "Magnus"
        assert result.identity.verified is False
        assert result.identity.verification_method == "username_claim"
        assert result.profile.kind is ProfileKind.SELF
        assert result.profile.display_name == "Magnus"

        sources = (
            (
                await db_session.execute(
                    select(ProfileSource).where(ProfileSource.profile_id == result.profile.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(sources) == 1
        assert sources[0].source is GameSource.LICHESS
        assert sources[0].verified is False

    async def test_first_login_records_audit_events(self, db_session: AsyncSession) -> None:
        platform_user = PlatformUser(
            provider=AuthProvider.CHESSCOM, provider_user_id="hikaru", username="Hikaru"
        )
        service = AuthService(db_session, _client(platform_user))

        result = await service.login(AuthProvider.CHESSCOM, "hikaru")

        events = (
            (
                await db_session.execute(
                    select(AuditEvent).where(AuditEvent.actor_user_id == result.user.id)
                )
            )
            .scalars()
            .all()
        )
        actions = {event.action for event in events}
        assert AuditAction.PROFILE_CREATED in actions

    async def test_unknown_username_raises_not_found(self, db_session: AsyncSession) -> None:
        service = AuthService(db_session, _client())

        with pytest.raises(UserNotFoundError):
            await service.login(AuthProvider.LICHESS, "nobody")


class TestRepeatLogin:
    async def test_second_login_reuses_the_same_account(self, db_session: AsyncSession) -> None:
        platform_user = PlatformUser(
            provider=AuthProvider.LICHESS, provider_user_id="42", username="Magnus"
        )
        service = AuthService(db_session, _client(platform_user))

        first = await service.login(AuthProvider.LICHESS, "magnus")
        second = await service.login(AuthProvider.LICHESS, "magnus")

        assert second.created is False
        assert second.user.id == first.user.id
        assert second.profile.id == first.profile.id

    async def test_second_login_picks_up_a_renamed_display_name(
        self, db_session: AsyncSession
    ) -> None:
        """People rename themselves upstream; the stored username should track that."""
        original = PlatformUser(
            provider=AuthProvider.LICHESS, provider_user_id="42", username="OldName"
        )
        service = AuthService(db_session, _client(original))
        first = await service.login(AuthProvider.LICHESS, "OldName")
        assert first.identity.provider_username == "OldName"

        renamed = PlatformUser(
            provider=AuthProvider.LICHESS, provider_user_id="42", username="NewName"
        )
        service = AuthService(db_session, _client(renamed))
        second = await service.login(AuthProvider.LICHESS, "NewName")

        assert second.identity.provider_username == "NewName"
        assert second.identity.id == first.identity.id

    async def test_second_login_updates_last_login_at(self, db_session: AsyncSession) -> None:
        platform_user = PlatformUser(
            provider=AuthProvider.LICHESS, provider_user_id="42", username="Magnus"
        )
        service = AuthService(db_session, _client(platform_user))

        first = await service.login(AuthProvider.LICHESS, "magnus")
        assert first.user.last_login_at is not None
        second = await service.login(AuthProvider.LICHESS, "magnus")

        assert second.user.last_login_at is not None
        assert second.user.last_login_at >= first.user.last_login_at


class TestCurrent:
    async def test_current_resolves_a_logged_in_user(self, db_session: AsyncSession) -> None:
        platform_user = PlatformUser(
            provider=AuthProvider.LICHESS, provider_user_id="42", username="Magnus"
        )
        service = AuthService(db_session, _client(platform_user))
        logged_in = await service.login(AuthProvider.LICHESS, "magnus")

        current = await service.current(logged_in.user.id)

        assert current is not None
        assert current.user.id == logged_in.user.id
        assert current.identity.provider_user_id == "42"
        assert current.profile.id == logged_in.profile.id

    async def test_current_returns_none_for_an_unknown_user(self, db_session: AsyncSession) -> None:
        service = AuthService(db_session, _client())

        assert await service.current(uuid.uuid4()) is None
