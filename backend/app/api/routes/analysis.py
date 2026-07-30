"""Engine analysis job polling and results.

Thin per the "routes delegate" rule: lookups live in `domain/analysis/queries.py`,
dispatch in `domain/analysis/dispatch.py`. Separate resource from `/imports` on purpose —
`ENGINE_ANALYSIS` and `PGN_IMPORT` share the `jobs` table by design, but polling one kind
through a route named for the other would be confusing, not economical.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.profile_scope import ScopedProfileIdDep
from app.api.dependencies.settings import SettingsDep
from app.db.models import GameAnalysis, GameMove, Job
from app.domain.analysis import create_retry_job, get_analysis_job, get_latest_analysis, get_moves
from app.domain.analysis import run_pending_analysis_jobs as _run_pending_analysis_jobs
from app.schemas.analysis import AnalysisJobSummary, GameAnalysisSummary, MoveEvaluationSummary

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _to_job_summary(job: Job) -> AnalysisJobSummary:
    return AnalysisJobSummary(
        id=job.id,
        kind=job.kind.value,
        status=job.status.value,
        game_id=job.game_id,
        error=job.error,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _to_analysis_summary(
    analysis: GameAnalysis, moves_by_ply: dict[int, GameMove]
) -> GameAnalysisSummary:
    return GameAnalysisSummary(
        id=analysis.id,
        game_id=analysis.game_id,
        analysis_version=analysis.analysis_version,
        engine_depth=analysis.engine_depth,
        summary=analysis.summary,
        completed_at=analysis.completed_at,
        moves=[
            MoveEvaluationSummary(
                ply=move.ply,
                san=moves_by_ply[move.ply].san if move.ply in moves_by_ply else None,
                fen_after=moves_by_ply[move.ply].fen_after if move.ply in moves_by_ply else None,
                eval_cp=move.eval_cp,
                mate_in=move.mate_in,
                best_move_uci=move.best_move_uci,
                pv=move.pv,
                classification=move.classification.value,
                eval_swing_cp=move.eval_swing_cp,
                mate_swing=move.mate_swing,
                is_critical_moment=move.is_critical_moment,
                deep_analyzed=move.deep_analyzed,
            )
            for move in analysis.evaluations
        ],
    )


@router.get("/jobs/{job_id}", response_model=AnalysisJobSummary)
async def get_analysis_job_status(
    job_id: uuid.UUID, profile_id: ScopedProfileIdDep, session: DbSessionDep
) -> AnalysisJobSummary:
    """Poll an analysis job's status, scoped to the requested profile."""
    job = await get_analysis_job(session, job_id, profile_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found")
    return _to_job_summary(job)


@router.get("/games/{game_id}", response_model=GameAnalysisSummary)
async def get_game_analysis(
    game_id: uuid.UUID, profile_id: ScopedProfileIdDep, session: DbSessionDep
) -> GameAnalysisSummary:
    """The most recent completed analysis for a game in the requested profile."""
    analysis = await get_latest_analysis(session, game_id, profile_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this game",
        )
    moves_by_ply = {m.ply: m for m in await get_moves(session, game_id, profile_id)}
    return _to_analysis_summary(analysis, moves_by_ply)


@router.post(
    "/games/{game_id}/retry", response_model=AnalysisJobSummary, status_code=status.HTTP_201_CREATED
)
async def retry_game_analysis(
    game_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> AnalysisJobSummary:
    """Queue a fresh analysis run for a game in the requested profile — e.g. after a
    prior run failed (engine timeout, transient error). Does not touch prior runs;
    `GameAnalysis` is versioned, so this adds one rather than replacing anything."""
    job = await create_retry_job(session, game_id, profile_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    # Commit explicitly before scheduling the background task — see the matching
    # comment in imports.py's create_import for why (Phase 5 defect, fixed here).
    await session.commit()
    background_tasks.add_task(
        _run_pending_analysis_jobs,
        [job.id],
        session_factory=request.app.state.db_session_factory,
        settings=settings,
    )
    return _to_job_summary(job)


__all__ = ["router"]
