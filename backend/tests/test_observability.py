"""Correlation middleware, rate limiting, context propagation, and the startup sweep.

Phase 17.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.middleware.correlation import CorrelationMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.core.config import Settings
from app.core.correlation import run_with_correlation
from app.db.models import Job, JobKind, JobStatus, Profile, ProfileKind, User
from app.db.session import session_scope
from app.domain.analysis.dispatch import startup_analysis_sweep

pytestmark = pytest.mark.asyncio


async def test_correlation_middleware() -> None:
    """Test that CorrelationMiddleware generates IDs, binds them to logs, and sets headers."""
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/test-endpoint")
    def get_correlation() -> dict[str, str]:
        context = structlog.contextvars.get_contextvars()
        return {
            "request_id": context.get("request_id", ""),
            "trace_id": context.get("trace_id", ""),
        }

    # TestClient doesn't block async tests
    client = TestClient(app)
    response = client.get("/test-endpoint")

    assert response.status_code == 200
    assert "X-Request-Id" in response.headers
    assert "X-Trace-Id" not in response.headers

    body = response.json()
    assert body["request_id"] == response.headers["X-Request-Id"]
    assert body["trace_id"] != ""


async def test_rate_limit_middleware() -> None:
    """Test that RateLimitMiddleware restricts requests based on IP address client limits."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit_per_minute=2)

    @app.get("/test")
    def get_test() -> str:
        return "ok"

    client = TestClient(app)

    # First and second requests allowed
    assert client.get("/test").status_code == 200
    assert client.get("/test").status_code == 200

    # Third request blocked (429)
    response = client.get("/test")
    assert response.status_code == 429
    assert response.text == "Rate limit exceeded. Please try again later."


async def test_run_with_correlation_propagation() -> None:
    """Test that run_with_correlation propagates correlation context to background tasks."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="task-req-123", trace_id="task-tr-456")

    resolved_context = {}

    async def dummy_task() -> None:
        resolved_context.update(structlog.contextvars.get_contextvars())

    # Schedule wrapped task
    wrapped = run_with_correlation(dummy_task)

    # Clear contextvars to simulate fresh task worker context
    structlog.contextvars.clear_contextvars()

    await wrapped()

    assert resolved_context.get("request_id") == "task-req-123"
    assert resolved_context.get("trace_id") == "task-tr-456"


@pytest.mark.usefixtures("db_schema")
async def test_startup_analysis_sweep(
    db_engine: AsyncEngine,
) -> None:
    """`startup_analysis_sweep` resets stuck jobs to pending and dispatches them."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    user_id = None
    try:
        # Use session_factory to commit setup data durably so it's visible to the sweep connection
        async with session_scope(session_factory) as session:
            user = User()
            session.add(user)
            await session.flush()
            user_id = user.id

            profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Test")
            session.add(profile)
            await session.flush()

            # Add jobs: one PENDING, one PROCESSING (stuck), and one DONE
            pending_job = Job(
                kind=JobKind.ENGINE_ANALYSIS,
                profile_id=profile.id,
                status=JobStatus.PENDING,
            )
            processing_job = Job(
                kind=JobKind.ENGINE_ANALYSIS,
                profile_id=profile.id,
                status=JobStatus.PROCESSING,
            )
            done_job = Job(
                kind=JobKind.ENGINE_ANALYSIS,
                profile_id=profile.id,
                status=JobStatus.DONE,
            )

            db_session_add_list = [pending_job, processing_job, done_job]
            session.add_all(db_session_add_list)
            await session.commit()

            # Save IDs for checking after commit
            pending_id = pending_job.id
            processing_id = processing_job.id
            done_id = done_job.id

        settings = Settings()

        # Mock run_pending_analysis_jobs to intercept execution calls
        with patch(
            "app.domain.analysis.dispatch.run_pending_analysis_jobs",
            new_callable=AsyncMock,
        ) as mock_run:
            await startup_analysis_sweep(session_factory, settings)

            # Allow background task to schedule/run
            await asyncio.sleep(0.05)

            # Assert run_pending_analysis_jobs was called
            mock_run.assert_called_once()
            called_ids = mock_run.call_args[0][0]

            assert pending_id in called_ids
            assert processing_id in called_ids
            assert done_id not in called_ids

            # Verify database statuses are updated (processing_job is reset to PENDING)
            async with session_scope(session_factory) as session:
                db_pending = await session.get(Job, pending_id)
                db_processing = await session.get(Job, processing_id)
                db_done = await session.get(Job, done_id)

                assert db_pending.status == JobStatus.PENDING
                assert db_processing.status == JobStatus.PENDING
                assert db_done.status == JobStatus.DONE
    finally:
        if user_id is not None:
            from sqlalchemy import delete

            async with session_scope(session_factory) as session:
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()


async def test_startup_sweep_task_is_strongly_referenced() -> None:
    """The detached sweep must not be collectable while it runs.

    asyncio holds only a weak reference to a running task, so a bare
    `create_task(...)` whose result nobody keeps can be garbage-collected mid-flight —
    silently losing the recovery of orphaned jobs, which is the one thing the sweep
    exists to do. Guards the reference-keeping in `_spawn_sweep`.
    """
    from app.domain.analysis import dispatch

    started = asyncio.Event()
    release = asyncio.Event()

    async def _work() -> None:
        started.set()
        await release.wait()

    task = dispatch._spawn_sweep(_work())
    await started.wait()

    assert task in dispatch._sweep_tasks

    release.set()
    await task
    # Completion clears the reference, so the set cannot grow without bound.
    assert task not in dispatch._sweep_tasks
