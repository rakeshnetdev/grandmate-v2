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


class TestConversationRecallIsNotAChessClaim:
    """A question about the exchange is answerable from the thread.

    Without this rule the agent hunts for tool results that cannot exist for "what did
    you say earlier", and either answers with no citations (fine) or invents one to
    satisfy the response format (not fine — the guardrail rejects it, and after two
    attempts `build_fallback_answer` replaces the model's perfectly good recall with the
    ungrounded fallback text).
    """

    def test_the_transcript_is_named_as_a_source(self) -> None:
        content = build_agent_system_message(Persona.SELF_LEARNER, active_game_id=None).content

        assert "The conversation above is itself a source" in content

    def test_tools_are_still_required_for_facts_not_yet_established(self) -> None:
        content = build_agent_system_message(Persona.SELF_LEARNER, active_game_id=None).content

        assert "call the tools for those as usual" in content

    def test_chess_grounding_is_unchanged(self) -> None:
        """The rule carves out conversation recall and nothing else."""
        content = build_agent_system_message(Persona.SELF_LEARNER, active_game_id=None).content

        assert "Ground every chess claim in a tool result" in content
        assert "Never assert that a move was played" in content

    def test_inventing_a_citation_is_explicitly_forbidden(self) -> None:
        content = build_agent_system_message(Persona.SELF_LEARNER, active_game_id=None).content

        assert "Never invent a citation" in content

    def test_the_rule_applies_to_every_persona(self) -> None:
        for persona in Persona:
            content = build_agent_system_message(persona, active_game_id=None).content
            assert "The conversation above is itself a source" in content
