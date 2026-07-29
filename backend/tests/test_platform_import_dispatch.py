"""`run_platform_import_job` tests (Phase 14) — the platform-sync analogue of
`test_import_analysis_dispatch_integration.py`'s real-session-factory pattern, but
exercising the ingestion/dedup path with a fake connector standing in for
Lichess/Chess.com, rather than a real engine.

A real, independently-committing session factory is used rather than the shared
`db_session` fixture for the same reason that test documents: this function opens its
*own* session (`session_scope`) exactly as it would from a `BackgroundTasks` callback,
and a single always-rolled-back transaction would make that meaningless.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.models import Game, GameSource, Job, JobKind, JobStatus, Profile, ProfileKind, User
from app.db.session import session_scope
from app.domain.imports.connectors import ConnectorError
from app.domain.imports.dispatch import run_platform_import_job
from app.domain.patterns import load_opening_index
from app.integrations.storage import LocalStorage

pytestmark = pytest.mark.asyncio

GAME_A = (
    '[Event "Test"]\n[White "hikaru"]\n[Black "Bob"]\n[Result "1-0"]\n\n'
    "1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0\n"
)
GAME_B = (
    '[Event "Test"]\n[White "Carol"]\n[Black "hikaru"]\n[Result "0-1"]\n\n1. d4 d5 2. c4 e6 0-1\n'
)


class _FakeConnector:
    def __init__(self, *, pgn_text: str = "", error: Exception | None = None) -> None:
        self._pgn_text = pgn_text
        self._error = error
        self.calls: list[tuple[str, int]] = []

    async def fetch_recent_games_pgn(self, username: str, max_games: int) -> str:
        self.calls.append((username, max_games))
        if self._error is not None:
            raise self._error
        return self._pgn_text


@pytest_asyncio.fixture
async def real_session_factory(
    db_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Same cleanup rationale as `test_import_analysis_dispatch_integration.py`'s
    fixture of the same name: `db_schema` builds the schema once per pytest session, so
    a real commit here must be cleaned up for tests that run afterwards. Deleting
    `User` alone cascades to `Profile`/`ProfileSource`/`Job`/`Game`."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    async with session_scope(factory) as session:
        await session.execute(delete(User))


@pytest_asyncio.fixture
async def profile_id(real_session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_scope(real_session_factory) as session:
        user = User()
        session.add(user)
        await session.flush()
        profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
        session.add(profile)
        await session.flush()
        return profile.id


async def _create_pending_job(
    session_factory: async_sessionmaker[AsyncSession], profile_id: uuid.UUID
) -> uuid.UUID:
    async with session_scope(session_factory) as session:
        job = Job(kind=JobKind.PGN_IMPORT, profile_id=profile_id, status=JobStatus.PENDING)
        session.add(job)
        await session.flush()
        return job.id


async def _run(
    job_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    connector: _FakeConnector,
    *,
    settings: Settings | None = None,
    tmp_path,
) -> None:
    resolved_settings = settings or Settings()
    await run_platform_import_job(
        job_id,
        provider=GameSource.LICHESS,
        username="hikaru",
        window=10,
        session_factory=session_factory,
        settings=resolved_settings,
        storage=LocalStorage(tmp_path),
        opening_index=load_opening_index(resolved_settings.patterns),
        connector_factory=lambda _provider, _settings: connector,
    )


class TestRunPlatformImportJob:
    async def test_a_successful_sync_ingests_games_with_the_right_source_and_completes_the_job(
        self,
        real_session_factory: async_sessionmaker[AsyncSession],
        profile_id: uuid.UUID,
        tmp_path,
    ) -> None:
        job_id = await _create_pending_job(real_session_factory, profile_id)
        connector = _FakeConnector(pgn_text=GAME_A + "\n" + GAME_B)

        await _run(job_id, real_session_factory, connector, tmp_path=tmp_path)

        assert connector.calls == [("hikaru", 10)]
        async with session_scope(real_session_factory) as session:
            job = await session.get(Job, job_id)
            assert job is not None
            assert job.status == JobStatus.DONE
            assert job.progress["imported"] == 2

            games = (
                (await session.execute(select(Game).where(Game.profile_id == profile_id)))
                .scalars()
                .all()
            )
            assert len(games) == 2
            # Not GameSource.UPLOAD — the bug this dataclass field fixes.
            assert all(g.source == GameSource.LICHESS for g in games)

            analysis_jobs = (
                (await session.execute(select(Job).where(Job.kind == JobKind.ENGINE_ANALYSIS)))
                .scalars()
                .all()
            )
            assert len(analysis_jobs) == 2

    async def test_a_connector_failure_marks_the_job_failed_not_an_unhandled_exception(
        self,
        real_session_factory: async_sessionmaker[AsyncSession],
        profile_id: uuid.UUID,
        tmp_path,
    ) -> None:
        job_id = await _create_pending_job(real_session_factory, profile_id)
        connector = _FakeConnector(error=ConnectorError("no such account"))

        await _run(job_id, real_session_factory, connector, tmp_path=tmp_path)

        async with session_scope(real_session_factory) as session:
            job = await session.get(Job, job_id)
            assert job is not None
            assert job.status == JobStatus.FAILED
            assert job.error is not None
            assert job.error["reason"] == "connector_error"

    async def test_an_account_with_no_games_completes_with_zero_total_not_a_failure(
        self,
        real_session_factory: async_sessionmaker[AsyncSession],
        profile_id: uuid.UUID,
        tmp_path,
    ) -> None:
        job_id = await _create_pending_job(real_session_factory, profile_id)
        connector = _FakeConnector(pgn_text="")

        await _run(job_id, real_session_factory, connector, tmp_path=tmp_path)

        async with session_scope(real_session_factory) as session:
            job = await session.get(Job, job_id)
            assert job is not None
            assert job.status == JobStatus.DONE
            assert job.progress["total"] == 0

    async def test_exceeding_max_games_marks_the_job_failed(
        self,
        real_session_factory: async_sessionmaker[AsyncSession],
        profile_id: uuid.UUID,
        tmp_path,
    ) -> None:
        job_id = await _create_pending_job(real_session_factory, profile_id)
        connector = _FakeConnector(pgn_text=GAME_A + "\n" + GAME_B)
        settings = Settings()
        settings.ingestion.max_games_per_import = 1

        await _run(job_id, real_session_factory, connector, settings=settings, tmp_path=tmp_path)

        async with session_scope(real_session_factory) as session:
            job = await session.get(Job, job_id)
            assert job is not None
            assert job.status == JobStatus.FAILED
            assert job.error is not None
            assert job.error["reason"] == "too_many_games"

    async def test_a_malformed_game_alongside_a_valid_one_still_completes_with_partial_import(
        self,
        real_session_factory: async_sessionmaker[AsyncSession],
        profile_id: uuid.UUID,
        tmp_path,
    ) -> None:
        """Partial-import recovery: one platform sync fetching several games must not
        fail entirely because one of them is malformed — the good games still import,
        the bad one is reported in `progress.rejected`, same as a manual multi-game
        upload already guarantees (`_ingest_sources` is unchanged either way)."""
        malformed = GAME_A.replace("3. Bb5 1-0", "3. Qxd8 1-0")
        job_id = await _create_pending_job(real_session_factory, profile_id)
        connector = _FakeConnector(pgn_text=malformed + "\n" + GAME_B)

        await _run(job_id, real_session_factory, connector, tmp_path=tmp_path)

        async with session_scope(real_session_factory) as session:
            job = await session.get(Job, job_id)
            assert job is not None
            assert job.status == JobStatus.DONE
            assert job.progress["imported"] == 1
            assert job.progress["rejected"][0]["reason"] == "malformed_pgn"

    async def test_a_missing_job_id_is_a_defensive_no_op(
        self, real_session_factory: async_sessionmaker[AsyncSession], tmp_path
    ) -> None:
        connector = _FakeConnector(pgn_text=GAME_A)

        # No job was ever created for this id — must not raise.
        await _run(uuid.uuid4(), real_session_factory, connector, tmp_path=tmp_path)

        assert connector.calls == []

    async def test_re_syncing_the_same_game_reports_a_duplicate(
        self,
        real_session_factory: async_sessionmaker[AsyncSession],
        profile_id: uuid.UUID,
        tmp_path,
    ) -> None:
        first_job_id = await _create_pending_job(real_session_factory, profile_id)
        await _run(
            first_job_id,
            real_session_factory,
            _FakeConnector(pgn_text=GAME_A),
            tmp_path=tmp_path,
        )

        second_job_id = await _create_pending_job(real_session_factory, profile_id)
        await _run(
            second_job_id,
            real_session_factory,
            _FakeConnector(pgn_text=GAME_A),
            tmp_path=tmp_path,
        )

        async with session_scope(real_session_factory) as session:
            job = await session.get(Job, second_job_id)
            assert job is not None
            assert job.progress["imported"] == 0
            assert job.progress["duplicates"] == 1
