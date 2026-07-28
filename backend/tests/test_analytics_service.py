"""Integration tests for `ProfileAnalyticsService.compute_snapshot` against a real,
transactional database — the window split, exclusion of unanalyzed games, and
versioned persistence are all about how loaded rows actually come back from Postgres,
which `test_analytics_metrics.py`'s in-memory objects don't exercise.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AnalyticsSettings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    Profile,
    ProfileAggregateSnapshot,
    ProfileKind,
    User,
)
from app.domain.analytics import ProfileAnalyticsService


def _settings(**overrides: object) -> AnalyticsSettings:
    return AnalyticsSettings(**overrides)  # type: ignore[arg-type]


async def _seed_profile(session: AsyncSession) -> uuid.UUID:
    """`Game.profile_id` and `ProfileAggregateSnapshot.profile_id` are real foreign
    keys — a snapshot's profile has to exist, unlike the in-memory objects
    `test_analytics_metrics.py` uses."""
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Test")
    session.add(profile)
    await session.flush()
    return profile.id


async def _seed_analyzed_game(
    session: AsyncSession,
    profile_id: uuid.UUID,
    *,
    accuracy: float,
    created_at: datetime,
    canonicalized: bool = True,
    with_analysis: bool = True,
    focus_color: GameColor | None = GameColor.WHITE,
    result: str = "1-0",
) -> Game:
    game = Game(
        profile_id=profile_id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "Player", "Black": "Opponent", "Result": result},
        raw_pgn_path="pgn/test.pgn",
        canonicalized_at=created_at if canonicalized else None,
        focus_color=focus_color,
        created_at=created_at,
    )
    session.add(game)
    await session.flush()

    if with_analysis:
        analysis = GameAnalysis(
            game_id=game.id,
            analysis_version="test",
            engine_depth=12,
            summary={
                "total_moves": 10,
                "counts": {"best": 10},
                "accuracy": accuracy,
                "critical_moments": 1,
            },
            created_at=created_at,
        )
        session.add(analysis)
        await session.flush()

    return game


class TestComputeSnapshot:
    async def test_no_games_yields_an_empty_snapshot(self, db_session: AsyncSession) -> None:
        profile_id = await _seed_profile(db_session)
        service = ProfileAnalyticsService(db_session, _settings())

        snapshot = await service.compute_snapshot(profile_id, window_size=10)

        assert snapshot.games_included == 0
        assert snapshot.sufficient_sample is False
        assert snapshot.metrics["accuracy"] == {"current": None, "previous": None, "delta": None}

    async def test_excludes_games_without_completed_analysis(
        self, db_session: AsyncSession
    ) -> None:
        profile_id = await _seed_profile(db_session)
        now = datetime.now(UTC)
        await _seed_analyzed_game(db_session, profile_id, accuracy=90.0, created_at=now)
        # Canonicalized but the background analysis job hasn't finished yet.
        await _seed_analyzed_game(
            db_session, profile_id, accuracy=0.0, created_at=now, with_analysis=False
        )
        # Never canonicalized at all.
        await _seed_analyzed_game(
            db_session, profile_id, accuracy=0.0, created_at=now, canonicalized=False
        )

        service = ProfileAnalyticsService(db_session, _settings())
        snapshot = await service.compute_snapshot(profile_id, window_size=10)

        assert snapshot.games_included == 1

    async def test_splits_current_and_previous_windows_by_recency(
        self, db_session: AsyncSession
    ) -> None:
        profile_id = await _seed_profile(db_session)
        base = datetime.now(UTC)
        # Oldest first: two "previous window" games at 80%, two "current window" games at
        # 100%, window_size=2.
        for offset, accuracy in [(4, 80.0), (3, 80.0), (2, 100.0), (1, 100.0)]:
            await _seed_analyzed_game(
                db_session,
                profile_id,
                accuracy=accuracy,
                created_at=base - timedelta(minutes=offset),
            )

        service = ProfileAnalyticsService(db_session, _settings())
        snapshot = await service.compute_snapshot(profile_id, window_size=2)

        assert snapshot.games_included == 2
        assert snapshot.metrics["accuracy"]["current"] == 100.0
        assert snapshot.metrics["accuracy"]["previous"] == 80.0
        assert snapshot.metrics["accuracy"]["delta"] == 20.0

    async def test_sufficient_sample_flag(self, db_session: AsyncSession) -> None:
        profile_id = await _seed_profile(db_session)
        now = datetime.now(UTC)
        for i in range(3):
            await _seed_analyzed_game(
                db_session, profile_id, accuracy=90.0, created_at=now - timedelta(minutes=i)
            )

        settings = _settings(analytics_min_games_for_trend=5)
        service = ProfileAnalyticsService(db_session, settings)
        snapshot = await service.compute_snapshot(profile_id, window_size=10)

        assert snapshot.games_included == 3
        assert snapshot.sufficient_sample is False

    async def test_each_call_persists_a_new_versioned_row(self, db_session: AsyncSession) -> None:
        profile_id = await _seed_profile(db_session)
        await _seed_analyzed_game(
            db_session, profile_id, accuracy=90.0, created_at=datetime.now(UTC)
        )

        service = ProfileAnalyticsService(db_session, _settings())
        first = await service.compute_snapshot(profile_id, window_size=10)
        second = await service.compute_snapshot(profile_id, window_size=10)

        assert first.id != second.id
        assert first.snapshot_version and second.snapshot_version

        rows = await db_session.execute(
            select(ProfileAggregateSnapshot).where(
                ProfileAggregateSnapshot.profile_id == profile_id
            )
        )
        assert len(list(rows.scalars().all())) == 2

    async def test_scoped_to_the_given_profile(self, db_session: AsyncSession) -> None:
        profile_a = await _seed_profile(db_session)
        profile_b = await _seed_profile(db_session)
        await _seed_analyzed_game(
            db_session, profile_a, accuracy=90.0, created_at=datetime.now(UTC)
        )
        await _seed_analyzed_game(
            db_session, profile_b, accuracy=50.0, created_at=datetime.now(UTC)
        )

        service = ProfileAnalyticsService(db_session, _settings())
        snapshot = await service.compute_snapshot(profile_a, window_size=10)

        assert snapshot.games_included == 1
        assert snapshot.metrics["accuracy"]["current"] == 90.0
