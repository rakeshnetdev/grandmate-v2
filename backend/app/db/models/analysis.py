"""Engine analysis: one row per game per analysis version, one row per ply (Phase 5).

`GameAnalysis` is versioned rather than overwritten in place — re-analysing under new
settings (a deeper baseline, revised thresholds) is additive, and old runs stay available
for comparison. `analysis_version` is a free-text tag the service sets (e.g. an engine
depth/threshold fingerprint), not an enum, since what counts as "a version" is a policy
decision that may change without a schema migration.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum

if TYPE_CHECKING:
    from app.db.models.patterns import MotifFinding, StrategicThemeFinding


class MoveClassification(enum.StrEnum):
    """Move quality label, per the glossary. `BEST` means the played move matches the
    engine's top choice exactly — distinct from `GOOD`, a small but nonzero loss."""

    BEST = "best"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


class GameAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One engine-analysis run over one game."""

    __tablename__ = "game_analysis"

    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_version: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    # {"accuracy_white": .., "accuracy_black": .., "counts": {"best": N, "good": N, ...}}
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    evaluations: Mapped[list[MoveEvaluation]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="MoveEvaluation.ply"
    )
    # Phase 6: tactical/strategic findings ride on this analysis run — see
    # app/db/models/patterns.py for why they key off game_analysis_id rather than game_id.
    motif_findings: Mapped[list[MotifFinding]] = relationship(
        cascade="all, delete-orphan", order_by="MotifFinding.ply"
    )
    theme_findings: Mapped[list[StrategicThemeFinding]] = relationship(
        cascade="all, delete-orphan", order_by="StrategicThemeFinding.ply"
    )


class MoveEvaluation(Base):
    """One ply's engine evaluation and classification.

    Composite primary key `(game_analysis_id, ply)`, no surrogate id — same reasoning as
    `GameMove`: no identity independent of its analysis run and sequence position.
    """

    __tablename__ = "move_evaluations"
    __table_args__ = (PrimaryKeyConstraint("game_analysis_id", "ply", name="pk_move_evaluations"),)

    game_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_analysis.id", ondelete="CASCADE"), nullable=False
    )
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    # Exactly one of eval_cp/mate_in is set — mirrors EngineEvaluation.
    eval_cp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mate_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_move_uci: Mapped[str | None] = mapped_column(String(8), nullable=True)
    pv: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    classification: Mapped[MoveClassification] = mapped_column(
        pg_enum(MoveClassification, "move_classification"), nullable=False
    )
    # Centipawn loss for the move actually played, from the mover's own perspective.
    # Always >= 0. Also what is_critical_moment is thresholded against.
    eval_swing_cp: Mapped[int] = mapped_column(Integer, nullable=False)
    is_critical_moment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Whether the tiered deep pass (ENGINE_DEEP_DEPTH) ran for this ply. Only
    # is_critical_moment plies get re-evaluated at depth; everything else is depth-only.
    deep_analyzed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    analysis: Mapped[GameAnalysis] = relationship(back_populates="evaluations")


__all__ = ["GameAnalysis", "MoveClassification", "MoveEvaluation"]
