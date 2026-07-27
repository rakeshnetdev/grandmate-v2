"""Tiered engine analysis orchestration (Phase 5).

Policy: evaluate every position in the game once at `ENGINE_DEPTH` (the "shallow sweep"),
then re-evaluate only the positions immediately after a move whose shallow-depth
centipawn loss crosses `CRITICAL_SWING_CP`, at the deeper `ENGINE_DEEP_DEPTH`. A deepened
position feeds two plies at once — it is both "after" for the critical move and "before"
for the move that follows — so one deep re-analysis improves both without redoing work.

Deliberately not deepened further: a deep-verified position does not retrigger its own
neighbourhood for a second round of deepening. `is_critical_moment` records the original
shallow-depth finding as a stable, non-flip-flopping fact rather than being recomputed
against the (possibly lower) post-deepening centipawn loss.
"""

from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import EngineSettings
from app.db.base import utc_now
from app.db.models import GameAnalysis, GameMove, MoveClassification, MoveEvaluation
from app.domain.analysis.classification import classify_move, compute_cpl
from app.integrations.engine import EngineAdapter, EngineEvaluation


class AnalysisService:
    """Runs the tiered policy for one game against an already-started `EngineAdapter`."""

    def __init__(
        self, session: AsyncSession, engine: EngineAdapter, settings: EngineSettings
    ) -> None:
        self._session = session
        self._engine = engine
        self._settings = settings

    async def analyze_game(self, game_id: uuid.UUID) -> GameAnalysis:
        moves = await self._load_moves(game_id)
        if not moves:
            raise ValueError(f"Game {game_id} has no canonicalized moves to analyse")

        # N+1 distinct positions for N plies — fen_after[i] == fen_before[i+1] is a Phase
        # 4 guarantee, so each position is evaluated exactly once even at shallow depth.
        positions = [moves[0].fen_before] + [move.fen_after for move in moves]
        evals: list[EngineEvaluation] = [
            await self._engine.analyse(fen, depth=self._settings.engine_depth) for fen in positions
        ]

        shallow_cpls = [compute_cpl(evals[i], evals[i + 1]) for i in range(len(moves))]
        critical_plies = {
            i for i, cpl in enumerate(shallow_cpls) if cpl >= self._settings.critical_swing_cp
        }
        deep_positions = {i + 1 for i in critical_plies}

        for index in sorted(deep_positions):
            evals[index] = await self._engine.analyse(
                positions[index], depth=self._settings.engine_deep_depth
            )

        final_cpls = [compute_cpl(evals[i], evals[i + 1]) for i in range(len(moves))]

        records: list[MoveEvaluation] = []
        for i, move in enumerate(moves):
            cpl = final_cpls[i]
            classification = classify_move(
                played_uci=move.uci,
                best_move_uci=evals[i].best_move_uci,
                cpl=cpl,
                settings=self._settings,
            )
            records.append(
                MoveEvaluation(
                    ply=i,
                    eval_cp=evals[i].eval_cp,
                    mate_in=evals[i].mate_in,
                    best_move_uci=evals[i].best_move_uci,
                    pv=evals[i].pv,
                    classification=classification,
                    eval_swing_cp=cpl,
                    is_critical_moment=i in critical_plies,
                    # True if *either* endpoint of this ply's own swing was deepened —
                    # position i (this ply's eval_before) or position i+1 (its
                    # eval_after). A critical ply's deepened "after" position feeds its
                    # own cpl calculation just as much as it feeds the next ply's
                    # "before" — both plies' eval_swing_cp reflect the deepened value,
                    # so both must report deep_analyzed=True, not just one of them.
                    deep_analyzed=i in deep_positions or (i + 1) in deep_positions,
                )
            )

        analysis = GameAnalysis(
            game_id=game_id,
            analysis_version=self._analysis_version(),
            engine_depth=self._settings.engine_depth,
            summary=self._summarize(records),
            completed_at=utc_now(),
        )
        self._session.add(analysis)
        await self._session.flush()

        for record in records:
            record.game_analysis_id = analysis.id
        self._session.add_all(records)

        return analysis

    async def _load_moves(self, game_id: uuid.UUID) -> list[GameMove]:
        result = await self._session.execute(
            select(GameMove).where(GameMove.game_id == game_id).order_by(GameMove.ply)
        )
        return list(result.scalars().all())

    def _analysis_version(self) -> str:
        s = self._settings
        return (
            f"sf-d{s.engine_depth}-dd{s.engine_deep_depth}"
            f"-t{s.inaccuracy_cp}.{s.mistake_cp}.{s.blunder_cp}"
        )

    @staticmethod
    def _summarize(records: list[MoveEvaluation]) -> dict[str, object]:
        counts = Counter(record.classification.value for record in records)
        # A simple, documented proxy — not a claim to match any particular commercial
        # product's accuracy formula: the share of moves that were the engine's top
        # choice or within GOOD range. Good enough to show relative game quality; not
        # meant to be authoritative to the decimal point.
        total = len(records)
        good_or_better = counts.get("best", 0) + counts.get("good", 0)
        accuracy = round(100 * good_or_better / total, 1) if total else 0.0
        return {
            "total_moves": total,
            "counts": {c.value: counts.get(c.value, 0) for c in MoveClassification},
            "accuracy": accuracy,
            "critical_moments": sum(1 for r in records if r.is_critical_moment),
        }


__all__ = ["AnalysisService"]
