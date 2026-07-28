"""Opening identification and tactical/strategic findings for a game (Phase 6).

Thin per the "routes delegate" rule: lookups live in `domain/patterns/queries.py`,
detection in `domain/patterns/service.py`. Separate resource from `/analysis` on
purpose — this data is a distinct concern (structured meaning layered on top of the
raw evaluations `/analysis` returns), even though findings are keyed off the same
`GameAnalysis` run under the hood.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.profile_scope import ScopedProfileIdDep
from app.db.models import Game
from app.domain.patterns.queries import get_opening_match, get_pattern_findings
from app.schemas.patterns import (
    GamePatternsSummary,
    MotifFindingSummary,
    OpeningMatchSummary,
    StrategicThemeFindingSummary,
)

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("/games/{game_id}", response_model=GamePatternsSummary)
async def get_game_patterns(
    game_id: uuid.UUID, profile_id: ScopedProfileIdDep, session: DbSessionDep
) -> GamePatternsSummary:
    """Opening identification plus every tactical/strategic finding for a game in the
    requested profile. A 404 means the game itself isn't in that profile; an empty
    response body otherwise (`opening: null`, empty finding lists) means detection
    hasn't found anything to report yet, or found nothing at all — both normal
    outcomes."""
    game = await session.get(Game, game_id)
    if game is None or game.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    opening = await get_opening_match(session, game_id, profile_id)
    findings = await get_pattern_findings(session, game_id, profile_id)

    return GamePatternsSummary(
        game_id=game_id,
        opening=(
            OpeningMatchSummary(
                eco=opening.eco,
                opening_name=opening.opening_name,
                epd=opening.epd,
                matched_ply=opening.matched_ply,
            )
            if opening is not None
            else None
        ),
        motifs=[
            MotifFindingSummary(
                ply=motif.ply,
                side=motif.side.value,
                motif=motif.motif.value,
                confidence=float(motif.confidence),
                evidence=motif.evidence,
            )
            for motif in findings.motifs
        ],
        themes=[
            StrategicThemeFindingSummary(
                ply=theme.ply,
                side=theme.side.value,
                theme=theme.theme.value,
                confidence=float(theme.confidence),
                evidence=theme.evidence,
            )
            for theme in findings.themes
        ],
    )


__all__ = ["router"]
