"""Ingestion orchestration: parse, dedup, persist, report.

Processing runs synchronously within the request. That is a deliberate choice for Phase
3's scope — manual upload/paste of a handful of games parses in well under a second, so
there is nothing to gain from a background task except two database sessions to keep
consistent in tests. The `jobs` table and polling endpoint exist so this is additive, not
a breaking change, once Phase 9's Lichess/Chess.com imports need real async work: only the
call site moves from inline to a worker, the schema and API contract stay the same.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models import Game, GameSource, Job, JobKind, JobStatus
from app.domain.imports.parsing import ParsedGame, RejectedGame, RejectionReason, parse_pgn_text
from app.integrations.storage import StorageBackend


class TooManyGamesError(Exception):
    """Raised when a submission's total game count exceeds the configured ceiling.

    Deliberately all-or-nothing: silently importing the first N and dropping the rest
    would leave the user guessing which games made it in.
    """

    def __init__(self, found: int, limit: int) -> None:
        self.found = found
        self.limit = limit
        super().__init__(f"{found} games found, exceeds the limit of {limit}")


@dataclass(frozen=True)
class SourceText:
    """One submitted PGN blob — a pasted string or one uploaded file's contents."""

    text: str
    label: str


def _storage_key(profile_id: uuid.UUID, content_hash: str) -> str:
    return f"pgn/{profile_id}/{content_hash}.pgn"


class ImportService:
    """Ingests raw PGN text into `games`, tracked through a `jobs` row."""

    def __init__(self, session: AsyncSession, storage: StorageBackend) -> None:
        self._session = session
        self._storage = storage

    async def ingest(
        self, profile_id: uuid.UUID, sources: list[SourceText], *, max_games: int
    ) -> Job:
        """Parse and persist every game across ``sources`` for ``profile_id``.

        Raises :class:`TooManyGamesError` before writing anything if the combined game
        count exceeds ``max_games`` — the caller maps that to a 422.
        """
        job = Job(kind=JobKind.PGN_IMPORT, profile_id=profile_id, status=JobStatus.PROCESSING)
        self._session.add(job)
        await self._session.flush()

        parsed_by_source: list[tuple[SourceText, list[ParsedGame], list[RejectedGame]]] = []
        total_games = 0
        for source in sources:
            result = parse_pgn_text(source.text)
            parsed_by_source.append((source, result.parsed, result.rejected))
            total_games += result.total

        if total_games > max_games:
            job.status = JobStatus.FAILED
            job.error = {
                "reason": "too_many_games",
                "found": total_games,
                "limit": max_games,
            }
            job.completed_at = utc_now()
            await self._session.flush()
            raise TooManyGamesError(total_games, max_games)

        imported = 0
        duplicates = 0
        rejected_report: list[dict[str, object]] = []

        for source, parsed_games, rejections in parsed_by_source:
            for rejection in rejections:
                rejected_report.append(
                    {
                        "source": source.label,
                        "index": rejection.index,
                        "reason": rejection.reason.value,
                        "detail": rejection.detail,
                    }
                )

            for local_index, parsed in enumerate(parsed_games):
                is_duplicate = await self._already_imported(profile_id, parsed.content_hash)
                if is_duplicate:
                    duplicates += 1
                    short_hash = parsed.content_hash[:12]
                    rejected_report.append(
                        {
                            "source": source.label,
                            "index": local_index,
                            "reason": RejectionReason.DUPLICATE_GAME.value,
                            "detail": f"Already imported for this profile (hash {short_hash}...)",
                        }
                    )
                    continue

                await self._storage.put(
                    _storage_key(profile_id, parsed.content_hash),
                    source.text.encode("utf-8"),
                    content_type="application/x-chess-pgn",
                )
                self._session.add(
                    Game(
                        profile_id=profile_id,
                        job_id=job.id,
                        source=GameSource.UPLOAD,
                        content_hash=parsed.content_hash,
                        headers=parsed.headers,
                        played_at=None,
                        raw_pgn_path=_storage_key(profile_id, parsed.content_hash),
                    )
                )
                imported += 1

        job.status = JobStatus.DONE
        job.progress = {
            "total": total_games,
            "imported": imported,
            "duplicates": duplicates,
            "rejected": rejected_report,
        }
        job.completed_at = utc_now()
        await self._session.flush()
        return job

    async def _already_imported(self, profile_id: uuid.UUID, content_hash: str) -> bool:
        result = await self._session.execute(
            select(Game.id).where(Game.profile_id == profile_id, Game.content_hash == content_hash)
        )
        return result.scalar_one_or_none() is not None

    async def get_job(self, job_id: uuid.UUID, profile_id: uuid.UUID) -> Job | None:
        """Scoped to ``profile_id`` so one profile can never poll another's job."""
        result = await self._session.execute(
            select(Job).where(Job.id == job_id, Job.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(self, profile_id: uuid.UUID) -> list[Job]:
        result = await self._session.execute(
            select(Job).where(Job.profile_id == profile_id).order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())


__all__ = ["ImportService", "SourceText", "TooManyGamesError"]
