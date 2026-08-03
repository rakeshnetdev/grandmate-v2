"""PGN parsing and validation for raw ingestion (Phase 3).

Deliberately shallow: this reads headers and the mainline move list only, to validate a
game and compute its dedup hash. It does **not** replay positions to FEN/EPD or persist
per-move records — that is Phase 4's canonical game object. Keeping the boundary here
means Phase 3 never touches the deterministic-core rules checked by
`tests/test_layer_boundaries.py`.

A source file may contain one game or many (standard PGN concatenation, e.g. a Lichess
export) — both are the same code path here, so "batch" needs no special case for the
single-game input the user actually starts with.
"""

from __future__ import annotations

import enum
import hashlib
import io
from dataclasses import dataclass, field

import chess.pgn

# Games above this line count fail structural sanity (a real chess game cannot run this
# long); catches a garbage stream that python-chess still manages to iterate on. Not user
# configurable — this is a sanity bound, not a policy tunable like MAX_GAMES_PER_IMPORT.
_MAX_PLAUSIBLE_PLIES = 1000

# python-chess reports every variant that shares standard chess rules under this UCI name,
# which is exactly the set our engine adapter can evaluate: "Standard", "From Position",
# and "Chess960" all resolve to it. Anything else (Antichess, Atomic, Crazyhouse, Horde,
# King of the Hill, Three-check, Racing Kings) is a different game with different legality
# rules, and must not enter the pipeline — see `_variant_of`.
_SUPPORTED_UCI_VARIANT = "chess"


def _variant_of(game: chess.pgn.Game) -> str | None:
    """The game's UCI variant name, or ``None`` when the `Variant` tag is unrecognisable.

    Rejecting non-standard variants at ingestion is not squeamishness about scope: their
    positions are illegal under standard rules (an Antichess game legally captures both
    kings), and feeding a kingless FEN to standard Stockfish **segfaults the engine
    process** rather than returning an error. The crash surfaces far downstream as a dead
    analysis job, so the boundary is enforced here, at the single point every source —
    paste, upload, batch, Lichess, Chess.com — passes through.

    Resolution is delegated to python-chess rather than matched against a hardcoded list
    of variant names, so a variant we have never seen is still classified correctly.
    """
    try:
        return game.board().uci_variant
    except (ValueError, KeyError):
        # An unparseable or unknown `Variant` tag. Not standard chess by any reading, so
        # it is rejected on the same branch rather than allowed through on a technicality.
        return None


class RejectionReason(enum.StrEnum):
    """Why a single game within a submission was not imported."""

    MALFORMED_PGN = "malformed_pgn"
    NO_MOVES = "no_moves"
    MISSING_REQUIRED_TAG = "missing_required_tag"
    IMPLAUSIBLE_LENGTH = "implausible_length"
    DUPLICATE_GAME = "duplicate_game"
    UNSUPPORTED_VARIANT = "unsupported_variant"


@dataclass(frozen=True)
class ParsedGame:
    """A structurally valid game, ready for dedup checking and persistence."""

    headers: dict[str, str]
    moves_uci: list[str]
    content_hash: str
    # This game's own serialized PGN — not the source text it was found in. A source file
    # holding several games must not leave every one of them pointing at storage for the
    # whole file; each game gets exactly its own text. `str(game)` round-trips through
    # python-chess (headers, moves, variations, comments, NAGs all preserved).
    pgn_text: str


@dataclass(frozen=True)
class RejectedGame:
    """A game that did not make it in, and why — surfaced to the caller, never silently
    dropped."""

    index: int
    reason: RejectionReason
    detail: str


@dataclass(frozen=True)
class ParseResult:
    parsed: list[ParsedGame] = field(default_factory=list)
    rejected: list[RejectedGame] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.parsed) + len(self.rejected)


def _content_hash(headers: chess.pgn.Headers, moves_uci: list[str]) -> str:
    """sha256 over normalised movetext + result + players + date.

    Ignores comments, clock annotations, and header ordering/whitespace, so the same game
    re-exported by a different tool still hashes identically. Combined at the service layer
    with a (profile_id, content_hash) uniqueness check.
    """
    key = "|".join(
        [
            " ".join(moves_uci),
            headers.get("Result", "*"),
            headers.get("White", ""),
            headers.get("Black", ""),
            headers.get("UTCDate", headers.get("Date", "")),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_pgn_text(text: str) -> ParseResult:
    """Parse every game in ``text``. One malformed game does not stop the rest."""
    stream = io.StringIO(text)
    result = ParseResult()
    index = 0

    while True:
        try:
            game = chess.pgn.read_game(stream)
        except Exception as exc:
            result.rejected.append(
                RejectedGame(index=index, reason=RejectionReason.MALFORMED_PGN, detail=str(exc))
            )
            break

        if game is None:
            break

        white = game.headers.get("White", "?")
        black = game.headers.get("Black", "?")
        variant = _variant_of(game)

        # Checked before `game.errors`: a variant game whose moves are illegal under
        # standard rules would otherwise be reported as "malformed", which sends whoever
        # reads the rejection looking for a corrupt file that does not exist.
        if variant != _SUPPORTED_UCI_VARIANT:
            result.rejected.append(
                RejectedGame(
                    index=index,
                    reason=RejectionReason.UNSUPPORTED_VARIANT,
                    detail=(
                        f"{game.headers.get('Variant', 'unknown')} is not standard chess "
                        "and cannot be analysed"
                    ),
                )
            )
        elif game.errors:
            result.rejected.append(
                RejectedGame(
                    index=index,
                    reason=RejectionReason.MALFORMED_PGN,
                    detail=str(game.errors[0]),
                )
            )
        elif white in ("", "?") or black in ("", "?"):
            result.rejected.append(
                RejectedGame(
                    index=index,
                    reason=RejectionReason.MISSING_REQUIRED_TAG,
                    detail="White and Black tags are both required",
                )
            )
        else:
            moves_uci = [move.uci() for move in game.mainline_moves()]
            if not moves_uci:
                result.rejected.append(
                    RejectedGame(
                        index=index, reason=RejectionReason.NO_MOVES, detail="Game has no moves"
                    )
                )
            elif len(moves_uci) > _MAX_PLAUSIBLE_PLIES:
                result.rejected.append(
                    RejectedGame(
                        index=index,
                        reason=RejectionReason.IMPLAUSIBLE_LENGTH,
                        detail=f"{len(moves_uci)} plies exceeds the plausible maximum",
                    )
                )
            else:
                result.parsed.append(
                    ParsedGame(
                        headers=dict(game.headers),
                        moves_uci=moves_uci,
                        content_hash=_content_hash(game.headers, moves_uci),
                        pgn_text=str(game),
                    )
                )
        index += 1

    if index == 0:
        # `read_game` returned None on the very first call: no game-shaped content at all.
        result.rejected.append(
            RejectedGame(
                index=0,
                reason=RejectionReason.MALFORMED_PGN,
                detail="No parseable game found in submitted text",
            )
        )

    return result


__all__ = ["ParseResult", "ParsedGame", "RejectedGame", "RejectionReason", "parse_pgn_text"]
