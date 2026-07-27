"""Background dispatch tests: bounded concurrency, status transitions, timeout, retry.

Fake engines throughout — these test the *dispatcher's* behaviour (does it respect
ENGINE_MAX_CONCURRENT_GAMES, does a failure land on the right job without killing the
batch, can a failed job be retried), not engine correctness, which
`tests/test_engine_stockfish.py` covers with the real thing.

**Why setup and verification go through `session_scope`, not the `db_session` fixture.**
`db_session` wraps the whole test in one outer transaction that is always rolled back —
exactly what `run_pending_analysis_jobs` cannot participate in: it opens its own session
per job via `session_factory`, on its own connection, and commits independently, the same
way it does in production. A write made through `db_session` never becomes visible to
that separate connection (it is not durably committed, only flushed within the
still-open outer transaction) — so setup and assertions here use real, separately
committed sessions instead, same as the dispatcher itself.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import EngineSettings, Settings
from app.db.models import (
    Game,
    GameMove,
    GameSource,
    Job,
    JobKind,
    JobStatus,
    Profile,
    ProfileKind,
    User,
)
from app.db.session import session_scope
from app.domain.analysis.dispatch import run_pending_analysis_jobs
from app.domain.analysis.queries import create_retry_job
from app.integrations.engine import EngineError, EngineEvaluation, EngineTimeoutError


class ConcurrencyTracker:
    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.lock = asyncio.Lock()


class TrackingEngine:
    """Sleeps briefly per `analyse()` call and records the peak number of instances
    mid-call at once, to verify the semaphore actually bounds concurrency rather than
    merely limiting how many jobs get *started*."""

    def __init__(self, tracker: ConcurrencyTracker, delay: float = 0.05) -> None:
        self._tracker = tracker
        self._delay = delay

    async def start(self) -> None:
        pass

    async def analyse(self, fen: str, *, depth: int) -> EngineEvaluation:
        async with self._tracker.lock:
            self._tracker.active += 1
            self._tracker.peak = max(self._tracker.peak, self._tracker.active)
        await asyncio.sleep(self._delay)
        async with self._tracker.lock:
            self._tracker.active -= 1
        return EngineEvaluation(eval_cp=0, mate_in=None, best_move_uci="uci0", pv=["uci0"])

    async def quit(self) -> None:
        pass


class FailingEngine:
    """Always fails — `start()` succeeds, `analyse()` raises."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def start(self) -> None:
        pass

    async def analyse(self, fen: str, *, depth: int) -> EngineEvaluation:
        raise self._error

    async def quit(self) -> None:
        pass


class SucceedingEngine:
    """Returns a fixed, valid evaluation for any position — enough for a 1-move game."""

    async def start(self) -> None:
        pass

    async def analyse(self, fen: str, *, depth: int) -> EngineEvaluation:
        return EngineEvaluation(eval_cp=0, mate_in=None, best_move_uci="uci0", pv=["uci0"])

    async def quit(self) -> None:
        pass


async def _make_profile(session: AsyncSession) -> Profile:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


async def _make_game_with_one_move(session: AsyncSession, profile: Profile) -> Game:
    game = Game(
        profile_id=profile.id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "A", "Black": "B"},
        raw_pgn_path="pgn/test.pgn",
    )
    session.add(game)
    await session.flush()
    session.add(
        GameMove(
            game_id=game.id,
            ply=0,
            san="move0",
            uci="uci0",
            fen_before="fen0",
            fen_after="fen1",
            epd_after="fen1",
        )
    )
    await session.flush()
    return game


async def _make_pending_job(session: AsyncSession, profile: Profile, game: Game) -> Job:
    job = Job(
        kind=JobKind.ENGINE_ANALYSIS,
        profile_id=profile.id,
        game_id=game.id,
        status=JobStatus.PENDING,
    )
    session.add(job)
    await session.flush()
    return job


@pytest_asyncio.fixture
async def session_factory(
    db_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A real, independently-committing session factory bound to the test's own engine —
    what both the dispatcher and this file's own setup/verification helpers use.

    Real commits mean real cleanup is required: `db_schema` only drops tables once per
    whole test *session*, and these tests bypass `db_session`'s per-test rollback (that
    is the entire point — see the module docstring), so without this teardown every
    profile/game/job created here would leak into whichever test happens to run next and
    breaks any assertion shaped like "select every row of X". Deleting `User` is enough:
    every other table here cascades from it.
    """
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    async with session_scope(factory) as session:
        await session.execute(delete(User))


async def _get_job(session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID) -> Job:
    async with session_scope(session_factory) as session:
        job = await session.get(Job, job_id)
        assert job is not None
        # Detach so its attributes remain readable after the session (and its
        # transaction) closes — this session's only purpose was the one fresh read.
        session.expunge(job)
        return job


class TestBoundedConcurrency:
    async def test_respects_the_configured_concurrency_limit(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        job_ids = []
        async with session_scope(session_factory) as session:
            profile = await _make_profile(session)
            for _ in range(6):
                game = await _make_game_with_one_move(session, profile)
                job = await _make_pending_job(session, profile, game)
                job_ids.append(job.id)

        tracker = ConcurrencyTracker()
        settings = Settings()
        settings.engine.engine_max_concurrent_games = 2

        await run_pending_analysis_jobs(
            job_ids,
            session_factory=session_factory,
            settings=settings,
            engine_factory=lambda _s: TrackingEngine(tracker),
        )

        assert tracker.peak == 2


class TestStatusTransitions:
    async def test_a_successful_job_ends_done_with_completed_at_set(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with session_scope(session_factory) as session:
            profile = await _make_profile(session)
            game = await _make_game_with_one_move(session, profile)
            job = await _make_pending_job(session, profile, game)
            job_id = job.id

        await run_pending_analysis_jobs(
            [job_id],
            session_factory=session_factory,
            settings=Settings(),
            engine_factory=lambda _s: SucceedingEngine(),
        )

        result = await _get_job(session_factory, job_id)
        assert result.status == JobStatus.DONE
        assert result.completed_at is not None
        assert result.error is None

    async def test_an_engine_error_fails_the_job_without_raising(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with session_scope(session_factory) as session:
            profile = await _make_profile(session)
            game = await _make_game_with_one_move(session, profile)
            job = await _make_pending_job(session, profile, game)
            job_id = job.id

        await run_pending_analysis_jobs(
            [job_id],
            session_factory=session_factory,
            settings=Settings(),
            engine_factory=lambda _s: FailingEngine(EngineError("boom")),
        )

        result = await _get_job(session_factory, job_id)
        assert result.status == JobStatus.FAILED
        assert result.error is not None
        assert result.error["reason"] == "engine_error"
        assert "boom" in result.error["detail"]

    async def test_a_timeout_fails_the_job_with_a_distinguishable_reason(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """`EngineTimeoutError` is a subclass of `EngineError` — both are caught by the
        same handler, but the detail string still carries which one actually fired."""
        async with session_scope(session_factory) as session:
            profile = await _make_profile(session)
            game = await _make_game_with_one_move(session, profile)
            job = await _make_pending_job(session, profile, game)
            job_id = job.id

        await run_pending_analysis_jobs(
            [job_id],
            session_factory=session_factory,
            settings=Settings(),
            engine_factory=lambda _s: FailingEngine(EngineTimeoutError("timed out after 30s")),
        )

        result = await _get_job(session_factory, job_id)
        assert result.status == JobStatus.FAILED
        assert result.error is not None
        assert "timed out" in result.error["detail"]

    async def test_one_failing_job_does_not_block_the_rest_of_the_batch(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with session_scope(session_factory) as session:
            profile = await _make_profile(session)
            failing_game = await _make_game_with_one_move(session, profile)
            failing_job = await _make_pending_job(session, profile, failing_game)
            failing_job_id = failing_job.id
            ok_game = await _make_game_with_one_move(session, profile)
            ok_job = await _make_pending_job(session, profile, ok_game)
            ok_job_id = ok_job.id

        call_count = 0

        def factory(_s: EngineSettings) -> object:
            nonlocal call_count
            call_count += 1
            return FailingEngine(EngineError("boom")) if call_count == 1 else SucceedingEngine()

        # Concurrency forced to 1: with the default (4), both jobs start at essentially
        # the same time and which one reaches `engine_factory` first is a race, not a
        # guarantee — this test is about failure isolation, not scheduling order, so
        # concurrency is pinned to make that order deterministic instead.
        settings = Settings()
        settings.engine.engine_max_concurrent_games = 1

        await run_pending_analysis_jobs(
            [failing_job_id, ok_job_id],
            session_factory=session_factory,
            settings=settings,
            engine_factory=factory,
        )

        failing_result = await _get_job(session_factory, failing_job_id)
        ok_result = await _get_job(session_factory, ok_job_id)
        assert failing_result.status == JobStatus.FAILED
        assert ok_result.status == JobStatus.DONE


class TestRetry:
    async def test_a_failed_jobs_game_can_be_retried_successfully(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with session_scope(session_factory) as session:
            profile = await _make_profile(session)
            game = await _make_game_with_one_move(session, profile)
            first_job = await _make_pending_job(session, profile, game)
            first_job_id = first_job.id
            game_id = game.id
            profile_id = profile.id

        await run_pending_analysis_jobs(
            [first_job_id],
            session_factory=session_factory,
            settings=Settings(),
            engine_factory=lambda _s: FailingEngine(EngineError("transient")),
        )
        first_result = await _get_job(session_factory, first_job_id)
        assert first_result.status == JobStatus.FAILED

        async with session_scope(session_factory) as session:
            retry_job = await create_retry_job(session, game_id, profile_id)
            assert retry_job is not None
            assert retry_job.id != first_job_id
            retry_job_id = retry_job.id

        await run_pending_analysis_jobs(
            [retry_job_id],
            session_factory=session_factory,
            settings=Settings(),
            engine_factory=lambda _s: SucceedingEngine(),
        )
        retry_result = await _get_job(session_factory, retry_job_id)
        assert retry_result.status == JobStatus.DONE

        # The original failed job's own record is untouched — retry adds, not overwrites.
        first_result_again = await _get_job(session_factory, first_job_id)
        assert first_result_again.status == JobStatus.FAILED
