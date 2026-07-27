"""ImportService orchestration tests: dedup, storage, job status, per-game rejections.

Uses the real transactional `db_session` fixture and a real `LocalStorage` pointed at a
pytest `tmp_path`, so these exercise the actual dedup query and actual file writes, not
mocks standing in for either.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import PatternSettings
from app.db.models import Game, GameSource, JobStatus, Profile, ProfileKind, User
from app.domain.imports import ImportResult, ImportService, SourceText, TooManyGamesError
from app.domain.patterns import load_opening_index
from app.integrations.storage import LocalStorage

# Built once for the whole module: real vendored dataset, no reason to reparse it per
# test. Phase 6's opening lookup and pattern settings are call-time `ingest()` arguments
# (see ImportService.ingest's own docstring for why), so every test needs them threaded
# through — `_ingest` below is what keeps that out of every individual test body.
_PATTERN_SETTINGS = PatternSettings()
_OPENING_INDEX = load_opening_index(_PATTERN_SETTINGS)


async def _ingest(
    service: ImportService, profile_id: uuid.UUID, sources: list[SourceText], *, max_games: int
) -> ImportResult:
    return await service.ingest(
        profile_id,
        sources,
        max_games=max_games,
        opening_index=_OPENING_INDEX,
        pattern_settings=_PATTERN_SETTINGS,
    )


GAME_A = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0
"""

GAME_B = """[Event "Test"]
[White "Carol"]
[Black "Dave"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


async def _make_profile(session: AsyncSession) -> Profile:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


class TestIngest:
    async def test_imports_a_single_game(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        service = ImportService(db_session, storage)

        result = await _ingest(
            service, profile.id, [SourceText(text=GAME_A, label="a.pgn")], max_games=10
        )
        job = result.job

        assert job.status == JobStatus.DONE
        assert job.progress["imported"] == 1
        assert job.progress["duplicates"] == 0
        assert job.progress["rejected"] == []
        assert job.completed_at is not None
        assert len(result.analysis_job_ids) == 1

        games = (await db_session.execute(select(Game))).scalars().all()
        assert len(games) == 1
        assert games[0].profile_id == profile.id
        assert games[0].source == GameSource.UPLOAD
        assert games[0].job_id == job.id
        assert await storage.exists(games[0].raw_pgn_path)

    async def test_imports_a_multi_game_file_as_n_games(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        """A batch is not a special mode — a file with two games produces two games."""
        profile = await _make_profile(db_session)
        service = ImportService(db_session, storage)

        result = await _ingest(
            service,
            profile.id,
            [SourceText(text=GAME_A + "\n" + GAME_B, label="batch.pgn")],
            max_games=10,
        )

        assert result.job.progress["imported"] == 2
        assert len(result.analysis_job_ids) == 2

    async def test_each_games_stored_pgn_contains_only_that_game(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        """Regression: storage previously held the whole source text under every game's
        key, so a multi-game file left both games' `raw_pgn_path` pointing at a blob
        containing both — no way to tell which was which."""
        profile = await _make_profile(db_session)
        service = ImportService(db_session, storage)

        await _ingest(
            service,
            profile.id,
            [SourceText(text=GAME_A + "\n" + GAME_B, label="batch.pgn")],
            max_games=10,
        )

        games = (await db_session.execute(select(Game).order_by(Game.created_at))).scalars().all()
        assert len(games) == 2
        contents = {g.headers["White"]: (await storage.get(g.raw_pgn_path)).decode() for g in games}
        assert "Carol" not in contents["Alice"]
        assert "Alice" not in contents["Carol"]

    async def test_reimporting_the_same_game_is_flagged_as_duplicate_not_error(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        service = ImportService(db_session, storage)

        await _ingest(service, profile.id, [SourceText(text=GAME_A, label="a.pgn")], max_games=10)
        second_result = await _ingest(
            service, profile.id, [SourceText(text=GAME_A, label="a-again.pgn")], max_games=10
        )
        second_job = second_result.job

        assert second_job.status == JobStatus.DONE
        assert second_job.progress["imported"] == 0
        assert second_job.progress["duplicates"] == 1
        assert second_job.progress["rejected"][0]["reason"] == "duplicate_game"
        assert second_result.analysis_job_ids == []

    async def test_malformed_game_is_reported_but_does_not_fail_the_job(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        service = ImportService(db_session, storage)
        malformed = GAME_A.replace("3. Bb5 1-0", "3. Qxd8 1-0")

        result = await _ingest(
            service,
            profile.id,
            [SourceText(text=malformed + "\n" + GAME_B, label="mixed.pgn")],
            max_games=10,
        )
        job = result.job

        assert job.status == JobStatus.DONE
        assert job.progress["imported"] == 1
        assert len(job.progress["rejected"]) == 1
        assert job.progress["rejected"][0]["reason"] == "malformed_pgn"

    async def test_submission_over_the_limit_fails_the_job_and_writes_nothing(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        service = ImportService(db_session, storage)
        batch = "\n".join([GAME_A, GAME_B] * 3)  # 6 games

        with pytest.raises(TooManyGamesError):
            await _ingest(
                service, profile.id, [SourceText(text=batch, label="big.pgn")], max_games=5
            )

        games = (await db_session.execute(select(Game))).scalars().all()
        assert games == []

    async def test_dedup_is_scoped_per_profile(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile_a = await _make_profile(db_session)
        profile_b = await _make_profile(db_session)
        service = ImportService(db_session, storage)

        await _ingest(service, profile_a.id, [SourceText(text=GAME_A, label="a.pgn")], max_games=10)
        result_b = await _ingest(
            service, profile_b.id, [SourceText(text=GAME_A, label="a.pgn")], max_games=10
        )

        assert result_b.job.progress["imported"] == 1
        assert result_b.job.progress["duplicates"] == 0


class TestJobLookup:
    async def test_get_job_is_scoped_to_the_owning_profile(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        owner = await _make_profile(db_session)
        stranger = await _make_profile(db_session)
        service = ImportService(db_session, storage)
        result = await _ingest(
            service, owner.id, [SourceText(text=GAME_A, label="a.pgn")], max_games=10
        )
        job = result.job

        assert (await service.get_job(job.id, owner.id)) is not None
        assert (await service.get_job(job.id, stranger.id)) is None

    async def test_list_jobs_returns_only_the_profiles_own_jobs_most_recent_first(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        other = await _make_profile(db_session)
        service = ImportService(db_session, storage)

        await _ingest(service, other.id, [SourceText(text=GAME_A, label="a.pgn")], max_games=10)
        first = await _ingest(
            service, profile.id, [SourceText(text=GAME_A, label="a.pgn")], max_games=10
        )
        second = await _ingest(
            service, profile.id, [SourceText(text=GAME_B, label="b.pgn")], max_games=10
        )

        jobs = await service.list_jobs(profile.id)

        assert [job.id for job in jobs] == [second.job.id, first.job.id]
