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
from app.db.models import Job
from app.domain.analysis import run_pending_analysis_jobs
from app.domain.imports import ImportService, SourceText, TooManyGamesError
from app.schemas.imports import JobSummary

router = APIRouter(prefix="/imports", tags=["imports"])


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

    service = ImportService(session, storage)
    try:
        result = await service.ingest(
            current.profile.id,
            sources,
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
            run_pending_analysis_jobs,
            result.analysis_job_ids,
            session_factory=request.app.state.db_session_factory,
            settings=settings,
        )

    return _to_job_summary(result.job)


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
