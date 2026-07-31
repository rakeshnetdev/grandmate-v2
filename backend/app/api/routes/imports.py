"""PGN upload, paste, and batch ingestion.

Thin per the "routes delegate" rule: parsing lives in `domain/imports/parsing.py`,
orchestration in `domain/imports/service.py`. This module only translates HTTP
(multipart form + files) into `ImportService` calls and back.

A single endpoint accepts pasted text, one file, or many files in the same request —
deliberately, so a single-game PGN is not a special case of the multi-game/multi-file
path, just the N=1 instance of it.

`create_import` also dispatches Phase 5's engine-analysis jobs as a `BackgroundTasks`
callback — the one place in this module that isn't "thin," because bridging the
request-scoped session to a background task's own session is an HTTP-layer concern, not
a domain one. `domain.imports.service` only ever creates the pending job rows.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from app.api.dependencies.auth import CurrentLoginDep
from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.patterns import OpeningIndexDep
from app.api.dependencies.settings import SettingsDep
from app.api.dependencies.storage import StorageDep
from app.db.models import GameSource, Job, JobKind, JobStatus
from app.core.correlation import run_with_correlation
from app.domain.analysis import run_pending_analysis_jobs
from app.domain.imports import ImportService, SourceText, TooManyGamesError, run_platform_import_job
from app.domain.profiles import (
    get_linked_usernames,
    get_or_create_study_profile,
    get_profile_source,
)
from app.schemas.imports import JobSummary, PlatformSyncRequest

router = APIRouter(prefix="/imports", tags=["imports"])

# Sources a client may request a sync for — `GameSource.UPLOAD` is a `Game.source`
# value, never something to fetch, so it is deliberately excluded here rather than
# accepted and rejected inside the handler.
_SYNCABLE_SOURCES = (GameSource.LICHESS, GameSource.CHESSCOM)


def _to_job_summary(job: Job) -> JobSummary:
    return JobSummary(
        id=job.id,
        kind=job.kind.value,
        status=job.status.value,
        progress=job.progress or {},
        error=job.error,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.post("", response_model=JobSummary, status_code=status.HTTP_201_CREATED)
async def create_import(
    request: Request,
    background_tasks: BackgroundTasks,
    current: CurrentLoginDep,
    session: DbSessionDep,
    settings: SettingsDep,
    storage: StorageDep,
    opening_index: OpeningIndexDep,
    pgn_text: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
) -> JobSummary:
    """Ingest pasted PGN text, one or more uploaded files, or both together.

    Every source file may itself contain one game or many — a plain single-game upload is
    just the N=1 case, not a different code path.
    """
    sources: list[SourceText] = []

    if pgn_text and pgn_text.strip():
        sources.append(SourceText(text=pgn_text, label="pasted"))

    max_upload_bytes = settings.ingestion.max_pgn_upload_mb * 1024 * 1024
    for upload in files:
        content = await upload.read()
        if len(content) > max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=(
                    f"{upload.filename} exceeds the {settings.ingestion.max_pgn_upload_mb}MB "
                    "upload limit"
                ),
            )
        text = content.decode("utf-8", errors="replace")
        sources.append(SourceText(text=text, label=upload.filename or "upload"))

    if not sources:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide pasted PGN text or at least one file",
        )

    # Phase 8b (D-021, ADR-0016): each parsed game routes to the caller's own SELF
    # profile or their study profile individually, based on whether its header names
    # match a linked platform username — decided inside `ingest`, not here.
    study_profile = await get_or_create_study_profile(session, current.user.id)
    self_linked_usernames = await get_linked_usernames(session, current.profile.id)

    service = ImportService(session, storage)
    try:
        result = await service.ingest(
            self_profile_id=current.profile.id,
            study_profile_id=study_profile.id,
            self_linked_usernames=self_linked_usernames,
            sources=sources,
            max_games=settings.ingestion.max_games_per_import,
            opening_index=opening_index,
            pattern_settings=settings.patterns,
        )
    except TooManyGamesError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    if result.analysis_job_ids:
        # Commit explicitly, here, before scheduling the background task. The
        # background task opens its own session (see dispatch.py) and looks up these
        # job rows by id — if that lookup can run before this session's write is
        # durable, it silently finds nothing and no-ops (Phase 5 defect, fixed here).
        # Relying on DbSessionDep's own post-yield commit was not a strong enough
        # guarantee of ordering relative to BackgroundTasks; committing here removes
        # the ambiguity outright.
        await session.commit()
        background_tasks.add_task(
            run_with_correlation(run_pending_analysis_jobs),
            result.analysis_job_ids,
            session_factory=request.app.state.db_session_factory,
            settings=settings,
        )

    return _to_job_summary(result.job)


@router.post("/{provider}/sync", response_model=JobSummary, status_code=status.HTTP_202_ACCEPTED)
async def sync_from_platform(
    provider: GameSource,
    body: PlatformSyncRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current: CurrentLoginDep,
    session: DbSessionDep,
    settings: SettingsDep,
    storage: StorageDep,
    opening_index: OpeningIndexDep,
) -> JobSummary:
    """Import recent games from Lichess or Chess.com (Phase 14, D-030/D-031). Reads each
    platform's public game-export endpoint — no OAuth involved, see D-030 — for either
    the profile's already-linked username, or an explicit `username` in the body when
    importing a player being studied (Phase 16b follow-up; see `PlatformSyncRequest`).

    Returns `202 Accepted` with a `PENDING` job immediately; the actual platform fetch
    and ingestion run in the background (`run_platform_import_job`) because, unlike a
    manual paste, a network round-trip to a third-party API has no bound on how long it
    might take. Poll `GET /imports/{job_id}` for the outcome, same as any other job.
    """
    if provider not in _SYNCABLE_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{provider.value!r} is not a syncable platform source",
        )

    # An explicit username (Phase 16b follow-up) is a player being *studied*, so there is
    # no linked account to look up — and none is required, since per-game routing sends
    # anything that isn't the caller's own play to their study profile by itself. A bad
    # username surfaces as a `connector_error` on the job, the same way a platform outage
    # does; validating it here would mean a second network call on the request path.
    if body.username is not None:
        username = body.username.strip()
        if not username:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="username must not be blank",
            )
    else:
        profile_source = await get_profile_source(session, current.profile.id, provider)
        if profile_source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No linked {provider.value} account for this profile",
            )
        username = profile_source.source_username

    window = body.window if body.window is not None else settings.analytics.analytics_default_window
    if window not in settings.analytics.window_sizes_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"window must be one of {settings.analytics.window_sizes_list}",
        )

    job = Job(kind=JobKind.PGN_IMPORT, profile_id=current.profile.id, status=JobStatus.PENDING)
    session.add(job)
    await session.flush()
    # Committed before scheduling the background task for the same reason
    # `create_import` commits before dispatching analysis jobs above: the background
    # task opens its own session and looks the job up by id, which must not race this
    # write's durability.
    await session.commit()

    background_tasks.add_task(
        run_with_correlation(run_platform_import_job),
        job.id,
        provider=provider,
        username=username,
        window=window,
        session_factory=request.app.state.db_session_factory,
        settings=settings,
        storage=storage,
        opening_index=opening_index,
    )

    return _to_job_summary(job)


@router.get("/{job_id}", response_model=JobSummary)
async def get_import(
    job_id: uuid.UUID, current: CurrentLoginDep, session: DbSessionDep, storage: StorageDep
) -> JobSummary:
    """Poll a job's status. Scoped to the caller's own profile."""
    service = ImportService(session, storage)
    job = await service.get_job(job_id, current.profile.id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return _to_job_summary(job)


@router.get("", response_model=list[JobSummary])
async def list_imports(
    current: CurrentLoginDep, session: DbSessionDep, storage: StorageDep
) -> list[JobSummary]:
    """List the caller's own import jobs, most recent first."""
    service = ImportService(session, storage)
    jobs = await service.list_jobs(current.profile.id)
    return [_to_job_summary(job) for job in jobs]


__all__ = ["router"]
