"""Job and Game model tests.

Mirrors `test_models_identity.py`: assert the constraints that carry real meaning rather
than ones merely documented. The one that matters here is dedup — `games` must refuse a
second row for the same profile and content hash, since that constraint is the backstop
behind the application-level dedup check in `app/domain/imports`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game, GameSource, Job, JobKind, JobStatus, Profile, ProfileKind, User


async def _make_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    return user


async def _make_profile(session: AsyncSession, owner: User, name: str = "Me") -> Profile:
    profile = Profile(owner_user_id=owner.id, kind=ProfileKind.SELF, display_name=name)
    session.add(profile)
    await session.flush()
    return profile


class TestJob:
    async def test_job_defaults_to_pending(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)

        job = Job(kind=JobKind.PGN_IMPORT, profile_id=profile.id)
        db_session.add(job)
        await db_session.flush()

        assert job.status == JobStatus.PENDING
        assert job.progress == {}
        assert job.completed_at is None

    async def test_job_deleted_when_profile_is_deleted(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)
        job = Job(kind=JobKind.PGN_IMPORT, profile_id=profile.id)
        db_session.add(job)
        await db_session.flush()

        await db_session.delete(profile)
        await db_session.flush()

        # `select()`, not `session.get()`: the profile->job cascade is DB-level (FK
        # ondelete=CASCADE), not an ORM relationship, so the identity map still holds the
        # now-deleted Python object. A fresh query is what proves the DB row is gone.
        remaining = (await db_session.execute(select(Job))).scalars().all()
        assert remaining == []


class TestGame:
    async def test_a_profile_can_hold_many_distinct_games(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)
        db_session.add_all(
            [
                Game(
                    profile_id=profile.id,
                    source=GameSource.UPLOAD,
                    content_hash="hash-one",
                    headers={"White": "a", "Black": "b"},
                    raw_pgn_path=f"pgn/{profile.id}/hash-one.pgn",
                ),
                Game(
                    profile_id=profile.id,
                    source=GameSource.UPLOAD,
                    content_hash="hash-two",
                    headers={"White": "a", "Black": "c"},
                    raw_pgn_path=f"pgn/{profile.id}/hash-two.pgn",
                ),
            ]
        )
        await db_session.flush()

        games = (
            (await db_session.execute(select(Game).where(Game.profile_id == profile.id)))
            .scalars()
            .all()
        )
        assert {g.content_hash for g in games} == {"hash-one", "hash-two"}

    async def test_same_profile_cannot_store_the_same_content_hash_twice(
        self, db_session: AsyncSession
    ) -> None:
        """The DB-level backstop behind the application's dedup check."""
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)
        db_session.add(
            Game(
                profile_id=profile.id,
                source=GameSource.UPLOAD,
                content_hash="dupe-hash",
                headers={},
                raw_pgn_path=f"pgn/{profile.id}/dupe-hash.pgn",
            )
        )
        await db_session.flush()

        db_session.add(
            Game(
                profile_id=profile.id,
                source=GameSource.UPLOAD,
                content_hash="dupe-hash",
                headers={},
                raw_pgn_path=f"pgn/{profile.id}/dupe-hash-2.pgn",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_two_different_profiles_can_hold_the_same_content_hash(
        self, db_session: AsyncSession
    ) -> None:
        """Dedup is per-profile, not global — the same public game studied by two
        different profiles is not a duplicate of itself."""
        user = await _make_user(db_session)
        profile_a = await _make_profile(db_session, user, "A")
        profile_b = await _make_profile(db_session, user, "B")
        db_session.add_all(
            [
                Game(
                    profile_id=profile_a.id,
                    source=GameSource.UPLOAD,
                    content_hash="shared-hash",
                    headers={},
                    raw_pgn_path=f"pgn/{profile_a.id}/shared-hash.pgn",
                ),
                Game(
                    profile_id=profile_b.id,
                    source=GameSource.UPLOAD,
                    content_hash="shared-hash",
                    headers={},
                    raw_pgn_path=f"pgn/{profile_b.id}/shared-hash.pgn",
                ),
            ]
        )
        await db_session.flush()  # must not raise

    async def test_game_survives_its_job_being_deleted(self, db_session: AsyncSession) -> None:
        """`job_id` is `SET NULL`: a game is durable evidence, the job is just the
        transient record of how it arrived."""
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)
        job = Job(kind=JobKind.PGN_IMPORT, profile_id=profile.id)
        db_session.add(job)
        await db_session.flush()

        game = Game(
            profile_id=profile.id,
            job_id=job.id,
            source=GameSource.UPLOAD,
            content_hash="hash-x",
            headers={},
            raw_pgn_path=f"pgn/{profile.id}/hash-x.pgn",
        )
        db_session.add(game)
        await db_session.flush()
        game_id = game.id

        await db_session.delete(job)
        await db_session.flush()

        surviving = await db_session.get(Game, game_id)
        assert surviving is not None
        assert surviving.job_id is None

    async def test_game_deleted_when_profile_is_deleted(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        profile = await _make_profile(db_session, user)
        game = Game(
            profile_id=profile.id,
            source=GameSource.UPLOAD,
            content_hash="hash-y",
            headers={},
            raw_pgn_path=f"pgn/{profile.id}/hash-y.pgn",
        )
        db_session.add(game)
        await db_session.flush()

        await db_session.delete(profile)
        await db_session.flush()

        remaining = (await db_session.execute(select(Game))).scalars().all()
        assert remaining == []
