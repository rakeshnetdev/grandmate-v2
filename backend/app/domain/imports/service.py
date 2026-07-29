"""Ingestion orchestration: parse, dedup, persist, canonicalize, report.

Processing runs synchronously within the request. That is a deliberate choice for Phase
3's scope — manual upload/paste of a handful of games parses in well under a second, so
there is nothing to gain from a background task except two database sessions to keep
consistent in tests. The `jobs` table and polling endpoint exist so this is additive, not
a breaking change, once Phase 9's Lichess/Chess.com imports need real async work: only the
call site moves from inline to a worker, the schema and API contract stay the same.

Phase 4 folds canonicalization (`GameParsingService`) into the same request, per the same
reasoning: a `Game` row is not just stored, it comes out already fully parsed — move list,
FEN/EPD, and (where the header names match a linked platform username) focus side.

Phase 5's engine analysis does **not** join that list. Benchmarked at ~7s/game on real
hardware, a batch import would turn a sub-second request into minutes — confirmed with
the owner, `ingest()` only creates a pending `ENGINE_ANALYSIS` job per successfully
canonicalized game. The caller (the route) is responsible for dispatching
`domain.analysis.run_pending_analysis_jobs` as a background task after the response is
sent; this module only ever creates the job rows.

Phase 6's opening lookup *does* join this request, unlike engine analysis: it is a hash
lookup over already-computed EPDs (`GameMove.epd_after`), not a slow external call, so
there is nothing to gain from deferring it — see `app/db/models/patterns.py` for the
full reasoning on why opening detection and tactical/strategic detection have different
trigger points.

Phase 8b routes each parsed game to one of two profiles before it is ever written — the
account's own `SELF` profile if either header name matches a linked platform username,
otherwise its `OPPONENT`-kind study profile (D-021, ADR-0016). This runs the same
`matches_any_linked_username` check Phase 4's `resolve_focus` is built on, just earlier:
early enough to pick where the row lands, not just how to label it afterward.
Canonicalization still re-resolves `focus_color`/`opponent_name` against whichever
profile the game actually landed in — for a self-routed game this repeats the same
match; for a study-routed game the study profile has no linked usernames of its own, so
it trivially stays `None`, which is correct.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import PatternSettings
from app.db.base import utc_now
from app.db.models import Game, GameSource, Job, JobKind, JobStatus
from app.domain.games import GameParsingService
from app.domain.games.normalization import matches_any_linked_username
from app.domain.imports.parsing import ParsedGame, RejectedGame, RejectionReason, parse_pgn_text
from app.domain.patterns import OpeningIndex, PatternDetectionService
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
    """One submitted PGN blob — a pasted string, one uploaded file's contents, or
    (Phase 14) the PGN a platform connector fetched.

    ``source`` defaults to ``GameSource.UPLOAD`` so every existing manual-paste/upload
    call site keeps working unchanged; the platform-sync path is the only caller that
    passes ``GameSource.LICHESS``/``GameSource.CHESSCOM`` explicitly, so the resulting
    ``Game`` rows record where they actually came from rather than being silently
    mislabelled as uploads.
    """

    text: str
    label: str
    source: GameSource = GameSource.UPLOAD


@dataclass(frozen=True)
class ImportResult:
    """What `ingest()` produced: the import job itself, and the analysis jobs it queued.

    `analysis_job_ids` is what the route hands to the background dispatcher — kept
    separate from `job.progress` (a JSON bag meant for display) so the caller has typed,
    direct access without parsing anything back out.
    """

    job: Job
    analysis_job_ids: list[uuid.UUID] = field(default_factory=list)


def _storage_key(profile_id: uuid.UUID, content_hash: str) -> str:
    return f"pgn/{profile_id}/{content_hash}.pgn"


class ImportService:
    """Ingests raw PGN text into `games`, tracked through a `jobs` row."""

    def __init__(self, session: AsyncSession, storage: StorageBackend) -> None:
        self._session = session
        self._storage = storage
        self._game_parser = GameParsingService(session, storage)

    async def ingest(
        self,
        *,
        self_profile_id: uuid.UUID,
        study_profile_id: uuid.UUID,
        self_linked_usernames: list[str],
        sources: list[SourceText],
        max_games: int,
        opening_index: OpeningIndex,
        pattern_settings: PatternSettings,
    ) -> ImportResult:
        """Parse and persist every game across ``sources``, routing each one to
        ``self_profile_id`` or ``study_profile_id`` individually (Phase 8b) — a single
        batch may split across both.

        Raises :class:`TooManyGamesError` before writing anything if the combined game
        count exceeds ``max_games`` — the caller maps that to a 422.

        ``opening_index``/``pattern_settings``/the profile arguments are call-time
        parameters, not constructor state, same reasoning as ``max_games``: they belong
        to *this operation*, not to every use of this service — ``get_job``/``list_jobs``
        have no need of them.

        The import ``Job`` row itself is recorded against ``self_profile_id`` regardless
        of where individual games land — it tracks the account's request, not one
        target profile's content.
        """
        job = Job(kind=JobKind.PGN_IMPORT, profile_id=self_profile_id, status=JobStatus.PROCESSING)
        self._session.add(job)
        await self._session.flush()
        return await self._ingest_sources(
            job,
            self_profile_id=self_profile_id,
            study_profile_id=study_profile_id,
            self_linked_usernames=self_linked_usernames,
            sources=sources,
            max_games=max_games,
            opening_index=opening_index,
            pattern_settings=pattern_settings,
        )

    async def ingest_into_job(
        self,
        job: Job,
        *,
        self_profile_id: uuid.UUID,
        study_profile_id: uuid.UUID,
        self_linked_usernames: list[str],
        sources: list[SourceText],
        max_games: int,
        opening_index: OpeningIndex,
        pattern_settings: PatternSettings,
    ) -> ImportResult:
        """Identical processing to :meth:`ingest`, but writing into an already-created,
        ``PENDING`` ``job`` rather than creating one (Phase 14).

        Exists for the platform-sync path: the route creates the job immediately (so
        the caller has an id to poll before any network call to Lichess/Chess.com has
        even started) and a background task fills it in once the platform fetch
        completes — see ``domain/imports/dispatch.py``. Manual paste/upload has no such
        two-step need (parsing a pasted blob is effectively instant), so :meth:`ingest`
        keeps creating its own job inline, unchanged.
        """
        job.status = JobStatus.PROCESSING
        await self._session.flush()
        return await self._ingest_sources(
            job,
            self_profile_id=self_profile_id,
            study_profile_id=study_profile_id,
            self_linked_usernames=self_linked_usernames,
            sources=sources,
            max_games=max_games,
            opening_index=opening_index,
            pattern_settings=pattern_settings,
        )

    async def _ingest_sources(
        self,
        job: Job,
        *,
        self_profile_id: uuid.UUID,
        study_profile_id: uuid.UUID,
        self_linked_usernames: list[str],
        sources: list[SourceText],
        max_games: int,
        opening_index: OpeningIndex,
        pattern_settings: PatternSettings,
    ) -> ImportResult:
        """The actual parse/dedupe/persist/canonicalize/report work, shared by
        :meth:`ingest` and :meth:`ingest_into_job` — the only difference between those
        two entry points is who creates ``job`` and when."""
        pattern_service = PatternDetectionService(self._session, pattern_settings)
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
        analysis_job_ids: list[uuid.UUID] = []

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
                target_profile_id = self._target_profile_id(
                    parsed.headers,
                    self_profile_id=self_profile_id,
                    study_profile_id=study_profile_id,
                    self_linked_usernames=self_linked_usernames,
                )

                is_duplicate = await self._already_imported(target_profile_id, parsed.content_hash)
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
                    _storage_key(target_profile_id, parsed.content_hash),
                    parsed.pgn_text.encode("utf-8"),
                    content_type="application/x-chess-pgn",
                )
                game = Game(
                    profile_id=target_profile_id,
                    job_id=job.id,
                    source=source.source,
                    content_hash=parsed.content_hash,
                    headers=parsed.headers,
                    played_at=None,
                    raw_pgn_path=_storage_key(target_profile_id, parsed.content_hash),
                )
                self._session.add(game)
                await self._session.flush()
                # Canonicalization (Phase 4), same request — fast enough to stay inline.
                # A canonicalization failure does not un-import the game; see
                # GameParsingService.canonicalize's own docstring.
                await self._game_parser.canonicalize(game)
                imported += 1

                if game.canonicalized_at is not None:
                    # Opening lookup (Phase 6) also stays inline — a hash lookup over
                    # EPDs already produced by canonicalization, not a slow external
                    # call, so there is no reason to defer it the way engine analysis is
                    # deferred below. No opening match is not an error; most positions
                    # in most games are outside any named opening line.
                    await pattern_service.detect_opening(game, opening_index)

                    # Engine analysis (Phase 5) does NOT join canonicalization inline —
                    # benchmarked far too slow for a synchronous request. Queue it; the
                    # route dispatches domain.analysis.run_pending_analysis_jobs as a
                    # background task after this response is sent. No job is queued for
                    # a game that failed canonicalization — there are no moves to analyse.
                    analysis_job = Job(
                        kind=JobKind.ENGINE_ANALYSIS,
                        profile_id=target_profile_id,
                        game_id=game.id,
                        status=JobStatus.PENDING,
                    )
                    self._session.add(analysis_job)
                    await self._session.flush()
                    analysis_job_ids.append(analysis_job.id)

        job.status = JobStatus.DONE
        job.progress = {
            "total": total_games,
            "imported": imported,
            "duplicates": duplicates,
            "rejected": rejected_report,
        }
        job.completed_at = utc_now()
        await self._session.flush()
        return ImportResult(job=job, analysis_job_ids=analysis_job_ids)

    @staticmethod
    def _target_profile_id(
        headers: dict[str, str],
        *,
        self_profile_id: uuid.UUID,
        study_profile_id: uuid.UUID,
        self_linked_usernames: list[str],
    ) -> uuid.UUID:
        """Which profile this parsed game belongs to (D-021, ADR-0016).

        An account with no linked usernames at all can't be checked against anything —
        rather than treat "nothing to check" the same as "checked and it's not mine",
        an unattributable game stays with the account's own profile, the same place it
        would have landed before Phase 8b existed.
        """
        if not self_linked_usernames:
            return self_profile_id
        belongs_to_self = matches_any_linked_username(
            white=headers.get("White", ""),
            black=headers.get("Black", ""),
            linked_usernames=self_linked_usernames,
        )
        return self_profile_id if belongs_to_self else study_profile_id

    async def _already_imported(self, profile_id: uuid.UUID, content_hash: str) -> bool:
        result = await self._session.execute(
            select(Game.id).where(Game.profile_id == profile_id, Game.content_hash == content_hash)
        )
        return result.scalar_one_or_none() is not None

    async def get_job(self, job_id: uuid.UUID, profile_id: uuid.UUID) -> Job | None:
        """Scoped to ``profile_id`` so one profile can never poll another's job.

        Filtered to ``PGN_IMPORT`` — Phase 5's ``ENGINE_ANALYSIS`` jobs share this same
        table by design, but polling them is `domain.analysis`'s surface
        (`/api/v1/analysis/jobs/{id}`), not `/api/v1/imports/{id}`. Mixing kinds into one
        listing would mean this route showing job types it has nothing to do with.
        """
        result = await self._session.execute(
            select(Job).where(
                Job.id == job_id, Job.profile_id == profile_id, Job.kind == JobKind.PGN_IMPORT
            )
        )
        return result.scalar_one_or_none()

    async def list_jobs(self, profile_id: uuid.UUID) -> list[Job]:
        """``PGN_IMPORT`` jobs only — see `get_job` for why."""
        result = await self._session.execute(
            select(Job)
            .where(Job.profile_id == profile_id, Job.kind == JobKind.PGN_IMPORT)
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())


__all__ = ["ImportResult", "ImportService", "SourceText", "TooManyGamesError"]
