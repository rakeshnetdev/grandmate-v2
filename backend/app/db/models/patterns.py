"""Opening identification and pattern intelligence (Phase 6, D-011/D-012, ADR-0009).

Three tables, two different lifecycles:

- `game_openings` keys off `game_id` directly. Opening identification only needs
  `GameMove.epd_after` (Phase 4 output) — it has no dependency on engine analysis, so it
  is computed inline during canonicalization, same request as Phase 4 itself.
- `game_tactics` (tactical motifs) and `game_strategy_tags` (strategic themes) key off
  `game_analysis_id`, not `game_id`. Confidence scoring and evidence for several detectors
  read `MoveEvaluation` (eval swing, classification) for corroboration, so both tables
  only make sense once a `GameAnalysis` run exists — detection rides along in the
  background job right after `AnalysisService.analyze_game()` succeeds (Phase 5's
  dispatcher), not a separate job kind. See `app/domain/patterns/service.py`.

Neither findings table is versioned the way `GameAnalysis` is: detectors are pure
functions over already-stored data, cheap to recompute, so a re-run (e.g. after a
detector bugfix) deletes and replaces a game's rows rather than keeping historical runs
side by side. `game_openings` follows the same non-versioned shape via a unique
constraint on `game_id`.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.db.models.games import GameColor


class MotifType(enum.StrEnum):
    """Tactical motifs detected by Phase 6.

    Ten of the sixteen motifs in `glossary.md`'s starter taxonomy — the low/medium
    difficulty ones, confirmed with the owner before coding. The six high-difficulty
    motifs (deflection, decoy, overloading, interference, zwischenzug, windmill) are a
    documented gap, not silently dropped: they need engine-corroborated confidence that a
    confident wrong label would actively mislead a learner without, per the glossary's own
    sequencing note.
    """

    FORK = "fork"
    PIN = "pin"
    SKEWER = "skewer"
    DISCOVERED_ATTACK = "discovered_attack"
    DOUBLE_CHECK = "double_check"
    BACK_RANK_MATE = "back_rank_mate"
    SMOTHERED_MATE = "smothered_mate"
    HANGING_PIECE = "hanging_piece"
    REMOVING_THE_DEFENDER = "removing_the_defender"
    X_RAY = "x_ray"


class StrategicThemeType(enum.StrEnum):
    """Strategic themes detected by Phase 6 — all ten from `glossary.md`'s starter
    taxonomy. Unlike motifs, none of these were judged to need engine corroboration to
    ship safely: each is a structural, span-of-plies property computed directly from
    replayed positions (and, for time-trouble collapse, move classifications)."""

    WEAK_KING_SAFETY = "weak_king_safety"
    PAWN_STRUCTURE_DAMAGE = "pawn_structure_damage"
    PASSED_PAWN_CREATION = "passed_pawn_creation"
    PIECE_ACTIVITY_IMBALANCE = "piece_activity_imbalance"
    BAD_BISHOP = "bad_bishop"
    OPEN_FILE_CONTROL = "open_file_control"
    CENTRE_CONTROL = "centre_control"
    SPACE_ADVANTAGE = "space_advantage"
    DEVELOPMENT_LAG = "development_lag"
    TIME_TROUBLE_COLLAPSE = "time_trouble_collapse"


class OpeningMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The deepest Lichess-openings-dataset EPD match along a game's played positions.

    One row per game, not versioned — re-vendoring the dataset or fixing the lookup just
    replaces this row. `matched_ply` is `GameMove.ply` of the position that matched
    (0-indexed, same convention as `GameMove`), which is also the row a report links back
    to for "this is where book knowledge ended".
    """

    __tablename__ = "game_openings"
    __table_args__ = (UniqueConstraint("game_id", name="uq_game_openings_game_id"),)

    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    eco: Mapped[str] = mapped_column(String(3), nullable=False)
    opening_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # The matched position itself — not in the original data-model.md sketch, added so a
    # report or a later re-lookup does not have to re-derive it from game_moves via
    # matched_ply. Cheap to store, saves a join in the common read path.
    epd: Mapped[str] = mapped_column(String(90), nullable=False)
    matched_ply: Mapped[int] = mapped_column(Integer, nullable=False)


class MotifFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One tactical motif detected at one ply, scoped to a specific `GameAnalysis` run.

    `side` is not in the original data-model.md sketch: a motif belongs to whichever side
    created or benefits from it (the mover, for every motif this phase ships), and
    profile-scoped rollups (Phase 8) need to filter "the profile's own tactics" from "what
    the opponent did" constantly. Burying that in `evidence` would make every rollup query
    parse JSON to answer a question a column answers directly.
    """

    __tablename__ = "game_tactics"

    game_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_analysis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    side: Mapped[GameColor] = mapped_column(pg_enum(GameColor, "game_color"), nullable=False)
    motif: Mapped[MotifType] = mapped_column(pg_enum(MotifType, "motif_type"), nullable=False)
    # 0.00-1.00. Not decoration — this is what a confidence floor filters on
    # (PATTERN_MIN_CONFIDENCE_TO_PERSIST) and what a coaching report chooses to surface.
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    # Squares, pieces, and — where a detector uses it — the corroborating
    # eval_swing_cp/classification from this same GameAnalysis run. What a reviewer reads
    # when a detector misfires, and what a future grounding guardrail checks a claim
    # against (data-model.md).
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class StrategicThemeFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One strategic theme detected over a span of plies, scoped to a `GameAnalysis` run.

    `ply` is the span's start ply, per data-model.md ("ply range start for strategy
    tags"); the span's end and supporting detail live in `evidence`, not as their own
    columns — strategic evidence genuinely varies in shape by theme (a pawn-structure
    span looks nothing like a king-safety span), where motif evidence does not need that
    flexibility as badly.
    """

    __tablename__ = "game_strategy_tags"

    game_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_analysis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    side: Mapped[GameColor] = mapped_column(pg_enum(GameColor, "game_color"), nullable=False)
    theme: Mapped[StrategicThemeType] = mapped_column(
        pg_enum(StrategicThemeType, "strategic_theme_type"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = [
    "MotifFinding",
    "MotifType",
    "OpeningMatch",
    "StrategicThemeFinding",
    "StrategicThemeType",
]
