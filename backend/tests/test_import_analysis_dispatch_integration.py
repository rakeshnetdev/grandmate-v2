"""Regression coverage for the Phase 5 background-job race, fixed in Phase 7.

**The bug** (see `final_docs/v2/phase-reports/phase-06-opening-detection-tags.md`):
`create_import`/`retry_game_analysis` created a `Job` row using the request's own
`DbSessionDep` session, then handed the job id to `BackgroundTasks`, which opened a
*separate* session in `dispatch.py`. That session's lookup of the just-created row could
run before the request session's write was durable, so `_process_one_job`'s defensive
"job vanished" guard silently no-opped the job forever — no error, no log, `pending`
forever. The fix (`app/api/routes/imports.py`, `app/api/routes/analysis.py`) commits the
request session explicitly before scheduling the background task, rather than relying on
`DbSessionDep`'s own post-yield commit ordering relative to `BackgroundTasks`.

**Why this test is shaped differently from `test_import_routes.py`.** Those tests
deliberately stub `run_pending_analysis_jobs` and set `db_session_factory = None` — they
are about the import HTTP contract, not engine dispatch, and reusing the shared
`db_session` fixture (one always-rolled-back outer transaction) would make a real
dual-session handoff meaningless: nothing either session writes there is ever durably
committed for the other to see, race or no race. This test instead uses a real,
independently-committing session factory bound to the test database — the same rationale
`test_analysis_dispatch.py` documents — wired into the real app exactly as production
does, so the request session and the background task's session are the genuine two
separate connections the original bug lived in.

**Why real Stockfish, not a fake engine.** The route always calls
`run_pending_analysis_jobs` with its default `engine_factory=build_engine`; nothing at the
HTTP layer can substitute a fake engine without changing production wiring. Skipped when
Stockfish is not installed, same convention as `test_engine_stockfish.py`.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies.storage import get_storage
from app.core.config import EngineSettings, Settings
from app.db.models import AuditEvent, Job, JobKind, User
from app.db.session import session_scope
from app.domain.patterns import load_opening_index
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app

pytestmark = pytest.mark.skipif(
    not os.path.exists(EngineSettings().stockfish_path),
    reason="Stockfish not installed at EngineSettings().stockfish_path",
)

# White is "magnus" to match `live_client`'s login username — Phase 8b routes an
# imported game to the account's own SELF profile only if a header name matches a linked
# username (see `domain/imports/service.py`), and the final assertion below queries
# `/analysis/games/{id}` with no `profile_id`, which defaults to SELF.
GAME = """[Event "Test"]
[White "magnus"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0
"""


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest_asyncio.fixture
async def real_session_factory(
    db_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Independently-committing sessions on the test database — not the shared,
    always-rolled-back `db_session` fixture. See the module docstring for why.

    `db_schema` (in `db_fixtures.py`) creates the schema once per whole pytest *session*,
    not per test, so a real commit here is visible to every test that runs afterwards
    unless it is cleaned up — same rationale as `test_analysis_dispatch.py`'s
    `session_factory` fixture. Unlike that fixture, this test logs in through the real
    HTTP endpoint, which also writes an `AuditEvent` — and `AuditEvent.actor_user_id` is
    `ON DELETE SET NULL`, not cascade (by design: deleting an account must not erase the
    audit trail), so deleting `User` alone would leave an orphaned row behind. Delete both.
    """
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    async with session_scope(factory) as session:
        await session.execute(delete(AuditEvent))
        await session.execute(delete(User))


@pytest_asyncio.fixture
async def live_client(
    monkeypatch: pytest.MonkeyPatch,
    real_session_factory: async_sessionmaker[AsyncSession],
    tmp_path,
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)

    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    app = create_app(settings)
    # Real factory, not `None` — this is the one thing that must differ from
    # `test_import_routes.py`'s fixture: the whole point here is exercising the real
    # request-session -> background-task-session handoff.
    app.state.db_session_factory = real_session_factory
    app.state.opening_index = load_opening_index(settings.patterns)
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"})
        yield client


class TestBackgroundAnalysisReallyCompletes:
    async def test_import_analysis_job_reaches_done_through_the_real_dispatch_path(
        self,
        live_client: httpx.AsyncClient,
        real_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        response = await live_client.post("/api/v1/imports", data={"pgn_text": GAME})
        assert response.status_code == 201

        # The HTTP contract doesn't expose the analysis job's game id (no games-list
        # route yet — a known, separately-tracked gap), so find it the same way
        # `test_analysis_dispatch.py` verifies dispatch outcomes: a fresh, independently
        # committed read against the real database.
        async with session_scope(real_session_factory) as session:
            result = await session.execute(
                select(Job)
                .where(Job.kind == JobKind.ENGINE_ANALYSIS)
                .order_by(Job.created_at.desc())
            )
            analysis_job = result.scalars().first()
            assert analysis_job is not None
            game_id = analysis_job.game_id

        analysis_response = await live_client.get(f"/api/v1/analysis/games/{game_id}")

        # Before the fix, this job stayed `pending` forever and this would 404 forever —
        # not flakily, deterministically, on every run. The response here proves the
        # background task's session actually saw the job row this request just committed.
        assert analysis_response.status_code == 200
        assert analysis_response.json()["game_id"] == str(game_id)
