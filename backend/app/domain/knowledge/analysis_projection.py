"""The `analysis` bucket's content: projecting a profile's own canonical game data
into short, retrievable text (Phase 7).

Deliberately minimal, ahead of Phase 8's aggregation work: per-game opening match,
critical moments, and motif/theme findings only — no aggregate-window synthesis across
several games, which needs Phase 8's profile aggregates to exist first. This is the
`analysis` bucket's *content generation*; `AnalysisRetriever`
(`domain/retrieval/analysis_retriever.py`) is what makes it queryable, profile-scoped.

Not currently wired into `domain/analysis/dispatch.py`'s background job — it requires a
real embedding call per game, and this phase's own scope is the retrieval substrate
itself, not that automatic pipeline wiring. Recorded as a known gap in the Phase 7
report rather than left silently unfinished; `project_game` is a complete, independently
tested, and directly callable service in the meantime (e.g. from the ingestion/eval
tooling or a future dispatch hook).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AnalysisKnowledgeChunk,
    Game,
    GameAnalysis,
    MotifFinding,
    MoveClassification,
    OpeningMatch,
    StrategicThemeFinding,
)
from app.domain.analysis.queries import get_latest_analysis
from app.integrations.llm.base import EmbeddingProvider

# Move classifications significant enough to project as a "critical moment" chunk.
# `is_critical_moment` already captures large eval swings; blunders/mistakes are
# included even when a swing fell just under that threshold, since a labelled blunder
# is coaching-relevant regardless of the exact centipawn cutoff that flagged it.
_CRITICAL_CLASSIFICATIONS = frozenset({MoveClassification.MISTAKE, MoveClassification.BLUNDER})


@dataclass(frozen=True)
class ProjectedChunk:
    """One piece of analysis text, before embedding."""

    kind: str
    content: str
    metadata: dict[str, object]


def _project_opening(opening: OpeningMatch) -> ProjectedChunk:
    return ProjectedChunk(
        kind="opening",
        content=(
            f"Opening: {opening.opening_name} (ECO {opening.eco}), "
            f"reached at ply {opening.matched_ply}."
        ),
        metadata={
            "eco": opening.eco,
            "opening_name": opening.opening_name,
            "matched_ply": opening.matched_ply,
        },
    )


def _project_critical_moments(analysis: GameAnalysis) -> list[ProjectedChunk]:
    chunks = []
    for move in analysis.evaluations:
        if not (move.is_critical_moment or move.classification in _CRITICAL_CLASSIFICATIONS):
            continue
        chunks.append(
            ProjectedChunk(
                kind="critical_moment",
                content=(
                    f"At ply {move.ply}, the move played was classified as "
                    f"{move.classification.value}, an eval swing of {move.eval_swing_cp} "
                    "centipawns against the mover."
                ),
                metadata={
                    "ply": move.ply,
                    "classification": move.classification.value,
                    "eval_swing_cp": move.eval_swing_cp,
                },
            )
        )
    return chunks


def _project_motif(motif: MotifFinding) -> ProjectedChunk:
    label = motif.motif.value.replace("_", " ")
    return ProjectedChunk(
        kind="motif",
        content=(
            f"At ply {motif.ply}, a {label} was found for {motif.side.value} "
            f"(confidence {motif.confidence})."
        ),
        metadata={
            "ply": motif.ply,
            "motif": motif.motif.value,
            "side": motif.side.value,
            "confidence": float(motif.confidence),
        },
    )


def _project_theme(theme: StrategicThemeFinding) -> ProjectedChunk:
    label = theme.theme.value.replace("_", " ")
    return ProjectedChunk(
        kind="theme",
        content=(
            f"Starting at ply {theme.ply}, {label} was observed for {theme.side.value} "
            f"(confidence {theme.confidence})."
        ),
        metadata={
            "ply": theme.ply,
            "theme": theme.theme.value,
            "side": theme.side.value,
            "confidence": float(theme.confidence),
        },
    )


class AnalysisProjectionService:
    """Builds and persists `analysis_knowledge_chunks` for one game at a time."""

    def __init__(self, session: AsyncSession, embedding_provider: EmbeddingProvider) -> None:
        self._session = session
        self._embedding_provider = embedding_provider

    async def project_game(self, game_id: uuid.UUID) -> list[AnalysisKnowledgeChunk]:
        """(Re)build the `analysis`-bucket chunks for `game_id`.

        Idempotent by replacement, same philosophy as `OpeningMatch`: a re-run (e.g.
        after a re-analysis or a detector fix) deletes this game's existing chunks and
        inserts fresh ones rather than accumulating stale rows alongside them.
        """
        game = await self._session.get(Game, game_id)
        if game is None:
            return []

        projected = await self._collect_projections(game_id)
        if not projected:
            return []

        await self._delete_existing(game_id)

        embeddings = await self._embedding_provider.embed([chunk.content for chunk in projected])
        rows = [
            AnalysisKnowledgeChunk(
                profile_id=game.profile_id,
                game_id=game_id,
                kind=chunk.kind,
                content=chunk.content,
                chunk_metadata=chunk.metadata,
                embedding=embedding,
            )
            for chunk, embedding in zip(projected, embeddings, strict=True)
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows

    async def _collect_projections(self, game_id: uuid.UUID) -> list[ProjectedChunk]:
        projected: list[ProjectedChunk] = []

        opening_result = await self._session.execute(
            select(OpeningMatch).where(OpeningMatch.game_id == game_id)
        )
        opening = opening_result.scalar_one_or_none()
        if opening is not None:
            projected.append(_project_opening(opening))

        analysis = await get_latest_analysis(
            self._session, game_id, await self._profile_id(game_id)
        )
        if analysis is None:
            return projected

        projected.extend(_project_critical_moments(analysis))

        motifs = await self._session.execute(
            select(MotifFinding).where(MotifFinding.game_analysis_id == analysis.id)
        )
        projected.extend(_project_motif(motif) for motif in motifs.scalars().all())

        themes = await self._session.execute(
            select(StrategicThemeFinding).where(
                StrategicThemeFinding.game_analysis_id == analysis.id
            )
        )
        projected.extend(_project_theme(theme) for theme in themes.scalars().all())

        return projected

    async def _profile_id(self, game_id: uuid.UUID) -> uuid.UUID:
        game = await self._session.get(Game, game_id)
        assert game is not None  # already checked by the caller
        return game.profile_id

    async def _delete_existing(self, game_id: uuid.UUID) -> None:
        existing = await self._session.execute(
            select(AnalysisKnowledgeChunk).where(AnalysisKnowledgeChunk.game_id == game_id)
        )
        for row in existing.scalars().all():
            await self._session.delete(row)
        await self._session.flush()


__all__ = ["AnalysisProjectionService", "ProjectedChunk"]
