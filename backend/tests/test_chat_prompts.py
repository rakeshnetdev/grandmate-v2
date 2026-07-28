"""Intent classification parsing and the agent system message (Phase 10)."""

from __future__ import annotations

import json

from app.db.models import Persona
from app.domain.chat.prompts import build_agent_system_message, build_intent_messages, parse_intent


class TestParseIntent:
    def test_parses_a_valid_intent(self) -> None:
        assert parse_intent(json.dumps({"intent": "compare"})) == "compare"

    def test_falls_back_to_explain_on_off_taxonomy_intent(self) -> None:
        assert parse_intent(json.dumps({"intent": "roast_my_opening"})) == "explain"

    def test_falls_back_to_explain_on_malformed_json(self) -> None:
        assert parse_intent("not json") == "explain"

    def test_falls_back_to_explain_on_unexpected_shape(self) -> None:
        assert parse_intent(json.dumps(["explain"])) == "explain"


class TestBuildIntentMessages:
    def test_carries_the_question_as_the_user_message(self) -> None:
        messages = build_intent_messages("why was 23...Nxe4 bad?")

        assert messages[0].role == "system"
        assert messages[-1].role == "user"
        assert messages[-1].content == "why was 23...Nxe4 bad?"


class TestBuildAgentSystemMessage:
    def test_mentions_the_active_game_when_one_is_set(self) -> None:
        message = build_agent_system_message(Persona.SELF_LEARNER, active_game_id="g-1")

        assert message.content is not None
        assert "g-1" in message.content

    def test_says_no_game_is_open_when_none_is_set(self) -> None:
        message = build_agent_system_message(Persona.COACH, active_game_id=None)

        assert message.content is not None
        assert "No specific game is currently open" in message.content

    def test_kid_voice_forbids_centipawn_values(self) -> None:
        message = build_agent_system_message(Persona.KID, active_game_id=None)

        assert message.content is not None
        assert "centipawn" in message.content.lower()
