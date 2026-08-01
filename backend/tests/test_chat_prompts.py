"""Intent classification parsing and the agent system message (Phase 10)."""

from __future__ import annotations

import json

from app.db.models import Persona
from app.domain.chat.prompts import (
    INTENTS,
    build_agent_system_message,
    build_intent_messages,
    parse_intent,
)


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


class TestConversationalIntent:
    """A question about the conversation is not a chess claim (Phase 10 follow-up).

    Without this the agent hunts for tool results it cannot find, emits citations it
    cannot support, and the guardrail correctly rejects them — leaving the reader with
    the ungrounded fallback in answer to a question that was never about chess.
    """

    def test_conversational_is_in_the_taxonomy(self) -> None:
        assert "conversational" in INTENTS
        assert parse_intent('{"intent": "conversational"}') == "conversational"

    def test_conversational_turns_may_answer_from_the_thread(self) -> None:
        content = build_agent_system_message(
            Persona.SELF_LEARNER, active_game_id=None, intent="conversational"
        ).content

        assert "the conversation so far" in content

    def test_other_intents_do_not_get_the_block(self) -> None:
        for intent in ("explain", "compare", "summarise", "train_next", None):
            content = build_agent_system_message(
                Persona.SELF_LEARNER, active_game_id=None, intent=intent
            ).content
            assert "the conversation so far" not in content

    def test_chess_grounding_is_unchanged_for_conversational_turns(self) -> None:
        """The whole point: this loosens sourcing for talk about the conversation, and
        nothing at all for chess claims."""
        content = build_agent_system_message(
            Persona.SELF_LEARNER, active_game_id=None, intent="conversational"
        ).content

        assert "Ground every chess claim in a tool result" in content
        assert "still needs its citation" in content

    def test_tools_remain_available_on_a_conversational_turn(self) -> None:
        content = build_agent_system_message(
            Persona.SELF_LEARNER, active_game_id=None, intent="conversational"
        ).content

        assert "Still call tools" in content
