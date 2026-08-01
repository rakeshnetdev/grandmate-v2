"""Bounded-concurrency background dispatch for analysis jobs (Phase 5).

Runs after the HTTP response that created the jobs has already been sent — this module is
what a FastAPI `BackgroundTasks` callback calls into, never a route handler directly. Each
job gets its own database session via `session_scope`: the request's session is closed by
the time background tasks run, so reusing it is not an option, and sharing one session
across concurrently-running jobs would not be safe either.

Concurrency is bounded per `ENGINE_MAX_CONCURRENT_GAMES` — confirmed with the owner after
benchmarking real per-game analysis time (~7s sequential on this machine). One Stockfish
process per concurrently-running game; `ENGINE_THREADS` stays 1 for determinism, per
`EngineSettings`.

Phase 6 addition: once `AnalysisService.analyze_game` succeeds, `_process_one_job` also
runs `PatternDetectionService.detect_patterns` over the resulting `GameAnalysis` before
marking the job `DONE` — motif/theme detection needs a completed analysis run to exist
(`app/db/models/patterns.py`), and is pure computation over already-fetched data rather
than another slow external call, so it rides along here instead of getting its own job
kind and its own bounded-concurrency dispatcher.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import EngineSettings, Settings
from app.core.logging import get_logger
from app.db.base import utc_now
from app.db.models import Job, JobStatus
from app.db.session import session_scope
from app.domain.analysis.service import AnalysisService
from app.domain.patterns import PatternDetectionService
from app.integrations.engine import EngineAdapter, EngineError, build_engine

logger = get_logger(__name__)

EngineFactory = Callable[[EngineSettings], EngineAdapter]

# Strong references to in-flight startup sweeps — see `startup_analysis_sweep`.
_background_tasks: set[asyncio.Task[None]] = set()


async def run_pending_analysis_jobs(
    job_ids: list[uuid.UUID],
    *,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    engine_factory: EngineFactory = build_engine,
) -> None:
    """Process `job_ids` with at most `ENGINE_MAX_CONCURRENT_GAMES` running at once.

    Never raises — a single game's failure is recorded on its own job row (see
    `_process_one_job`) and must not take down the rest of the batch or the background
    task runner itself.

    `engine_factory` defaults to the real `StockfishEngine` factory; tests substitute a
    fake so concurrency/timeout/retry behaviour is verifiable without real engine
    processes or real search time.
    """
    semaphore = asyncio.Semaphore(settings.engine.engine_max_concurrent_games)

    async def _run_one(job_id: uuid.UUID) -> None:
        async with semaphore, session_scope(session_factory) as session:
            await _process_one_job(session, job_id, settings, engine_factory)

    await asyncio.gather(*[_run_one(job_id) for job_id in job_ids])


async def _process_one_job(
    session: AsyncSession, job_id: uuid.UUID, settings: Settings, engine_factory: EngineFactory
) -> None:
    job = await session.get(Job, job_id)
    if job is None or job.status != JobStatus.PENDING or job.game_id is None:
        # Defensive: nothing to do if the job vanished, was already handled, or somehow
        # has no target game. Not an error worth surfacing — there is no caller waiting
        # on this background task's return value.
        return

    job.status = JobStatus.PROCESSING
    await session.flush()

    engine = engine_factory(settings.engine)
    try:
        await engine.start()
        service = AnalysisService(session, engine, settings.engine)
        analysis = await service.analyze_game(job.game_id)
    except EngineError as exc:
        job.status = JobStatus.FAILED
        job.error = {"reason": "engine_error", "detail": str(exc)}
        job.completed_at = utc_now()
        logger.warning("analysis_job_failed", job_id=str(job_id), reason=str(exc))
        return
    except ValueError as exc:
        # e.g. the game has no canonicalized moves — a data-state problem, not a timeout
        # or engine crash, but still not this job's to succeed at.
        job.status = JobStatus.FAILED
        job.error = {"reason": "invalid_game_state", "detail": str(exc)}
        job.completed_at = utc_now()
        logger.warning("analysis_job_failed", job_id=str(job_id), reason=str(exc))
        return
    finally:
        await engine.quit()

    try:
        # Phase 6: tactical/strategic findings ride on this analysis run rather than
        # getting a job kind of their own — see PatternDetectionService's docstring.
        # Deliberately broad except: this is enrichment on top of an already-successful
        # GameAnalysis, so a bug in a detector must not turn a good analysis run into a
        # FAILED job and discard it.
        await PatternDetectionService(session, settings.patterns).detect_patterns(analysis)
    except Exception as exc:
        logger.warning("pattern_detection_failed", job_id=str(job_id), reason=str(exc))

    job.status = JobStatus.DONE
    job.completed_at = utc_now()


async def startup_analysis_sweep(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Find all pending or stale processing analysis jobs on startup,
    reset the processing ones to pending, and trigger their execution in the background.
    """
    from sqlalchemy import select

    from app.db.models import Job, JobKind, JobStatus

    try:
        async with session_scope(session_factory) as session:
            stmt = select(Job).where(
                Job.kind == JobKind.ENGINE_ANALYSIS,
                Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
            )
            result = await session.execute(stmt)
            jobs = result.scalars().all()

            if not jobs:
                return

            job_ids = []
            for job in jobs:
                if job.status == JobStatus.PROCESSING:
                    job.status = JobStatus.PENDING
                    job.error = None
                job_ids.append(job.id)

            await session.commit()

        logger.info("startup_analysis_sweep_triggered", job_count=len(job_ids))
        # Dispatch in a background task so FastAPI startup is not blocked.
        #
        # The reference is held in a module-level set, and discarded only when the task
        # finishes: asyncio keeps only a weak reference to a running task, so a bare
        # `create_task(...)` can be garbage-collected mid-flight and the recovery sweep
        # would vanish silently — exactly the failure this sweep exists to prevent.
        task = asyncio.create_task(
            run_pending_analysis_jobs(
                job_ids,
                session_factory=session_factory,
                settings=settings,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except Exception as exc:
        logger.error("startup_analysis_sweep_failed", reason=str(exc))


__all__ = ["run_pending_analysis_jobs", "startup_analysis_sweep"]
