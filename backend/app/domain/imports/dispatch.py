"""Background dispatch for platform-sync import jobs (Phase 14, D-030/D-031).

The platform-sync analogue of `domain/analysis/dispatch.py`'s
`run_pending_analysis_jobs`: runs after the HTTP response that created the job has
already been sent, opens its own database session (the request's session is long closed
by the time a background task runs), and never raises — a failed platform fetch is
recorded on the job row itself, not surfaced to whatever is running the background task.

**Why a job is pre-created before this runs**, unlike `ImportService.ingest`'s own
inline job creation: fetching from Lichess or Chess.com is genuinely slow and
unpredictable (network latency, rate-limit backoff, a multi-month Chess.com archive
walk) in a way a manual PGN paste never is — the module docstring in
`domain/imports/service.py` anticipated exactly this before Phase 14 existed. The route
creates a `PENDING` job and returns immediately so the caller has something to poll;
this function fills it in.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.base import utc_now
from app.db.models import GameSource, Job, JobStatus, Profile
from app.db.session import session_scope
from app.domain.analysis import run_pending_analysis_jobs
from app.domain.imports.connectors import ConnectorError, PlatformGameConnector
from app.domain.imports.service import ImportService, SourceText, TooManyGamesError
from app.domain.patterns import OpeningIndex
from app.domain.profiles import get_linked_usernames, get_or_create_study_profile
from app.integrations.chesscom import ChessComGameConnector
from app.integrations.lichess import LichessGameConnector
from app.integrations.storage import StorageBackend

logger = get_logger(__name__)

ConnectorFactory = Callable[[GameSource, Settings], PlatformGameConnector]


def build_platform_connector(provider: GameSource, settings: Settings) -> PlatformGameConnector:
    """The real connector for `provider`. Tests substitute a fake factory, same
    reasoning `analysis/dispatch.py`'s `engine_factory` parameter exists."""
    if provider is GameSource.LICHESS:
        return LichessGameConnector(settings.ingestion)
    if provider is GameSource.CHESSCOM:
        return ChessComGameConnector(settings.ingestion)
    raise ValueError(f"{provider!r} has no platform connector")


async def run_platform_import_job(
    job_id: uuid.UUID,
    *,
    provider: GameSource,
    username: str,
    window: int,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    storage: StorageBackend,
    opening_index: OpeningIndex,
    connector_factory: ConnectorFactory = build_platform_connector,
) -> None:
    """Fetch `username`'s recent games from `provider` and ingest them into the
    already-created, `PENDING` `job_id` row.

    Never raises — a connector failure, a `TooManyGamesError`, or a missing profile are
    all recorded on the job row (the caller has no return value to inspect; polling the
    job is how a client learns the outcome), mirroring
    `analysis/dispatch.py`'s `_process_one_job` posture exactly.
    """
    analysis_job_ids: list[uuid.UUID] = []

    async with session_scope(session_factory) as session:
        job = await session.get(Job, job_id)
        if job is None or job.status != JobStatus.PENDING:
            # Defensive: nothing to do if the job vanished or was already handled —
            # same posture as `_process_one_job`, no caller is waiting on a return value.
            return

        profile = await session.get(Profile, job.profile_id)
        if profile is None:
            job.status = JobStatus.FAILED
            job.error = {"reason": "profile_not_found"}
            job.completed_at = utc_now()
            return

        connector = connector_factory(provider, settings)
        try:
            pgn_text = await connector.fetch_recent_games_pgn(username, window)
        except ConnectorError as exc:
            job.status = JobStatus.FAILED
            job.error = {"reason": "connector_error", "detail": str(exc)}
            job.completed_at = utc_now()
            logger.warning(
                "platform_import_failed",
                job_id=str(job_id),
                provider=provider.value,
                reason=str(exc),
            )
            return

        if not pgn_text.strip():
            # A real, successful fetch that simply found no games — not a failure.
            job.status = JobStatus.DONE
            job.progress = {"total": 0, "imported": 0, "duplicates": 0, "rejected": []}
            job.completed_at = utc_now()
            return

        study_profile = await get_or_create_study_profile(session, profile.owner_user_id)
        self_linked_usernames = await get_linked_usernames(session, profile.id)
        source = SourceText(text=pgn_text, label=f"{provider.value}:{username}", source=provider)

        service = ImportService(session, storage)
        try:
            result = await service.ingest_into_job(
                job,
                self_profile_id=profile.id,
                study_profile_id=study_profile.id,
                self_linked_usernames=self_linked_usernames,
                sources=[source],
                max_games=settings.ingestion.max_games_per_import,
                opening_index=opening_index,
                pattern_settings=settings.patterns,
            )
        except TooManyGamesError:
            # `_ingest_sources` already marked the job FAILED with the details before
            # raising — nothing further to do here.
            return

        analysis_job_ids = result.analysis_job_ids

    if analysis_job_ids:
        # Dispatched only after the above session has committed (the `async with`
        # block exited), same ordering reasoning `api/routes/imports.py` documents for
        # its own inline commit-before-dispatch: a separate session opened by
        # `run_pending_analysis_jobs` must never race the write that created these rows.
        await run_pending_analysis_jobs(
            analysis_job_ids, session_factory=session_factory, settings=settings
        )


__all__ = ["build_platform_connector", "run_platform_import_job"]
