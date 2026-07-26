"""Games and their canonical move records (Phase 3 ingestion, Phase 4 canonicalization).

`Game` mirrors the documented `games` table. Three columns track the Phase 3 / Phase 4
boundary explicitly rather than leaving it implicit:

- `focus_color` / `opponent_name` are nullable — populated by Phase 4's header
  normalisation policy when exactly one PGN header name matches a linked platform
  username for the profile; left `null` when that can't be determined (self-play, a
  studied game that isn't the profile's own, no linked source yet). Never guessed.
- `canonicalized_at` is null until Phase 4's replay succeeds for this game.
- `parse_error` holds structured detail when replay fails. A canonicalization failure
  does not un-import the game — the row, raw PGN, and dedup guarantee from Phase 3 all
  stand; the game is just not yet (or not) browsable in canonical form.

`GameMove` is one row per ply, written only on successful canonicalization.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.db.models.identity import GameSource

if TYPE_CHECKING:
    from app.db.models.imports import Job


class GameColor(enum.StrEnum):
    WHITE = "white"
    BLACK = "black"


class Game(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A successfully ingested, deduplicated game.

    Only games that pass Phase 3 validation and are not duplicates get a row here —
    ingestion rejections are reported through the owning `Job.progress`, never persisted
    as game rows. Canonicalization (Phase 4) failures are different: the game stays,
    tracked via `parse_error`.
    """

    __tablename__ = "games"
    __table_args__ = (
        # Scopes deduplication to a profile: the same game uploaded by two different
        # profiles is not a duplicate of each other.
        UniqueConstraint("profile_id", "content_hash", name="uq_games_profile_content_hash"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[GameSource] = mapped_column(pg_enum(GameSource, "game_source"), nullable=False)
    # Platform game id for Lichess/Chess.com imports (Phase 9). Null for manual upload.
    source_game_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # sha256 over normalised movetext + result + players + date — see
    # app/domain/imports/parsing.py for the exact recipe.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    headers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    focus_color: Mapped[GameColor | None] = mapped_column(
        pg_enum(GameColor, "game_color"), nullable=True
    )
    opponent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    time_control: Mapped[str | None] = mapped_column(String(64), nullable=True)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_pgn_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Phase 4: set once move replay + FEN/EPD generation succeeds for this game.
    canonicalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Structured failure detail when replay fails — see app/domain/games/parsing.py for
    # the taxonomy. Null while canonicalization hasn't run or has succeeded.
    parse_error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    job: Mapped[Job | None] = relationship(back_populates="games")
    moves: Mapped[list[GameMove]] = relationship(
        back_populates="game", cascade="all, delete-orphan", order_by="GameMove.ply"
    )


class GameMove(Base):
    """One ply of a canonicalized game. Written only on successful replay.

    Composite primary key `(game_id, ply)`, no surrogate id — a move record has no
    identity independent of its game and position in the sequence, and `data-model.md`
    specifies this shape explicitly.
    """

    __tablename__ = "game_moves"
    __table_args__ = (PrimaryKeyConstraint("game_id", "ply", name="pk_game_moves"),)

    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    # Zero-indexed: ply 0 is White's first move.
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    san: Mapped[str] = mapped_column(String(16), nullable=False)
    uci: Mapped[str] = mapped_column(String(8), nullable=False)
    fen_before: Mapped[str] = mapped_column(String(100), nullable=False)
    fen_after: Mapped[str] = mapped_column(String(100), nullable=False)
    # Indexed: the opening-lookup key (EPD is a FEN without move counters, so it
    # identifies a position independent of how many moves it took to reach — see ADR-0009).
    epd_after: Mapped[str] = mapped_column(String(90), nullable=False, index=True)
    # Milliseconds remaining on the clock after this move, where the source PGN provides
    # a `[%clk ...]` annotation. Null otherwise — most manually uploaded games won't have it.
    clock_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    game: Mapped[Game] = relationship(back_populates="moves")


__all__ = ["Game", "GameColor", "GameMove"]
