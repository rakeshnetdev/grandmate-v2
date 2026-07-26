"""Canonical game parsing: full move replay, FEN/EPD generation (Phase 4).

Where `domain/imports/parsing.py` reads headers and a bare move list to validate and hash
a submission, this module does the real work: replay every move on a fresh board and
record the position before and after it. That is what a "canonical game object" means —
Phase 3 only proved a game was *plausible*, this proves every position is reconstructible.

Deliberately pure — no I/O, no database, no storage access. `GameParsingService` in
`service.py` owns fetching the stored PGN and persisting the result; this module only
turns PGN text into `CanonicalMove` records or raises `CanonicalizationError`.
"""

from __future__ import annotations

import enum
import io
from dataclasses import dataclass

import chess.pgn


class CanonicalizationFailureReason(enum.StrEnum):
    """Why a game that already passed Phase 3's ingestion check still failed replay.

    Distinct from `domain.imports.parsing.RejectionReason` on purpose: a rejection means
    "never stored," a canonicalization failure means "stored, but not yet browsable in
    canonical form" — different remediation, different user-facing meaning.
    """

    # The stored PGN could not be parsed at all — should be rare given Phase 3 already
    # validated it, but the stored bytes are a separate read from what Phase 3 saw.
    UNPARSEABLE = "unparseable"
    # Parsed, but replaying a move against a fresh board failed. Also should be rare
    # (Phase 3's `mainline_moves()` walk already resolves each move's legality), but
    # replay is the authoritative check, not an assumption carried over from ingestion.
    REPLAY_ERROR = "replay_error"


class CanonicalizationError(Exception):
    """Raised when a game cannot be turned into canonical move records."""

    def __init__(self, reason: CanonicalizationFailureReason, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class CanonicalMove:
    """One ply, ready to persist as a `GameMove` row."""

    ply: int
    san: str
    uci: str
    fen_before: str
    fen_after: str
    epd_after: str
    clock_ms: int | None


@dataclass(frozen=True)
class CanonicalGame:
    moves: list[CanonicalMove]


def canonicalize_pgn(pgn_text: str) -> CanonicalGame:
    """Fully replay a single game's PGN into per-ply FEN/EPD/SAN/UCI records.

    Raises :class:`CanonicalizationError` on any inconsistency rather than silently
    skipping a bad ply — a canonical game object with a gap in it is worse than no
    canonical object at all, since later phases (engine analysis, opening lookup) assume
    every ply is present and correct.
    """
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception as exc:  # python-chess can raise on truly broken input
        raise CanonicalizationError(CanonicalizationFailureReason.UNPARSEABLE, str(exc)) from exc

    if game is None:
        raise CanonicalizationError(
            CanonicalizationFailureReason.UNPARSEABLE, "No parseable game found"
        )
    if game.errors:
        raise CanonicalizationError(CanonicalizationFailureReason.UNPARSEABLE, str(game.errors[0]))

    board = game.board()
    moves: list[CanonicalMove] = []

    for ply, node in enumerate(game.mainline()):
        fen_before = board.fen()
        try:
            san = board.san(node.move)
            board.push(node.move)
        except Exception as exc:
            raise CanonicalizationError(
                CanonicalizationFailureReason.REPLAY_ERROR,
                f"Ply {ply} ({node.move.uci()}): {exc}",
            ) from exc

        clock_seconds = node.clock()
        moves.append(
            CanonicalMove(
                ply=ply,
                san=san,
                uci=node.move.uci(),
                fen_before=fen_before,
                fen_after=board.fen(),
                epd_after=board.epd(),
                clock_ms=None if clock_seconds is None else round(clock_seconds * 1000),
            )
        )

    if not moves:
        raise CanonicalizationError(CanonicalizationFailureReason.UNPARSEABLE, "Game has no moves")

    return CanonicalGame(moves=moves)


__all__ = [
    "CanonicalGame",
    "CanonicalMove",
    "CanonicalizationError",
    "CanonicalizationFailureReason",
    "canonicalize_pgn",
]
