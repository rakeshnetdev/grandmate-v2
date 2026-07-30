"""Unit tests for `domain/reports/story_prompts.py` (Phase 16b)."""

from __future__ import annotations

from app.domain.reports.facts import Fact
from app.domain.reports.story_prompts import build_story_messages

_FACTS = [Fact(id="summary", kind="summary", severity="info", ply=None, confidence=None)]


def _system_text() -> str:
    messages = build_story_messages(_FACTS, white="A", black="B", result="1-0", focus_color="white")
    return messages[0].content


class TestBuildStoryMessages:
    def test_requires_a_kind_field_with_the_story_vocabulary(self) -> None:
        text = _system_text()
        assert '"kind"' in text
        assert "opening" in text
        assert "middlegame" in text
        assert "endgame" in text
        assert "lesson" in text

    def test_forbids_engine_numbers_and_second_person(self) -> None:
        text = _system_text()
        assert "No engine numbers" in text
        assert 'say "you" or "your"' in text

    def test_user_message_names_the_players_own_color(self) -> None:
        messages = build_story_messages(
            _FACTS, white="A", black="B", result="1-0", focus_color="white"
        )
        assert "played white" in messages[1].content.lower()
