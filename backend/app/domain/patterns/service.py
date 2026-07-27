"""Pattern detection orchestration (Phase 6).

Two independent capabilities, two different trigger points — see
`app/db/models/patterns.py` for the full reasoning:

- `detect_opening` only needs `GameMove.epd_after` (Phase 4 output), so it runs inline
  during canonicalization, same request as Phase 4 itself.
- `detect_patterns` runs the motif and theme detector registries over a completed
  `GameAnalysis`, so it only makes sense once one exists. It rides along in the
  background job right after `AnalysisService.analyze_game()` succeeds
  (`app/domain/analysis/dispatch.py`) rather than being a separate job kind — motif and
  theme detection is pure computation over already-fetched data, not another slow
  external call, so there is nothing for a second job to buy here.
"""

from __future__ import annotations

import uuid

import chess
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import PatternSettings
from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameMove,
    MotifFinding,
    MoveEvaluation,
    OpeningMatch,
    StrategicThemeFinding,
)
from app.domain.patterns.confidence import CORROBORATED_MOTIFS, corroborate
from app.domain.patterns.motifs import MOTIF_DETECTORS
from app.domain.patterns.opening_lookup import OpeningIndex
from app.domain.patterns.themes import THEME_DETECTORS
from app.domain.patterns.themes.base import PlyContext


class PatternDetectionService:
    """Runs opening lookup and motif/theme detection, and persists the findings.

    `opening_index` is a parameter of `detect_opening` itself, not a constructor
    dependency — it is the only one of this service's two capabilities that needs it
    (`detect_patterns` never touches it), and the two are called from different places
    with different lifecycles (see this module's docstring). Forcing every caller to
    supply an index it may not use would blur that separation for no benefit.
    """

    def __init__(self, session: AsyncSession, settings: PatternSettings) -> None:
        self._session = session
        self._settings = settings

    async def detect_opening(self, game: Game, opening_index: OpeningIndex) -> OpeningMatch | None:
        """Look up the deepest opening match for `game` and persist it.

        Idempotent: a pre-existing match for this game is replaced rather than
        duplicated, since `game_openings.game_id` is unique and this could in principle
        be called again for the same game (e.g. a future re-canonicalization).
        """
        moves = await self._load_moves(game.id)
        if not moves:
            return None

        match = opening_index.match([move.epd_after for move in moves])
        if match is None:
            return None

        existing = await self._session.execute(
            select(OpeningMatch).where(OpeningMatch.game_id == game.id)
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row is not None:
            await self._session.delete(existing_row)
            await self._session.flush()

        opening = OpeningMatch(
            game_id=game.id,
            eco=match.eco,
            opening_name=match.opening_name,
            epd=match.epd,
            matched_ply=match.matched_ply,
        )
        self._session.add(opening)
        await self._session.flush()
        return opening

    async def detect_patterns(self, analysis: GameAnalysis) -> None:
        """Run every registered motif detector per ply and every theme detector per
        side, over `analysis`'s game. Findings below `PATTERN_MIN_CONFIDENCE_TO_PERSIST`
        are computed but not persisted — the confidence floor from `PatternSettings`.

        Evaluations are loaded with an explicit query rather than read off
        `analysis.evaluations` — `AnalysisService.analyze_game` sets each record's
        `game_analysis_id` column directly rather than through the relationship
        attribute, so that in-memory collection is not reliably populated on the same
        `GameAnalysis` instance the caller just created.
        """
        moves = await self._load_moves(analysis.game_id)
        evaluations_by_ply = await self._load_evaluations_by_ply(analysis.id)
        plies = [
            PlyContext(move=move, evaluation=evaluations_by_ply.get(move.ply)) for move in moves
        ]

        self._detect_motifs(analysis.id, plies)
        self._detect_themes(analysis.id, plies)
        await self._session.flush()

    def _detect_motifs(self, analysis_id: uuid.UUID, plies: list[PlyContext]) -> None:
        for ply_context in plies:
            board_before = ply_context.board_before
            move = chess.Move.from_uci(ply_context.move.uci)
            board_after = ply_context.board_after
            side = GameColor.WHITE if board_before.turn == chess.WHITE else GameColor.BLACK

            for motif_type, detector in MOTIF_DETECTORS.items():
                detection = detector(board_before, move, board_after, self._settings)
                if detection is None:
                    continue

                confidence = detection.confidence
                if motif_type in CORROBORATED_MOTIFS:
                    confidence = corroborate(confidence, ply_context.evaluation)
                if confidence < self._settings.pattern_min_confidence_to_persist:
                    continue

                self._session.add(
                    MotifFinding(
                        game_analysis_id=analysis_id,
                        ply=ply_context.ply,
                        side=side,
                        motif=motif_type,
                        confidence=round(confidence, 2),
                        evidence=detection.evidence,
                    )
                )

    def _detect_themes(self, analysis_id: uuid.UUID, plies: list[PlyContext]) -> None:
        for side in (GameColor.WHITE, GameColor.BLACK):
            for theme_type, detector in THEME_DETECTORS.items():
                detection = detector(plies, side, self._settings)
                if detection is None:
                    continue
                if detection.confidence < self._settings.pattern_min_confidence_to_persist:
                    continue

                self._session.add(
                    StrategicThemeFinding(
                        game_analysis_id=analysis_id,
                        ply=detection.ply,
                        side=side,
                        theme=theme_type,
                        confidence=round(detection.confidence, 2),
                        evidence=detection.evidence,
                    )
                )

    async def _load_moves(self, game_id: uuid.UUID) -> list[GameMove]:
        result = await self._session.execute(
            select(GameMove).where(GameMove.game_id == game_id).order_by(GameMove.ply)
        )
        return list(result.scalars().all())

    async def _load_evaluations_by_ply(self, analysis_id: uuid.UUID) -> dict[int, MoveEvaluation]:
        result = await self._session.execute(
            select(MoveEvaluation).where(MoveEvaluation.game_analysis_id == analysis_id)
        )
        return {evaluation.ply: evaluation for evaluation in result.scalars().all()}


__all__ = ["PatternDetectionService"]
