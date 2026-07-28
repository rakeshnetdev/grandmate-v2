"""Phase 8b (D-021, ADR-0016): per-game routing between a profile's own SELF import and
its study profile, and dedup scoped to wherever a game actually lands.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import PatternSettings
from app.db.models import Game, Job, JobKind, Profile, ProfileKind, User
from app.domain.imports import ImportResult, ImportService, SourceText
from app.domain.patterns import load_opening_index
from app.integrations.storage import LocalStorage

_PATTERN_SETTINGS = PatternSettings()
_OPENING_INDEX = load_opening_index(_PATTERN_SETTINGS)

OWN_GAME = """[Event "Test"]
[White "MyHandle"]
[Black "SomeOpponent"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0
"""

UNOWNED_GAME = """[Event "Test"]
[White "Carlsen,Magnus"]
[Black "Nilssen,J"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""

SELF_PLAY_GAME = """[Event "Test"]
[White "MyHandle"]
[Black "MyHandle"]
[Result "1/2-1/2"]

1. e4 e5 1/2-1/2
"""


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


async def _make_profile_pair(session: AsyncSession) -> tuple[Profile, Profile]:
    user = User()
    session.add(user)
    await session.flush()
    self_profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    study_profile = Profile(
        owner_user_id=user.id, kind=ProfileKind.OPPONENT, display_name="Study games"
    )
    session.add_all([self_profile, study_profile])
    await session.flush()
    return self_profile, study_profile


async def _ingest(
    service: ImportService,
    self_profile: Profile,
    study_profile: Profile,
    sources: list[SourceText],
    *,
    self_linked_usernames: list[str],
) -> ImportResult:
    return await service.ingest(
        self_profile_id=self_profile.id,
        study_profile_id=study_profile.id,
        self_linked_usernames=self_linked_usernames,
        sources=sources,
        max_games=10,
        opening_index=_OPENING_INDEX,
        pattern_settings=_PATTERN_SETTINGS,
    )


class TestProfileRouting:
    async def test_a_matching_game_lands_in_self(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        self_profile, study_profile = await _make_profile_pair(db_session)
        service = ImportService(db_session, storage)

        await _ingest(
            service,
            self_profile,
            study_profile,
            [SourceText(text=OWN_GAME, label="a.pgn")],
            self_linked_usernames=["MyHandle"],
        )

        games = (await db_session.execute(select(Game))).scalars().all()
        assert len(games) == 1
        assert games[0].profile_id == self_profile.id

    async def test_a_non_matching_game_lands_in_study(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        self_profile, study_profile = await _make_profile_pair(db_session)
        service = ImportService(db_session, storage)

        await _ingest(
            service,
            self_profile,
            study_profile,
            [SourceText(text=UNOWNED_GAME, label="a.pgn")],
            self_linked_usernames=["MyHandle"],
        )

        games = (await db_session.execute(select(Game))).scalars().all()
        assert len(games) == 1
        assert games[0].profile_id == study_profile.id

    async def test_a_mixed_batch_splits_across_both_profiles(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        self_profile, study_profile = await _make_profile_pair(db_session)
        service = ImportService(db_session, storage)

        await _ingest(
            service,
            self_profile,
            study_profile,
            [SourceText(text=OWN_GAME + "\n" + UNOWNED_GAME, label="batch.pgn")],
            self_linked_usernames=["MyHandle"],
        )

        games = (await db_session.execute(select(Game))).scalars().all()
        assert len(games) == 2
        profile_ids = {g.profile_id for g in games}
        assert profile_ids == {self_profile.id, study_profile.id}

    async def test_ambiguous_self_play_still_routes_to_self(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        """Both sides matching the linked username (self-play) is still the account's
        own game — only a game matching *neither* side belongs in the study profile."""
        self_profile, study_profile = await _make_profile_pair(db_session)
        service = ImportService(db_session, storage)

        await _ingest(
            service,
            self_profile,
            study_profile,
            [SourceText(text=SELF_PLAY_GAME, label="a.pgn")],
            self_linked_usernames=["MyHandle"],
        )

        games = (await db_session.execute(select(Game))).scalars().all()
        assert len(games) == 1
        assert games[0].profile_id == self_profile.id

    async def test_no_linked_usernames_defaults_everything_to_self(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        """An account with nothing to check against keeps today's pre-Phase-8b
        behaviour rather than silently routing everything away from self."""
        self_profile, study_profile = await _make_profile_pair(db_session)
        service = ImportService(db_session, storage)

        await _ingest(
            service,
            self_profile,
            study_profile,
            [SourceText(text=UNOWNED_GAME, label="a.pgn")],
            self_linked_usernames=[],
        )

        games = (await db_session.execute(select(Game))).scalars().all()
        assert len(games) == 1
        assert games[0].profile_id == self_profile.id

    async def test_dedup_is_scoped_to_the_resolved_profile_not_always_self(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        self_profile, study_profile = await _make_profile_pair(db_session)
        service = ImportService(db_session, storage)

        first = await _ingest(
            service,
            self_profile,
            study_profile,
            [SourceText(text=UNOWNED_GAME, label="a.pgn")],
            self_linked_usernames=["MyHandle"],
        )
        second = await _ingest(
            service,
            self_profile,
            study_profile,
            [SourceText(text=UNOWNED_GAME, label="a-again.pgn")],
            self_linked_usernames=["MyHandle"],
        )

        assert first.job.progress["imported"] == 1
        assert second.job.progress["imported"] == 0
        assert second.job.progress["duplicates"] == 1

    async def test_analysis_job_is_scoped_to_the_games_own_profile(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        self_profile, study_profile = await _make_profile_pair(db_session)
        service = ImportService(db_session, storage)

        await _ingest(
            service,
            self_profile,
            study_profile,
            [SourceText(text=UNOWNED_GAME, label="a.pgn")],
            self_linked_usernames=["MyHandle"],
        )

        analysis_jobs = (
            (await db_session.execute(select(Job).where(Job.kind == JobKind.ENGINE_ANALYSIS)))
            .scalars()
            .all()
        )
        assert len(analysis_jobs) == 1
        assert analysis_jobs[0].profile_id == study_profile.id
