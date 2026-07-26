"""Header normalisation unit tests: which side is the profile? No database — pure."""

from __future__ import annotations

from app.db.models import GameColor
from app.domain.games.normalization import resolve_focus


class TestResolveFocus:
    def test_matches_white_case_insensitively(self) -> None:
        result = resolve_focus(
            white="DrNykterstein", black="Hikaru", linked_usernames=["drnykterstein"]
        )

        assert result.focus_color == GameColor.WHITE
        assert result.opponent_name == "Hikaru"

    def test_matches_black(self) -> None:
        result = resolve_focus(white="Carlsen,Magnus", black="hikaru", linked_usernames=["Hikaru"])

        assert result.focus_color == GameColor.BLACK
        assert result.opponent_name == "Carlsen,Magnus"

    def test_strips_whitespace_before_comparing(self) -> None:
        result = resolve_focus(
            white=" DrNykterstein ", black="Hikaru", linked_usernames=["drnykterstein"]
        )

        assert result.focus_color == GameColor.WHITE

    def test_no_match_leaves_both_fields_none(self) -> None:
        """An uploaded historical game the profile is studying, not playing — never
        guessed."""
        result = resolve_focus(
            white="Carlsen,Magnus", black="Caruana,Fabiano", linked_usernames=["drnykterstein"]
        )

        assert result.focus_color is None
        assert result.opponent_name is None

    def test_both_sides_matching_leaves_both_fields_none(self) -> None:
        """Self-play, or ambiguous — not guessed either way."""
        result = resolve_focus(
            white="drnykterstein", black="hikaru", linked_usernames=["drnykterstein", "hikaru"]
        )

        assert result.focus_color is None
        assert result.opponent_name is None

    def test_no_linked_usernames_leaves_both_fields_none(self) -> None:
        result = resolve_focus(white="Alice", black="Bob", linked_usernames=[])

        assert result.focus_color is None
        assert result.opponent_name is None
