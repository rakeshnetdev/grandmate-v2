"""Identity and permission model tests.

These assert the constraints that carry security meaning. A unique constraint that is
merely documented is not a constraint — the database has to refuse the write.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditAction,
    AuditEvent,
    AuthProvider,
    GameSource,
    Persona,
    Profile,
    ProfileKind,
    ProfileRelationship,
    ProfileSource,
    RelationshipRole,
    User,
    UserIdentity,
)


async def _make_user(session: AsyncSession, email: str | None = None) -> User:
    user = User(email=email)
    session.add(user)
    await session.flush()
    return user


async def _make_profile(session: AsyncSession, owner: User, name: str = "Me") -> Profile:
    profile = Profile(owner_user_id=owner.id, kind=ProfileKind.SELF, display_name=name)
    session.add(profile)
    await session.flush()
    return profile


class TestUserIdentity:
    async def test_user_can_hold_both_providers(self, db_session: AsyncSession) -> None:
        """The whole reason for a separate identities table (ADR-0007)."""
        user = await _make_user(db_session)
        db_session.add_all(
            [
                UserIdentity(
                    user_id=user.id,
                    provider=AuthProvider.LICHESS,
                    provider_user_id="li-1",
                    provider_username="player",
                ),
                UserIdentity(
                    user_id=user.id,
                    provider=AuthProvider.CHESSCOM,
                    provider_user_id="cc-1",
                    provider_username="player",
                ),
            ]
        )
        await db_session.flush()

        identities = (
            (await db_session.execute(select(UserIdentity).where(UserIdentity.user_id == user.id)))
            .scalars()
            .all()
        )
        assert {i.provider for i in identities} == {AuthProvider.LICHESS, AuthProvider.CHESSCOM}

    async def test_one_platform_account_cannot_map_to_two_users(
        self, db_session: AsyncSession
    ) -> None:
        """Without this, two people could each claim the same Chess.com username."""
        first = await _make_user(db_session)
        second = await _make_user(db_session)

        db_session.add(
            UserIdentity(
                user_id=first.id,
                provider=AuthProvider.CHESSCOM,
                provider_user_id="magnus",
                provider_username="magnus",
            )
        )
        await db_session.flush()

        db_session.add(
            UserIdentity(
                user_id=second.id,
                provider=AuthProvider.CHESSCOM,
                provider_user_id="magnus",
                provider_username="magnus",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_same_id_on_different_providers_is_allowed(
        self, db_session: AsyncSession
    ) -> None:
        """Uniqueness is per provider — the two namespaces are unrelated."""
        user = await _make_user(db_session)
        db_session.add_all(
            [
                UserIdentity(
                    user_id=user.id,
                    provider=AuthProvider.LICHESS,
                    provider_user_id="same",
                    provider_username="same",
                ),
                UserIdentity(
                    user_id=user.id,
                    provider=AuthProvider.CHESSCOM,
                    provider_user_id="same",
                    provider_username="same",
                ),
            ]
        )

        await db_session.flush()  # must not raise

    async def test_deleting_a_user_removes_their_identities(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        db_session.add(
            UserIdentity(
                user_id=user.id,
                provider=AuthProvider.LICHESS,
                provider_user_id="li-9",
                provider_username="x",
            )
        )
        await db_session.flush()

        await db_session.delete(user)
        await db_session.flush()

        remaining = (await db_session.execute(select(UserIdentity))).scalars().all()
        assert remaining == []


class TestProfile:
    async def test_default_persona_is_self_learner(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)

        assert profile.default_persona is Persona.SELF_LEARNER

    async def test_a_user_may_hold_several_profiles(self, db_session: AsyncSession) -> None:
        """One account, several players — the coach and parent cases."""
        user = await _make_user(db_session)
        await _make_profile(db_session, user, "Me")
        db_session.add(
            Profile(owner_user_id=user.id, kind=ProfileKind.CHILD, display_name="My kid")
        )
        await db_session.flush()

        profiles = (
            (await db_session.execute(select(Profile).where(Profile.owner_user_id == user.id)))
            .scalars()
            .all()
        )
        assert len(profiles) == 2

    async def test_source_link_is_unique(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)

        for _ in range(2):
            db_session.add(
                ProfileSource(
                    profile_id=profile.id,
                    source=GameSource.CHESSCOM,
                    source_username="hikaru",
                )
            )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_profile_source_is_unverified_by_default(self, db_session: AsyncSession) -> None:
        """A typed username is a claim. It must not default to looking proven."""
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)
        source = ProfileSource(
            profile_id=profile.id, source=GameSource.CHESSCOM, source_username="someone"
        )
        db_session.add(source)
        await db_session.flush()

        assert source.verified is False


class TestProfileRelationship:
    async def test_grant_is_active_until_revoked(self, db_session: AsyncSession) -> None:
        owner = await _make_user(db_session)
        coach = await _make_user(db_session)
        profile = await _make_profile(db_session, owner, "Student")

        grant = ProfileRelationship(
            viewer_user_id=coach.id,
            subject_profile_id=profile.id,
            role=RelationshipRole.COACH,
        )
        db_session.add(grant)
        await db_session.flush()

        assert grant.is_active is True

    async def test_revocation_is_soft(self, db_session: AsyncSession) -> None:
        """The row survives revocation — an audit needs to see access that once existed."""
        from app.db.base import utc_now

        owner = await _make_user(db_session)
        coach = await _make_user(db_session)
        profile = await _make_profile(db_session, owner, "Student")
        grant = ProfileRelationship(
            viewer_user_id=coach.id,
            subject_profile_id=profile.id,
            role=RelationshipRole.COACH,
        )
        db_session.add(grant)
        await db_session.flush()

        grant.revoked_at = utc_now()
        await db_session.flush()

        assert grant.is_active is False
        assert (await db_session.execute(select(ProfileRelationship))).scalars().all() != []

    async def test_duplicate_grant_is_rejected(self, db_session: AsyncSession) -> None:
        owner = await _make_user(db_session)
        coach = await _make_user(db_session)
        profile = await _make_profile(db_session, owner, "Student")

        for _ in range(2):
            db_session.add(
                ProfileRelationship(
                    viewer_user_id=coach.id,
                    subject_profile_id=profile.id,
                    role=RelationshipRole.COACH,
                )
            )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_same_viewer_may_hold_different_roles(self, db_session: AsyncSession) -> None:
        """A parent who also coaches is one person with two distinct grants."""
        owner = await _make_user(db_session)
        viewer = await _make_user(db_session)
        profile = await _make_profile(db_session, owner, "Child")

        db_session.add_all(
            [
                ProfileRelationship(
                    viewer_user_id=viewer.id,
                    subject_profile_id=profile.id,
                    role=RelationshipRole.PARENT,
                ),
                ProfileRelationship(
                    viewer_user_id=viewer.id,
                    subject_profile_id=profile.id,
                    role=RelationshipRole.COACH,
                ),
            ]
        )

        await db_session.flush()  # must not raise


class TestAuditEvent:
    async def test_event_records_actor_and_action(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        event = AuditEvent(
            actor_user_id=user.id,
            action=AuditAction.PROFILE_VIEWED,
            subject_type="profile",
            subject_id=uuid.uuid4(),
            event_metadata={"reason": "coach review"},
        )
        db_session.add(event)
        await db_session.flush()

        assert event.action is AuditAction.PROFILE_VIEWED
        assert event.event_metadata["reason"] == "coach review"

    async def test_actor_may_be_null_for_failed_logins(self, db_session: AsyncSession) -> None:
        """A failed login has no established user, but must still be recordable."""
        event = AuditEvent(action=AuditAction.USER_LOGIN, event_metadata={"outcome": "rejected"})
        db_session.add(event)

        await db_session.flush()  # must not raise

    async def test_event_survives_deletion_of_its_actor(self, db_session: AsyncSession) -> None:
        """`SET NULL`, not cascade: deleting an account must not erase the audit trail."""
        user = await _make_user(db_session)
        db_session.add(AuditEvent(actor_user_id=user.id, action=AuditAction.USER_LOGIN))
        await db_session.flush()

        await db_session.delete(user)
        await db_session.flush()

        events = (await db_session.execute(select(AuditEvent))).scalars().all()
        assert len(events) == 1
        assert events[0].actor_user_id is None
