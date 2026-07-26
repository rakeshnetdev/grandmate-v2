"""Header normalisation: which side did the profile play? (Phase 4)

Phase 3 leaves `focus_color`/`opponent_name` null because raw ingestion has no way to
answer "which side is the profile" — that requires comparing PGN header names against the
platform usernames linked to the profile, which is exactly what this module does.

**Matching, not authentication.** This compares against *any* linked `ProfileSource`,
verified or not — unlike permission-sensitive checks (Phase 9's cross-profile viewing),
getting this wrong has no security consequence, only a wrong display label the profile
owner can see and is free to correct. Restricting to verified sources would make this
feature dead code today, since no login is verified yet (ADR-0014).

**Exact match only, case-insensitive.** PGN header names for real OTB games are commonly
"Last,First" (e.g. "Carlsen,Magnus"), which will not match a Lichess/Chess.com handle —
that is expected and correct: an uploaded historical game the profile is studying, not
playing, should not be mislabelled as theirs. Platform-exported PGNs (Phase 9) use the
handle directly as the header name, where this matches cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.models import GameColor


@dataclass(frozen=True)
class FocusResolution:
    """The outcome of trying to resolve which side the profile played.

    `focus_color`/`opponent_name` are both `None` when the header names don't
    identify the profile — an honest "we don't know," never a guess.
    """

    focus_color: GameColor | None
    opponent_name: str | None


def _normalize(name: str) -> str:
    return name.strip().casefold()


def resolve_focus(*, white: str, black: str, linked_usernames: list[str]) -> FocusResolution:
    """Match ``white``/``black`` against the profile's linked platform usernames.

    Exactly one match resolves the game. No match, or both sides matching (self-play, or
    two linked accounts colliding with generic names), leaves both fields `None`.
    """
    normalized_links = {_normalize(u) for u in linked_usernames}
    white_matches = _normalize(white) in normalized_links
    black_matches = _normalize(black) in normalized_links

    if white_matches and not black_matches:
        return FocusResolution(focus_color=GameColor.WHITE, opponent_name=black)
    if black_matches and not white_matches:
        return FocusResolution(focus_color=GameColor.BLACK, opponent_name=white)
    return FocusResolution(focus_color=None, opponent_name=None)


__all__ = ["FocusResolution", "resolve_focus"]
