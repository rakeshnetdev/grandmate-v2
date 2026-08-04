"""Intent classification parsing and the agent system message (Phase 10)."""

from __future__ import annotations

import json

from app.db.models import Persona
from app.domain.chat.prompts import (
    DEFAULT_INTENT,
    INTENTS,
    build_agent_system_message,
    build_intent_messages,
    parse_intent,
)
from app.integrations.llm.base import Message


class TestParseIntent:
    def test_parses_a_valid_intent(self) -> None:
        assert parse_intent(json.dumps({"intent": "multi_game"})) == "multi_game"

    def test_falls_back_to_the_default_on_off_taxonomy_intent(self) -> None:
        assert parse_intent(json.dumps({"intent": "roast_my_opening"})) == DEFAULT_INTENT

    def test_falls_back_to_the_default_on_malformed_json(self) -> None:
        assert parse_intent("not json") == DEFAULT_INTENT

    def test_falls_back_to_the_default_on_unexpected_shape(self) -> None:
        assert parse_intent(json.dumps(["knowledge"])) == DEFAULT_INTENT

    def test_the_default_is_itself_a_member_of_the_taxonomy(self) -> None:
        """Otherwise every fallback would route the agent down the unknown-route branch."""
        assert DEFAULT_INTENT in INTENTS


class TestBuildIntentMessages:
    def test_carries_the_question_as_the_user_message(self) -> None:
        messages = build_intent_messages("why was 23...Nxe4 bad?")

        assert messages[0].role == "system"
        assert messages[-1].role == "user"
        assert messages[-1].content == "why was 23...Nxe4 bad?"


class TestBuildAgentSystemMessage:
    def test_mentions_the_active_game_when_one_is_set(self) -> None:
        message = build_agent_system_message(
            Persona.SELF_LEARNER, active_game_id="g-1", route="single_game"
        )

        assert message.content is not None
        assert "g-1" in message.content

    def test_says_no_game_is_open_when_none_is_set(self) -> None:
        message = build_agent_system_message(
            Persona.COACH, active_game_id=None, route="single_game"
        )

        assert message.content is not None
        assert "No specific game is currently open" in message.content

    def test_kid_voice_avoids_jargon(self) -> None:
        message = build_agent_system_message(Persona.KID, active_game_id=None, route="single_game")

        assert message.content is not None
        assert "Avoid jargon" in message.content


class TestRouteSelectsTheContext:
    """The route is what stops a general question being answered from the open game.

    `single_game` is the only route that may reach for the active game — the whole point
    of the other three is that an open game must not be dragged into an answer that was
    never about it.
    """

    def test_a_knowledge_route_ignores_the_open_game(self) -> None:
        content = build_agent_system_message(
            Persona.SELF_LEARNER, active_game_id="g-1", route="knowledge"
        ).content

        assert content is not None
        # The game is open, but the route says the question is not about it.
        assert "g-1" not in content
        assert "do not answer from the open game" in content

    def test_a_multi_game_route_asks_for_aggregate_tools(self) -> None:
        content = build_agent_system_message(
            Persona.SELF_LEARNER, active_game_id="g-1", route="multi_game"
        ).content

        assert content is not None
        assert "g-1" not in content
        assert "patterns across multiple games" in content

    def test_a_train_next_route_asks_for_training_advice(self) -> None:
        content = build_agent_system_message(
            Persona.SELF_LEARNER, active_game_id="g-1", route="train_next"
        ).content

        assert content is not None
        assert "what to practise next" in content

    def test_an_unrecognised_route_degrades_to_the_game_context(self) -> None:
        """The router is an LLM, so an off-taxonomy value has to land somewhere sane
        rather than producing a message with no context paragraph at all."""
        content = build_agent_system_message(
            Persona.SELF_LEARNER, active_game_id="g-1", route="not-a-route"
        ).content

        assert content is not None
        assert "g-1" in content


def _message(*, persona: Persona = Persona.SELF_LEARNER, route: str = DEFAULT_INTENT) -> Message:
    """The template-level assertions below vary neither persona nor game, so they say so
    once here rather than repeating the same three arguments at every call site."""
    return build_agent_system_message(persona, active_game_id=None, route=route)


class TestScope:
    """The assistant answers chess, not whatever the user happens to paste.

    Without this the underlying model cheerfully debugs a stack trace: the grounding
    guardrail only checks *citations*, and a non-chess answer carries none, so it passes
    validation trivially. The limit has to be stated in the prompt because nothing
    downstream enforces it.
    """

    def test_out_of_scope_questions_are_declined(self) -> None:
        content = _message().content

        assert "out of scope" in content
        assert "only help with chess" in content

    def test_a_pasted_error_is_named_as_the_common_case(self) -> None:
        """The case that prompted the rule — and the one a model is most tempted by,
        since it looks like a user in obvious need of help."""
        content = _message().content

        assert "error messages or stack traces" in content

    def test_chess_conversation_and_app_questions_stay_in_scope(self) -> None:
        """The limit must not swallow the two things the chat is also meant to do —
        recall its own thread, and explain how GrandMate works."""
        content = _message().content

        assert "this conversation" in content
        assert "how to use GrandMate" in content

    def test_the_limit_applies_to_every_persona_and_route(self) -> None:
        for persona in Persona:
            for route in INTENTS:
                assert "out of scope" in _message(persona=persona, route=route).content


class TestAnswerFormatting:
    """The chat panel renders `answer` as markdown (frontend `Prose`), so the agent is
    told it may use it. Without this the model writes flat paragraphs and a list of five
    weaknesses arrives as one run-on sentence.
    """

    def test_markdown_bullets_are_offered(self) -> None:
        content = _message().content

        assert "rendered as markdown" in content
        assert '"- " bullet list' in content

    def test_the_narrow_panel_rules_out_headings_and_tables(self) -> None:
        content = _message().content

        assert "No headings, tables, or code blocks" in content

    def test_moves_are_left_for_the_renderer_to_highlight(self) -> None:
        """`Prose`'s highlighter styles SAN itself — a model that also bolds or
        backticks a move produces a doubly-decorated token."""
        content = _message().content

        assert "never wrap them in backticks or bold yourself" in content

    def test_the_guidance_reaches_every_persona_and_route(self) -> None:
        for persona in Persona:
            for route in INTENTS:
                assert "rendered as markdown" in _message(persona=persona, route=route).content


class TestConversationRecallIsNotAChessClaim:
    """A question about the exchange is answerable from the thread.

    Without this rule the agent hunts for tool results that cannot exist for "what did
    you say earlier", and either answers with no citations (fine) or invents one to
    satisfy the response format (not fine — the guardrail rejects it, and after two
    attempts `build_fallback_answer` replaces the model's perfectly good recall with the
    ungrounded fallback text).
    """

    def test_the_transcript_is_named_as_a_source(self) -> None:
        content = _message().content

        assert "The conversation above is itself a source" in content

    def test_tools_are_still_required_for_facts_not_yet_established(self) -> None:
        content = _message().content

        assert "call the tools for those as usual" in content

    def test_chess_grounding_is_unchanged(self) -> None:
        """The rule carves out conversation recall and nothing else."""
        content = _message().content

        assert "Ground every chess claim in a tool result" in content
        assert "Never assert that a move was played" in content

    def test_inventing_a_citation_is_explicitly_forbidden(self) -> None:
        content = _message().content

        assert "Never invent a citation" in content

    def test_the_rule_applies_to_every_persona_and_every_route(self) -> None:
        """The carve-out lives in the shared template, so no persona/route combination
        may drop it — a route that did would silently reintroduce the fallback bug."""
        for persona in Persona:
            for route in INTENTS:
                content = _message(persona=persona, route=route).content
                assert "The conversation above is itself a source" in content
