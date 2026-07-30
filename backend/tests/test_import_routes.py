"""HTTP-level import route tests: create, get, list.

Same pattern as `test_auth_routes.py`: a real transactional `db_session`, the app's own
`get_db_session` dependency overridden to hand out that session, and requests run as
coroutines on the test's event loop via `httpx.ASGITransport` rather than `TestClient`'s
background thread — see that file's docstring for why the loop match matters here too.

Login is real (platform lookup stubbed, same as auth tests) so every request carries a
genuine session cookie and a genuine self profile, rather than a fabricated one.

`run_pending_analysis_jobs` is stubbed the same way: `BackgroundTasks` execute inline
before `httpx.ASGITransport` returns control to the test, so an unstubbed call here would
mean every route test pays for real Stockfish analysis (~7s/game) and needs a real engine
session factory bound to this test's isolated transaction — neither of which these
HTTP-layer tests are about. Real engine behaviour is covered in `test_analysis_*.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.api.dependencies.storage import get_storage
from app.core.config import Settings
from app.domain.patterns import load_opening_index
from app.integrations.platforms import PlatformClient, PlatformUser
from app.integrations.storage import LocalStorage
from app.main import create_app

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


async def _fake_fetch_user(self: PlatformClient, provider, username: str) -> PlatformUser:  # type: ignore[no-untyped-def]
    return PlatformUser(provider=provider, provider_user_id=username.lower(), username=username)


@pytest.fixture(autouse=True)
def _stub_platform_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformClient, "fetch_user", _fake_fetch_user)


@pytest.fixture(autouse=True)
def _stub_analysis_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op: these tests check the import HTTP contract, not engine analysis."""

    async def _noop(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.api.routes.imports.run_pending_analysis_jobs", _noop)


@pytest.fixture(autouse=True)
def _stub_platform_import_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op: these tests check the sync route's HTTP contract (permission/validation),
    not the platform-fetch-and-ingest path itself — that is
    `test_platform_import_dispatch.py`'s job."""

    async def _noop(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.api.routes.imports.run_platform_import_job", _noop)


@pytest.fixture
def import_settings() -> Settings:
    settings = Settings()
    settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
    return settings


@pytest_asyncio.fixture
async def import_client(
    import_settings: Settings, db_session: AsyncSession, tmp_path
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(import_settings)
    # Normally set by the lifespan, which never runs against this transport. The route
    # reads it to pass to the (stubbed, see above) analysis dispatcher — never actually
    # used to open a connection here, since the stub ignores it.
    app.state.db_session_factory = None
    # Also normally set by the lifespan (Phase 6). Real here, not stubbed — opening
    # lookup runs inline in `ImportService.ingest`, not through a dispatcher these tests
    # stub out, so the route genuinely needs a working index to exercise the real path.
    app.state.opening_index = load_opening_index(import_settings.patterns)

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/v1/auth/login", json={"provider": "lichess", "username": "magnus"})
        yield client


class TestCreateImport:
    async def test_pasting_pgn_text_creates_a_done_job_with_one_imported_game(
        self, import_client: httpx.AsyncClient
    ) -> None:
        response = await import_client.post("/api/v1/imports", data={"pgn_text": GAME_A})

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "done"
        assert body["progress"]["imported"] == 1
        assert body["progress"]["duplicates"] == 0

    async def test_uploading_a_multi_game_file_imports_every_game(
        self, import_client: httpx.AsyncClient
    ) -> None:
        response = await import_client.post(
            "/api/v1/imports",
            files={"files": ("batch.pgn", GAME_A + "\n" + GAME_B, "application/x-chess-pgn")},
        )

        assert response.status_code == 201
        assert response.json()["progress"]["imported"] == 2

    async def test_uploading_two_files_in_one_request_imports_both(
        self, import_client: httpx.AsyncClient
    ) -> None:
        response = await import_client.post(
            "/api/v1/imports",
            files=[
                ("files", ("a.pgn", GAME_A, "application/x-chess-pgn")),
                ("files", ("b.pgn", GAME_B, "application/x-chess-pgn")),
            ],
        )

        assert response.status_code == 201
        assert response.json()["progress"]["imported"] == 2

    async def test_reimporting_the_same_game_reports_a_duplicate_not_an_error(
        self, import_client: httpx.AsyncClient
    ) -> None:
        await import_client.post("/api/v1/imports", data={"pgn_text": GAME_A})

        response = await import_client.post("/api/v1/imports", data={"pgn_text": GAME_A})

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "done"
        assert body["progress"]["imported"] == 0
        assert body["progress"]["duplicates"] == 1

    async def test_empty_submission_is_rejected(self, import_client: httpx.AsyncClient) -> None:
        # An explicit empty field, not a zero-length/no-content-type request: the latter
        # is not a shape any real client (browser, fetch, curl -F) ever produces.
        response = await import_client.post("/api/v1/imports", data={"pgn_text": ""})

        assert response.status_code == 422

    async def test_a_malformed_game_is_reported_in_progress_not_as_an_error_response(
        self, import_client: httpx.AsyncClient
    ) -> None:
        malformed = GAME_A.replace("3. Bb5 1-0", "3. Qxd8 1-0")

        response = await import_client.post("/api/v1/imports", data={"pgn_text": malformed})

        assert response.status_code == 201
        body = response.json()
        assert body["progress"]["imported"] == 0
        assert body["progress"]["rejected"][0]["reason"] == "malformed_pgn"

    async def test_submission_without_login_is_unauthorized(
        self, db_session: AsyncSession, tmp_path
    ) -> None:
        settings = Settings()
        settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
        app = create_app(settings)

        # `CurrentLoginDep` resolves its own `DbSessionDep` before the 401 check ever
        # runs, so this still needs a working session dependency even though nothing
        # gets read or written.
        async def _override_db_session() -> AsyncIterator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db_session] = _override_db_session
        app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/v1/imports", data={"pgn_text": GAME_A})

        assert response.status_code == 401


class TestSyncFromPlatform:
    """`import_client` logs in via Lichess as "magnus" (see the fixture above), which —
    per `AuthService.login` — creates exactly one `ProfileSource(source=LICHESS,
    source_username="magnus")` for the self profile. That is the one linked account
    these tests can exercise; there is no linked Chess.com account for this profile,
    which is itself one of the cases worth covering (Phase 14, D-030/D-031)."""

    async def test_syncing_a_linked_provider_returns_a_pending_job(
        self, import_client: httpx.AsyncClient
    ) -> None:
        response = await import_client.post("/api/v1/imports/lichess/sync", json={})

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert body["kind"] == "pgn_import"

    async def test_syncing_an_unlinked_provider_is_not_found(
        self, import_client: httpx.AsyncClient
    ) -> None:
        response = await import_client.post("/api/v1/imports/chesscom/sync", json={})

        assert response.status_code == 404

    async def test_syncing_upload_as_a_provider_is_rejected(
        self, import_client: httpx.AsyncClient
    ) -> None:
        """`upload` is a valid `GameSource` member (it is what manual imports record),
        but it is not a platform to fetch from — the route must reject it explicitly
        rather than accepting it because `GameSource` parses it."""
        response = await import_client.post("/api/v1/imports/upload/sync", json={})

        assert response.status_code == 422

    async def test_an_invalid_window_is_rejected(self, import_client: httpx.AsyncClient) -> None:
        response = await import_client.post("/api/v1/imports/lichess/sync", json={"window": 7})

        assert response.status_code == 422

    async def test_a_valid_explicit_window_is_accepted(
        self, import_client: httpx.AsyncClient
    ) -> None:
        response = await import_client.post("/api/v1/imports/lichess/sync", json={"window": 30})

        assert response.status_code == 202

    async def test_an_explicit_username_needs_no_linked_account(
        self, import_client: httpx.AsyncClient
    ) -> None:
        """Importing a player being studied (Phase 16b follow-up): chesscom is unlinked
        for this profile — a 404 without a username, per the test above — but an explicit
        username is a different question entirely and must not consult linked accounts."""
        response = await import_client.post(
            "/api/v1/imports/chesscom/sync", json={"username": "hikaru"}
        )

        assert response.status_code == 202
        assert response.json()["status"] == "pending"

    async def test_a_blank_explicit_username_is_rejected(
        self, import_client: httpx.AsyncClient
    ) -> None:
        response = await import_client.post(
            "/api/v1/imports/lichess/sync", json={"username": "   "}
        )

        assert response.status_code == 422

    async def test_sync_without_login_is_unauthorized(
        self, db_session: AsyncSession, tmp_path
    ) -> None:
        settings = Settings()
        settings.identity.session_jwt_secret = SecretStr("test-only-signing-secret-32-bytes-plus")
        app = create_app(settings)

        async def _override_db_session() -> AsyncIterator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db_session] = _override_db_session
        app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/v1/imports/lichess/sync", json={})

        assert response.status_code == 401


class TestGetAndListImports:
    async def test_get_returns_the_job_just_created(self, import_client: httpx.AsyncClient) -> None:
        create_response = await import_client.post("/api/v1/imports", data={"pgn_text": GAME_A})
        job_id = create_response.json()["id"]

        response = await import_client.get(f"/api/v1/imports/{job_id}")

        assert response.status_code == 200
        assert response.json()["id"] == job_id

    async def test_get_an_unknown_job_is_not_found(self, import_client: httpx.AsyncClient) -> None:
        response = await import_client.get("/api/v1/imports/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404

    async def test_list_returns_jobs_most_recent_first(
        self, import_client: httpx.AsyncClient
    ) -> None:
        first = await import_client.post("/api/v1/imports", data={"pgn_text": GAME_A})
        second = await import_client.post("/api/v1/imports", data={"pgn_text": GAME_B})

        response = await import_client.get("/api/v1/imports")

        assert response.status_code == 200
        ids = [job["id"] for job in response.json()]
        assert ids == [second.json()["id"], first.json()["id"]]
